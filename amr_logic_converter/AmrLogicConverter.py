from __future__ import annotations
from dataclasses import dataclass

from functools import reduce
from typing import Callable, Optional, Union, cast

import penman
from penman.tree import Tree, Node, Branch
from penman.graph import Graph

from amr_logic_converter.AmrContext import (
    AmrContext,
    OverrideIsProjectiveCallback,
    OverrideIsProjectiveCallbackInfo,
)
from amr_logic_converter.types import (
    And,
    Constant,
    ConstantType,
    Exists,
    Clause,
    Implies,
    Not,
    Predicate,
    Variable,
    Atom,
)


@dataclass
class OverrideQuantificationCallbackInfo:
    """Metadata passed to the OverrideQuantificationCallback wtih info about the node being processed"""

    instance_name: str
    bound_instance: Variable | Constant
    node: Node
    depth: int
    amr_tree: Tree
    is_negated: bool


OverrideQuantificationCallback = Callable[
    [Clause, OverrideQuantificationCallbackInfo], Union[Clause, None]
]


@dataclass
class OverrideConjunctionCallbackInfo:
    """Metadata passed to the OverrideConjunctionCallback wtih info about the node being processed"""

    predicate_term: Atom
    closure_term: Clause | None
    subterms: list[Clause]
    condition_term: Clause | None
    instance_name: str
    bound_instance: Variable | Constant
    node: Node
    depth: int
    amr_tree: Tree


OverrideConjunctionCallback = Callable[
    [Clause, OverrideConjunctionCallbackInfo], Union[Clause, None]
]


def normalize_atom(atom: Atom) -> Atom:
    # flip :ARGX-of(x,y) to :ARGX(y,x)
    if atom.symbol.endswith("-of") and len(atom.terms) == 2:
        predicate = Predicate(atom.symbol[:-3], atom.predicate.alignment)
        return predicate(atom.terms[1], atom.terms[0])
    return atom


def determine_const_type(value: str) -> ConstantType:
    return "string" if value.startswith('"') else "symbol"


