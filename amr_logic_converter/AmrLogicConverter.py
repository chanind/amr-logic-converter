from __future__ import annotations
from dataclasses import dataclass

from functools import reduce
from typing import Callable, Optional, Union, cast

import penman
from penman.tree import Tree, Node
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
        override_is_projective: Optional[OverrideIsProjectiveCallback] = None,
        override_quantification: Optional[OverrideQuantificationCallback] = None,
        override_conjunction: Optional[OverrideConjunctionCallback] = None,
    ) -> None:
        self.invert_relations = invert_relations
        self.capitalize_variables = capitalize_variables
        self.existentially_quantify_instances = existentially_quantify_instances
        self.use_variables_for_instances = use_variables_for_instances
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

    def _var_name(self, name: str) -> str:
        return name.capitalize() if self.capitalize_variables else name

    def _convert_amr_assertive(
        self,
        ctx: AmrContext,
        node: Node,
        closure: Optional[Callable[[str], Clause | None]] = None,
    ) -> Clause | None:
        # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥x,φ∥↓ = φ(x)
        # ∥(x\P),φ∥↓ = φ(x)
        # ∥(x\P :RiAi),φ∥↓ = φ(x)
        # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
        instance_name, instance_info = node
        instance_predicate, *edges = instance_info
        is_projective_instance = ctx.is_instance_projective(instance_name)
        if is_projective_instance:
            return None if closure is None else closure(instance_name)
        bound_instance = self._get_bound_instance(instance_name)
        predicate = Predicate.from_amr_str(instance_predicate[1])
        predicate_term = predicate(bound_instance)
        closure_term = closure(instance_name) if closure is not None else None
        sub_terms: list[Clause] = []

        for role, target in edges:

            def sub_closure(u: str) -> Atom:
                target: Variable | Constant = self._get_bound_instance(u)
                sub_predicate = Predicate.from_amr_str(role)
                atom = sub_predicate(bound_instance, target)
                return normalize_atom(atom) if self.invert_relations else atom

            # special case for the :polarity - attribute.
            # skip polarity as is handled in quantification
            if role == ":polarity" and target == "-":
                continue
            elif type(target) is tuple:
                sub_terms.append(self._convert_amr(ctx, target, sub_closure))
            elif target in ctx.instances:
                sub_terms.append(sub_closure(target))
            else:
                sub_predicate = Predicate.from_amr_str(role)
                sub_atom = sub_predicate(
                    bound_instance, Constant(target, determine_const_type(target))
                )
                sub_terms.append(
                    normalize_atom(sub_atom) if self.invert_relations else sub_atom
                )

        if self.override_conjunction is not None:
            info = OverrideConjunctionCallbackInfo(
                predicate_term=predicate_term,
                closure_term=closure_term,
                subterms=sub_terms,
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
        pre_terms.append(predicate_term)
        return And(*(pre_terms + sub_terms))

    def _quantify_instance(
        self,
        ctx: AmrContext,
        instance_name: str,
    ) -> Callable[[Clause], Clause]:
        node = ctx.get_node_for_instance(instance_name)
        _instance_predicate, *edges = node[1]
        bound_instance = self._get_bound_instance(instance_name)
        polarity = True
        for role, target in edges:
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
        self, ctx: AmrContext, formula: Clause, instances: list[str]
    ) -> Clause:
        """Wrap the formula in quantifiers for all instances in the list"""
        sorted_instances = sorted(
            instances,
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
        projections_for_context = ctx.get_instances_at_node_scope(context_node)

        edges = instance_info[1:]
        is_projective = ctx.is_instance_projective(instance_name)
        cur_closure = lambda x: x
        if is_projective and instance_name in projections_for_context:
            # handle 8.6-8.8 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x\P :RiAi)∥↑ = λp.∥(x/P :RiAi),λx.p∥↓
            non_projective_ctx = ctx.mark_instance_non_projective(instance_name)
            cur_closure = lambda u: self._convert_amr_assertive(
                non_projective_ctx, node, lambda x: u
            )

        def args_closure(p: Clause | None) -> Clause | None:
            # handle 8.3-8.5 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x/P :RiAi)∥↑ = λp.∥A1∥↑(∥A2∥↑( ...∥An∥↑(p)))
            # don't need to worry about iterating over non-nodes since those are just λp.p
            result = p
            for edge in edges:
                if type(edge[1]) is tuple:
                    sub_closure = self._convert_amr_projective(
                        ctx, edge[1], context_node
                    )
                    result = sub_closure(result)
            return cur_closure(result)

        return args_closure

    def _convert_amr(
        self,
        ctx: AmrContext,
        node: Node,
        assertive_closure: Optional[Callable[[str], Clause]] = None,
    ) -> Clause:
        projective_closure = self._convert_amr_projective(ctx, node, node)
        instances_to_quantify = ctx.get_instances_at_node_scope(node)
        base_formula = cast(
            Clause,
            projective_closure(
                self._convert_amr_assertive(ctx, node, assertive_closure)
            ),
        )
        return self._quanitfy_formula(ctx, base_formula, instances_to_quantify)

    def _maximally_project_amr(
        self, ctx: AmrContext, node: Node
    ) -> Callable[[Clause], Clause]:
        return cast(
            Callable[[Clause], Clause], self._convert_amr_projective(ctx, node, None)
        )

    def _override_scope_callback(
        self, info: OverrideIsProjectiveCallbackInfo
    ) -> bool | None:
        override: bool | None = None
        if self.maximally_hoist_coreferences and info.is_coreferent:
            override = True
        if self.override_is_projective is not None:
            override_res = self.override_is_projective(info)
            if override_res is True:
                override = True
            # setting False should override maximally_hoist_coreferences
            elif override_res is False:
                override = None
        return override

    def convert_amr_tree(self, amr_tree: Tree) -> Clause:
        ctx = AmrContext.from_amr_tree(
            amr_tree, override_is_projective=self._override_scope_callback
        )

        # special case to handle maximally projected instances
        maximal_projection = self._maximally_project_amr(ctx, amr_tree.node)
        formula = maximal_projection(self._convert_amr(ctx, amr_tree.node))
        maximum_scope_instances = ctx.get_instances_at_node_scope(None)
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
