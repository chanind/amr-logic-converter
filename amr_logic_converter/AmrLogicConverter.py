from __future__ import annotations
from dataclasses import dataclass

from functools import reduce
from typing import Callable, Optional, Union, cast
from typing_extensions import Literal

import penman
from penman.tree import Tree, Node
from penman.graph import Graph

from amr_logic_converter.AmrContext import (
    AmrContext,
    OverrideInstanceScopeCallback,
    OverrideInstanceScopeCallbackMeta,
)
from amr_logic_converter.types import (
    And,
    Constant,
    ConstantType,
    Exists,
    Formula,
    Not,
    Predicate,
    Variable,
)


@dataclass
class OverrideQuantificationCallbackMeta:
    """Metadata passed to the OverrideQuantificationCallback wtih info about the node being processed"""

    instance_name: str
    bound_instance: Variable | Constant
    node: Node
    amr_tree: Tree
    is_negated: bool


OverrideQuantificationCallback = Callable[
    [Formula, OverrideQuantificationCallbackMeta], Union[Formula, None]
]


def normalize_predicate(predicate: Predicate) -> Predicate:
    # flip :ARGX-of(x,y) to :ARGX(y,x)
    if (
        type(predicate.value) is str
        and predicate.value.endswith("-of")
        and len(predicate.args) == 2
    ):
        return Predicate(predicate.value[:-3], (predicate.args[1], predicate.args[0]))
    return predicate


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
    override_instance_scope: Optional[OverrideInstanceScopeCallback]
    override_quantification: Optional[OverrideQuantificationCallback]

    def __init__(
        self,
        invert_relations: bool = True,
        existentially_quantify_instances: bool = False,
        use_variables_for_instances: bool = False,
        maximally_hoist_coreferences: bool = False,
        capitalize_variables: bool = True,
        override_instance_scope: Optional[OverrideInstanceScopeCallback] = None,
        override_quantification: Optional[OverrideQuantificationCallback] = None,
    ) -> None:
        self.invert_relations = invert_relations
        self.capitalize_variables = capitalize_variables
        self.existentially_quantify_instances = existentially_quantify_instances
        self.use_variables_for_instances = use_variables_for_instances
        self.maximally_hoist_coreferences = maximally_hoist_coreferences
        self.override_instance_scope = override_instance_scope
        self.override_quantification = override_quantification

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
        closure: Optional[Callable[[str], Formula | None]] = None,
    ) -> Formula | None:
        instance_name, instance_info = node
        instance_predicate, *edges = instance_info
        is_projective_instance = ctx.is_instance_projective(instance_name)
        # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥x,φ∥↓ = φ(x)
        # ∥(x\P),φ∥↓ = φ(x)
        # ∥(x\P :RiAi),φ∥↓ = φ(x)
        # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
        if is_projective_instance:
            return None if closure is None else closure(instance_name)
        bound_instance = self._get_bound_instance(instance_name)

        predicate_term = Predicate(instance_predicate[1], (bound_instance,))
        closure_term = closure(instance_name) if closure is not None else None
        sub_terms: list[Formula] = []

        for role, target in edges:

            def sub_closure(u: str) -> Predicate:
                target: Variable | Constant = self._get_bound_instance(u)
                predicate = Predicate(role, (bound_instance, target))
                return (
                    normalize_predicate(predicate)
                    if self.invert_relations
                    else predicate
                )

            # special case for the :polarity - attribute. When this is present,
            # the attribute should be removed but the entire expression should be negated
            if role == ":polarity" and target == "-":
                continue
            elif type(target) is tuple:
                sub_terms.append(self._convert_amr(ctx, target, sub_closure))
            elif target in ctx.instances:
                sub_terms.append(sub_closure(target))
            else:
                predicate = Predicate(
                    role,
                    (bound_instance, Constant(target, determine_const_type(target))),
                )
                sub_terms.append(
                    normalize_predicate(predicate)
                    if self.invert_relations
                    else predicate
                )

        pre_terms = []
        if closure_term is not None:
            pre_terms.append(closure_term)
        pre_terms.append(predicate_term)
        return And(tuple(pre_terms + sub_terms))

    def _quantify_instance(
        self,
        ctx: AmrContext,
        instance_name: str,
    ) -> Callable[[Formula], Formula]:
        node = ctx.get_node_for_instance(instance_name)
        _instance_predicate, *edges = node[1]
        bound_instance = self._get_bound_instance(instance_name)
        polarity = True
        for role, target in edges:
            if role == ":polarity" and target == "-":
                polarity = False

        def quantification_closure(clause: Formula) -> Formula:
            if self.override_quantification is not None:
                override_expr = self.override_quantification(
                    clause,
                    OverrideQuantificationCallbackMeta(
                        node=node,
                        instance_name=instance_name,
                        bound_instance=bound_instance,
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
        self, ctx: AmrContext, formula: Formula, instances: list[str]
    ) -> Formula:
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
    ) -> Callable[[Formula | None], Formula | None]:
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

        def args_closure(p: Formula | None) -> Formula | None:
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
        assertive_closure: Optional[Callable[[str], Formula]] = None,
    ) -> Formula:
        projective_closure = self._convert_amr_projective(ctx, node, node)
        instances_to_quantify = ctx.get_instances_at_node_scope(node)
        base_formula = cast(
            Formula,
            projective_closure(
                self._convert_amr_assertive(ctx, node, assertive_closure)
            ),
        )
        return self._quanitfy_formula(ctx, base_formula, instances_to_quantify)

    def _maximally_project_amr(
        self, ctx: AmrContext, node: Node
    ) -> Callable[[Formula], Formula]:
        return cast(
            Callable[[Formula], Formula], self._convert_amr_projective(ctx, node, None)
        )

    def _override_scope_callback(
        self, meta: OverrideInstanceScopeCallbackMeta
    ) -> Literal["wide", "default"] | None:
        override: Literal["wide", "default"] | None = None
        if self.maximally_hoist_coreferences and meta.is_coreferent:
            override = "wide"
        if (
            self.override_instance_scope
            and self.override_instance_scope(meta) == "wide"
        ):
            override = "wide"
        return override

    def convert_amr_tree(self, amr_tree: Tree) -> Formula:
        ctx = AmrContext.from_amr_tree(
            amr_tree, override_instance_scope=self._override_scope_callback
        )

        # special case to handle maximally projected instances
        maximal_projection = self._maximally_project_amr(ctx, amr_tree.node)
        formula = maximal_projection(self._convert_amr(ctx, amr_tree.node))
        maximum_scope_instances = ctx.get_instances_at_node_scope(None)
        return self._quanitfy_formula(ctx, formula, maximum_scope_instances)

    def convert_amr_str(self, amr_str: str) -> Formula:
        return self.convert_amr_tree(penman.parse(amr_str))

    def convert(self, amr: str | Tree | Graph) -> Formula:
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