class AmrLogicConverter:
    """
    Main entry point for converting AMR to a logic formula.

    basic usage:
    converter = AmrLogicConverter()
    logic = converter.convert(
        '(c / chase-01~4'
        '   :ARG0~5 (d / dog~7)'
        '   :ARG0~3 (c / cat~2))'
    )
    print(logic)
    """

    invert_relations: bool
    existentially_quantify_instances: bool
    use_variables_for_instances: bool
    maximally_hoist_coreferences: bool
    capitalize_variables: bool
    use_implies_for_conditions: bool
    override_is_projective: Optional[OverrideIsProjectiveCallback]
    override_quantification: Optional[OverrideQuantificationCallback]
    override_conjunction: Optional[OverrideConjunctionCallback]

    def __init__(
        self,
        invert_relations: bool = True,
        existentially_quantify_instances: bool = False,
        use_variables_for_instances: bool = False,
        maximally_hoist_coreferences: bool = False,
        capitalize_variables: bool = True,
        use_implies_for_conditions: bool = False,
        override_is_projective: Optional[OverrideIsProjectiveCallback] = None,
        override_quantification: Optional[OverrideQuantificationCallback] = None,
        override_conjunction: Optional[OverrideConjunctionCallback] = None,
    ) -> None:
        self.invert_relations = invert_relations
        self.capitalize_variables = capitalize_variables
        self.existentially_quantify_instances = existentially_quantify_instances
        self.use_variables_for_instances = use_variables_for_instances
        self.use_implies_for_conditions = use_implies_for_conditions
        self.maximally_hoist_coreferences = maximally_hoist_coreferences
        self.override_is_projective = override_is_projective
        self.override_quantification = override_quantification
        self.override_conjunction = override_conjunction

    def _get_bound_instance(self, instance_name: str) -> Variable | Constant:
        use_variables_for_instances = (
            self.existentially_quantify_instances or self.use_variables_for_instances
        )
        bound_instance: Variable | Constant = (
            Variable(self._var_name(instance_name))
            if use_variables_for_instances
            else Constant(instance_name, "instance")
        )
        return bound_instance

    def _reprioritize_edge(self, edge: Branch) -> int:
        """Reprioritize edges to make it possible to change where in the tree coreferenced instances are defined"""
        role = edge[0]
        # make sure :condition is processed first if we're rewriting using Implies
        if self.use_implies_for_conditions and role == ":condition":
            return 1
        return 0

    def _sort_edges(self, edges: list[Branch], reverse: bool = True) -> list[Branch]:
        """Sort edges by reprioritized edge priority"""
        return sorted(edges, key=self._reprioritize_edge, reverse=reverse)

    def _var_name(self, name: str) -> str:
        return name.capitalize() if self.capitalize_variables else name

    def _convert_amr_assertive(
        self,
        ctx: AmrContext,
        instance_name: str,
        closure: Optional[Callable[[str], Clause | None]] = None,
    ) -> Clause | None:
        # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥x,φ∥↓ = φ(x)
        # ∥(x\P),φ∥↓ = φ(x)
        # ∥(x\P :RiAi),φ∥↓ = φ(x)
        # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
        if ctx.is_instance_rendered(instance_name):
            return None if closure is None else closure(instance_name)
        node = ctx.get_node_for_instance(instance_name)
        instance_predicate, *edges = node[1]
        bound_instance = self._get_bound_instance(instance_name)
        predicate = Predicate.from_amr_str(instance_predicate[1])
        predicate_term = predicate(bound_instance)
        closure_term = closure(instance_name) if closure is not None else None
        subterms: list[Clause] = []
        condition_term: Clause | None = None

        ctx.mark_instance_rendered(instance_name)
        for (role, target) in self._sort_edges(edges):

            def sub_closure(u: str) -> Atom:
                target: Variable | Constant = self._get_bound_instance(u)
                sub_predicate = Predicate.from_amr_str(role)
                atom = sub_predicate(bound_instance, target)
                return normalize_atom(atom) if self.invert_relations else atom

            # don't include the :condition relation in the logic if we're turning it into an implication
            target_closure: Callable[[str], Atom] | None = sub_closure
            if role == ":condition" and self.use_implies_for_conditions:
                target_closure = None

            target_instance = _get_instance_name(target, ctx)
            subterm: Clause | None = None
            # special case for the :polarity - attribute.
            # skip polarity as is handled in quantification
            if role == ":polarity" and target == "-":
                continue
            elif target_instance is not None:
                target_node = ctx.get_node_for_instance(target_instance)
                subterm = self._convert_amr(ctx, target_node, target_closure)
            else:
                sub_predicate = Predicate.from_amr_str(role)
                sub_atom = sub_predicate(
                    bound_instance, Constant(target, determine_const_type(target))
                )
                subterm = (
                    normalize_atom(sub_atom) if self.invert_relations else sub_atom
                )
            if role == ":condition":
                condition_term = subterm
            else:
                subterms.append(subterm)

        if self.override_conjunction is not None:
            info = OverrideConjunctionCallbackInfo(
                predicate_term=predicate_term,
                closure_term=closure_term,
                subterms=subterms,
                condition_term=condition_term,
                instance_name=instance_name,
                bound_instance=bound_instance,
                depth=ctx.get_instance_depth(instance_name),
                node=node,
                amr_tree=ctx.amr_tree,
            )
            override_result = self.override_conjunction(predicate_term, info)
            if override_result is not None:
                return override_result

        pre_terms = []
        if closure_term is not None:
            pre_terms.append(closure_term)
        if condition_term is not None and not self.use_implies_for_conditions:
            pre_terms.append(condition_term)
        pre_terms.append(predicate_term)
        conjunction = And(*(pre_terms + subterms))
        if condition_term is not None and self.use_implies_for_conditions:
            return Implies(condition_term, conjunction)
        return conjunction

    def _quantify_instance(
        self,
        ctx: AmrContext,
        instance_name: str,
    ) -> Callable[[Clause], Clause]:
        node = ctx.get_node_for_instance(instance_name)
        _instance_predicate, *edges = node[1]
        bound_instance = self._get_bound_instance(instance_name)
        polarity = True
        for role, target in self._sort_edges(edges):
            if role == ":polarity" and target == "-":
                polarity = False

        def quantification_closure(clause: Clause) -> Clause:
            if self.override_quantification is not None:
                override_expr = self.override_quantification(
                    clause,
                    OverrideQuantificationCallbackInfo(
                        node=node,
                        instance_name=instance_name,
                        bound_instance=bound_instance,
                        depth=ctx.get_instance_depth(instance_name),
                        amr_tree=ctx.amr_tree,
                        is_negated=not polarity,
                    ),
                )
                if override_expr is not None:
                    return override_expr
            expr = clause
            if self.existentially_quantify_instances:
                expr = Exists(cast(Variable, bound_instance), body=clause)
            return expr if polarity else Not(expr)

        return quantification_closure

    def _quanitfy_formula(
        self, ctx: AmrContext, formula: Clause, instances: set[str]
    ) -> Clause:
        """Wrap the formula in quantifiers for all instances in the list"""
        sorted_instances = sorted(
            sorted(instances),  # sort alphabetically as a tie-breaker
            key=lambda instance: ctx.get_instance_depth(instance),
            reverse=True,
        )

        return reduce(
            lambda formula, instance_name: self._quantify_instance(ctx, instance_name)(
                formula
            ),
            sorted_instances,
            formula,
        )

    def _convert_amr_projective(
        self,
        ctx: AmrContext,
        node: Node,
        context_node: Node | None,
    ) -> Callable[[Clause | None], Clause | None]:
        instance_name, instance_info = node
        # only project instances at their specific scope
        projections_for_context = ctx.get_instances_at_scope(context_node)

        edges = instance_info[1:]
        cur_closure = lambda x: x
        if instance_name in projections_for_context:
            # handle 8.6-8.8 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x\P :RiAi)∥↑ = λp.∥(x/P :RiAi),λx.p∥↓
            cur_closure = lambda u: self._convert_amr_assertive(
                ctx, instance_name, lambda x: u
            )

        def args_closure(p: Clause | None) -> Clause | None:
            # handle 8.3-8.5 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x/P :RiAi)∥↑ = λp.∥A1∥↑(∥A2∥↑( ...∥An∥↑(p)))
            # don't need to worry about iterating over non-nodes since those are just λp.p
            result = cur_closure(p)
            for edge in self._sort_edges(edges, reverse=False):
                if type(edge[1]) is tuple:
                    sub_closure = self._convert_amr_projective(
                        ctx, edge[1], context_node
                    )
                    result = sub_closure(result)
            return result

        return args_closure

    def _convert_amr(
        self,
        ctx: AmrContext,
        node: Node,
        assertive_closure: Optional[Callable[[str], Clause]] = None,
    ) -> Clause:
        instances_to_quantify = ctx.get_instances_to_quantify_at_scope(node)
        ctx.mark_instances_quantified(instances_to_quantify)
        projective_closure = self._convert_amr_projective(ctx, node, node)
        base_formula = cast(
            Clause,
            projective_closure(
                self._convert_amr_assertive(ctx, node[0], assertive_closure)
            ),
        )
        return self._quanitfy_formula(ctx, base_formula, instances_to_quantify)

    def _maximally_project_amr(
        self, ctx: AmrContext, node: Node
    ) -> Callable[[Clause], Clause]:
        return cast(
            Callable[[Clause], Clause], self._convert_amr_projective(ctx, node, None)
        )

    def _override_is_projective(
        self, info: OverrideIsProjectiveCallbackInfo
    ) -> bool | None:
        override: bool | None = None
        if self.maximally_hoist_coreferences and info.is_coreferent:
            override = True
        if self.override_is_projective is not None:
            callback_res = self.override_is_projective(info)
            if callback_res is not None:
                override = callback_res
        return override

    def convert_amr_tree(self, amr_tree: Tree) -> Clause:
        ctx = AmrContext.from_amr_tree(
            amr_tree, override_is_projective=self._override_is_projective
        )

        # special case to handle maximally projected instances
        maximal_projection = self._maximally_project_amr(ctx, amr_tree.node)
        formula = maximal_projection(self._convert_amr(ctx, amr_tree.node))
        maximum_scope_instances = ctx.get_instances_at_scope(None)
        return self._quanitfy_formula(ctx, formula, maximum_scope_instances)

    def convert_amr_str(self, amr_str: str) -> Clause:
        return self.convert_amr_tree(penman.parse(amr_str))

    def convert(self, amr: str | Tree | Graph) -> Clause:
        if isinstance(amr, str):
            return self.convert_amr_str(amr)
        elif isinstance(amr, Tree):
            return self.convert_amr_tree(amr)
        elif isinstance(amr, Graph):
            return self.convert_amr_tree(penman.configure(amr))
        else:
            raise TypeError(
                f"Expected amr to be a string, Tree, or Graph. Got {type(amr)}"
            )


def _get_instance_name(target: Node | str, ctx: AmrContext) -> str | None:
    if type(target) is tuple:
        return target[0]
    if target in ctx.instances:
        return target
    return None
