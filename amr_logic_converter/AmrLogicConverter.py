from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, cast
from typing_extensions import Literal
import penman
from penman.tree import Tree, Node
from penman.graph import Graph
from amr_logic_converter.find_coreferent_instances import find_coreferent_instances
from amr_logic_converter.map_instances_lca import map_instances_lca
from amr_logic_converter.map_instances_to_nodes import map_instances_to_nodes

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
from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)

INITIAL_CLOSURE: Callable[[str], Literal[True]] = lambda u: True


def normalize_predicate(predicate: Predicate) -> Predicate:
    # flip :ARGX-of(x,y) to :ARGX(y,x)
    if (
        type(predicate.value) is str
        and predicate.value.endswith("-of")
        and len(predicate.args) == 2
    ):
        return Predicate(predicate.value[:-3], (predicate.args[1], predicate.args[0]))
    return predicate


@dataclass
class AmrContext:
    instances: frozenset[str]
    # instances coreferenced in multiple places in the graph
    lca_instances_map: dict[str | None, list[str]]
    instance_node_map: dict[str, Node]

    # bound instances
    bound_instances: frozenset[str] = field(default_factory=frozenset)
    non_projective_instances: frozenset[str] = field(default_factory=frozenset)

    def mark_instance_non_projective(self, instance_name: str) -> AmrContext:
        """Return a new context with the given instance marked as non-projective."""
        return AmrContext(
            self.instances,
            self.lca_instances_map,
            self.instance_node_map,
            self.bound_instances,
            self.non_projective_instances | {instance_name},
        )

    def mark_instance_bound(self, instance_name: str) -> AmrContext:
        """Return a new context with the given instance marked as bound."""
        return AmrContext(
            self.instances,
            self.lca_instances_map,
            self.instance_node_map,
            self.bound_instances | {instance_name},
            self.non_projective_instances,
        )

    def is_instance_projective(self, instance_name: str) -> bool:
        return instance_name not in self.non_projective_instances

    def is_instance_bound(self, instance_name: str) -> bool:
        return instance_name in self.bound_instances


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

    def __init__(
        self,
        invert_relations: bool = True,
        existentially_quantify_instances: bool = False,
        use_variables_for_instances: bool = False,
        maximally_hoist_coreferences: bool = False,
    ) -> None:
        self.invert_relations = invert_relations
        self.existentially_quantify_instances = existentially_quantify_instances
        self.use_variables_for_instances = use_variables_for_instances
        self.maximally_hoist_coreferences = maximally_hoist_coreferences

    def _convert_amr_assertive(
        self,
        ctx: AmrContext,
        node: Node,
        closure: Optional[Callable[[str], Formula | None]] = None,
    ) -> Formula | None:
        instance_name, instance_info = node
        instance_predicate, *edges = instance_info
        is_projective_instance = ctx.is_instance_projective(instance_name)
        is_bound_instance = ctx.is_instance_bound(instance_name)
        use_variables_for_instances = (
            self.existentially_quantify_instances or self.use_variables_for_instances
        )
        # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥x,φ∥↓ = φ(x)
        # ∥(x\P),φ∥↓ = φ(x)
        # ∥(x\P :RiAi),φ∥↓ = φ(x)
        # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
        if is_projective_instance or is_bound_instance:
            return None if closure is None else closure(instance_name)
        bound_instance: Variable | Constant = (
            Variable(instance_name)
            if use_variables_for_instances
            else Constant(instance_name, "instance")
        )
        next_ctx = ctx.mark_instance_bound(instance_name)
        polarity = True

        predicate_term = Predicate(instance_predicate[1], (bound_instance,))
        closure_term = closure(instance_name) if closure is not None else None
        sub_terms: list[Formula] = []

        for role, target in edges:

            def sub_closure(u: str) -> Predicate:
                target: Variable | Constant = (
                    Variable(u)
                    if use_variables_for_instances
                    else Constant(u, "instance")
                )
                predicate = Predicate(role, (bound_instance, target))
                return (
                    normalize_predicate(predicate)
                    if self.invert_relations
                    else predicate
                )

            # special case for the :polarity - attribute. When this is present,
            # the attribute should be removed but the entire expression should be negated
            if role == ":polarity" and target == "-":
                polarity = False
            elif type(target) is tuple:
                sub_terms.append(self._convert_amr(next_ctx, target, sub_closure))
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
        expr: Formula = And(tuple(pre_terms + sub_terms))
        if self.existentially_quantify_instances:
            expr = Exists(cast(Variable, bound_instance), body=expr)
        return expr if polarity else Not(expr)

    def _convert_amr_projective(
        self,
        ctx: AmrContext,
        node: Node,
        context_node: Node | None,
    ) -> Callable[[Formula | None], Formula | None]:
        instance_name, instance_info = node
        # only project instances at their lca level
        # context_node = None means project maximally above everything else
        context_instance_name = context_node[0] if context_node is not None else None
        projections_for_context = ctx.lca_instances_map[context_instance_name]

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
        return cast(
            Formula,
            projective_closure(
                self._convert_amr_assertive(ctx, node, assertive_closure)
            ),
        )

    def _maximally_project_amr(
        self, ctx: AmrContext, node: Node
    ) -> Callable[[Formula], Formula]:
        return cast(
            Callable[[Formula], Formula], self._convert_amr_projective(ctx, node, None)
        )

    def convert_amr_tree(self, amr_tree: Tree) -> Formula:
        instances = extract_instances_from_amr_tree(amr_tree)
        coreferent_instances = find_coreferent_instances(amr_tree, instances)
        instance_node_map = map_instances_to_nodes(amr_tree, instances)
        instance_lca_map: Mapping[str, str | None] = map_instances_lca(
            amr_tree, instances
        )
        if self.maximally_hoist_coreferences:
            instance_lca_map = {
                instance: (None if instance in coreferent_instances else lca)
                for instance, lca in instance_lca_map.items()
            }
        lca_instances_map: dict[str | None, list[str]] = defaultdict(list)
        for instance, lca in instance_lca_map.items():
            lca_instances_map[lca].append(instance)
        ctx = AmrContext(
            instances=instances,
            instance_node_map=instance_node_map,
            lca_instances_map=lca_instances_map,
        )
        maximal_projection = self._maximally_project_amr(ctx, amr_tree.node)
        return maximal_projection(self._convert_amr(ctx, amr_tree.node))

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
