from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, cast
from typing_extensions import Literal
import penman
from penman.models import amr
from penman.tree import Tree, Node
from penman.graph import Graph

from amr_logic_converter.types import (
    And,
    Const,
    ConstType,
    Exists,
    Formula,
    Not,
    Predicate,
    Param,
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
    projective_instances: frozenset[str]

    def mark_instance_non_projective(self, instance_name: str) -> AmrContext:
        """Return a new context with the given instance marked as non-projective."""
        return AmrContext(
            self.instances,
            self.projective_instances - {instance_name},
        )


def t_elim(and_terms: list[Formula | Literal[True]]) -> list[Formula]:
    """remove True terms from a list of terms to be ANDed together"""
    return [term for term in and_terms if term is not True]


def determine_const_type(value: str) -> ConstType:
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

    def __init__(
        self,
        invert_relations: bool = True,
        existentially_quantify_instances: bool = False,
    ) -> None:
        self.invert_relations = invert_relations
        self.existentially_quantify_instances = existentially_quantify_instances

    def _convert_amr_assertive(
        self,
        ctx: AmrContext,
        node: Node,
        closure: Callable[[str], Formula | Literal[True]],
    ) -> Formula:
        instance_name, instance_info = node
        instance_predicate, *edges = instance_info
        is_projective_instance = instance_name in ctx.projective_instances
        # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥x,φ∥↓ = φ(x)
        # ∥(x\P),φ∥↓ = φ(x)
        # ∥(x\P :RiAi),φ∥↓ = φ(x)
        # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
        if is_projective_instance:
            # I think in this case it's impossible for the Formula to equal "True"
            return cast(Formula, closure(instance_name))
        bound_instance: Param | Const = (
            Param(instance_name)
            if self.existentially_quantify_instances
            else Const(instance_name, "instance")
        )
        polarity = True
        and_terms = [
            closure(instance_name),
            Predicate(instance_predicate[1], (bound_instance,)),
        ]

        for role, target in edges:

            def sub_closure(u: str) -> Predicate:
                target: Param | Const = (
                    Param(u)
                    if self.existentially_quantify_instances
                    else Const(u, "instance")
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
                and_terms.append(self._convert_amr_assertive(ctx, target, sub_closure))
            elif target in ctx.instances:
                and_terms.append(sub_closure(target))
            else:
                predicate = Predicate(
                    role, (bound_instance, Const(target, determine_const_type(target)))
                )
                and_terms.append(
                    normalize_predicate(predicate)
                    if self.invert_relations
                    else predicate
                )
        expr: Formula = And(tuple(t_elim(and_terms)))
        if self.existentially_quantify_instances:
            expr = Exists(cast(Param, bound_instance), body=expr)
        return expr if polarity else Not(expr)

    def _convert_amr_projective(
        self,
        ctx: AmrContext,
        node: Node,
    ) -> Callable[[Formula], Formula]:
        instance_name, instance_info = node
        edges = instance_info[1:]
        is_projective = instance_name in ctx.projective_instances
        if is_projective:
            # handle 8.6-8.8 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x\P :RiAi)∥↑ = λp.∥(x/P :RiAi),λx.p∥↓
            non_projective_ctx = ctx.mark_instance_non_projective(instance_name)
            return lambda u: self._convert_amr_assertive(
                non_projective_ctx, node, lambda x: u
            )

        def args_closure(p: Formula) -> Formula:
            # handle 8.3-8.5 from "Expressive Power of Abstract Meaning Representations"
            # ∥(x/P :RiAi)∥↑ = λp.∥A1∥↑(∥A2∥↑( ...∥An∥↑(p)))
            # don't need to worry about iterating over non-nodes since those are just λp.p
            result = p
            for edge in edges:
                if type(edge[1]) is tuple:
                    sub_closure = self._convert_amr_projective(ctx, edge[1])
                    result = sub_closure(result)
            return result

        return args_closure

    def convert_amr_tree(self, amr_tree: Tree) -> Formula:
        amr_graph = penman.interpret(amr_tree, model=amr.model)
        instances = set()
        reference_counts: dict[str, int] = defaultdict(int)
        for edge in amr_graph.edges():
            instances.add(edge.source)
            reference_counts[edge.target] += 1

        projective_instances = frozenset(
            [name for name, count in reference_counts.items() if count > 1]
        )
        ctx = AmrContext(
            instances=frozenset(instances),
            projective_instances=projective_instances,
        )
        assertive_amr = self._convert_amr_assertive(ctx, amr_tree.node, INITIAL_CLOSURE)
        projective_amr = self._convert_amr_projective(ctx, amr_tree.node)
        return projective_amr(assertive_amr)

    def convert_amr_str(self, amr_str: str) -> Formula:
        return self.convert_amr_tree(penman.parse(amr_str))

    def convert(self, amr: str | Tree | Graph) -> Formula:
        if type(amr) is str:
            return self.convert_amr_str(amr)
        elif type(amr) is Tree:
            return self.convert_amr_tree(amr)
        elif type(amr) is Graph:
            return self.convert_amr_tree(penman.configure(amr))
        else:
            raise TypeError(
                f"Expected amr to be a string, Tree, or Graph. Got {type(amr)}"
            )
