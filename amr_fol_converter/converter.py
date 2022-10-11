from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, cast
from typing_extensions import Literal
import penman
from penman.models import amr
from penman.graph import Instance, Edge, Attribute

from amr_fol_converter.types import And, Const, Exists, Formula, Not, Predicate, Var


INITIAL_CLOSURE: Callable[[str], Literal[True]] = lambda u: True


@dataclass
class AmrContext:
    instance_lookup: dict[str, Instance]
    relations_lookup: dict[str, list[Edge]]
    attributes_lookup: dict[str, list[Attribute]]
    # instances coreferenced in multiple places in the graph
    projective_instances: frozenset[str]
    # projective instances that have already been bound earlier in the parse
    bound_instances: frozenset[str] = frozenset({})

    def bind_projective_instance(self, instance_name: str) -> AmrContext:
        """Return a new context with the given projective instance marked as bound."""
        return AmrContext(
            self.instance_lookup,
            self.relations_lookup,
            self.attributes_lookup,
            self.projective_instances - {instance_name},
            self.bound_instances | {instance_name},
        )

    def mark_instance_non_projective(self, instance_name: str) -> AmrContext:
        """Return a new context with the given instance marked as non-projective."""
        return AmrContext(
            self.instance_lookup,
            self.relations_lookup,
            self.attributes_lookup,
            self.projective_instances - {instance_name},
            self.bound_instances,
        )


def t_elim(and_terms: list[Formula | Literal[True]]) -> list[Formula]:
    """remove True terms from a list of terms to be ANDed together"""
    return [term for term in and_terms if term is not True]


def convert_amr_assertive(
    ctx: AmrContext,
    instance_name: str,
    closure: Callable[[str], Formula | Literal[True]],
) -> Formula:
    instance = ctx.instance_lookup[instance_name]
    is_projective_instance = instance_name in ctx.projective_instances
    is_already_bound = instance_name in ctx.bound_instances
    # handle 7.2, 7.6-7.8 from "Expressive Power of Abstract Meaning Representations"
    # ∥x,φ∥↓ = φ(x)
    # ∥(x\P),φ∥↓ = φ(x)
    # ∥(x\P :RiAi),φ∥↓ = φ(x)
    # ∥(x\P :RiAi :polarity–),φ∥↓ = φ(x)
    if is_projective_instance or is_already_bound:
        # I think in this case it's impossible for the Formula to equal "True"
        return cast(Formula, closure(instance_name))
    bound_var = Var(instance_name)
    polarity = True
    and_terms = [
        closure(instance_name),
        Predicate(instance.target, (bound_var,)),
    ]
    next_ctx = ctx.bind_projective_instance(instance_name)
    for attribute in ctx.attributes_lookup[instance_name]:
        # special case for the :polarity - attribute. When this is present,
        # the attribute should be removed but the entire expression should be negated
        if attribute.role == ":polarity" and attribute.target == "-":
            polarity = False
        else:
            and_terms.append(
                Predicate(attribute.role, (bound_var, Const(attribute.target)))
            )
    for edge in ctx.relations_lookup[instance_name]:
        sub_closure = lambda u: Predicate(edge.role, (bound_var, Var(u)))
        and_terms.append(convert_amr_assertive(next_ctx, edge.target, sub_closure))
    existence_expr = Exists(bound_var, body=And(tuple(t_elim(and_terms))))
    return existence_expr if polarity else Not(existence_expr)


def convert_amr_projective(
    ctx: AmrContext,
    instance_name: str,
) -> Callable[[Formula], Formula]:
    is_projective = instance_name in ctx.projective_instances
    if is_projective:
        # handle 8.6-8.8 from "Expressive Power of Abstract Meaning Representations"
        # ∥(x\P :RiAi)∥↑ = λp.∥(x/P :RiAi),λx.p∥↓
        non_projective_ctx = ctx.mark_instance_non_projective(instance_name)
        return lambda u: convert_amr_assertive(
            non_projective_ctx, instance_name, lambda x: u
        )

    def args_closure(p: Formula) -> Formula:
        # handle 8.3-8.5 from "Expressive Power of Abstract Meaning Representations"
        # ∥(x/P :RiAi)∥↑ = λp.∥A1∥↑(∥A2∥↑( ...∥An∥↑(p)))
        # don't need to worry about iterating over attributes here because
        # they only contain constant arguments
        result = p
        next_ctx = ctx
        for edge in ctx.relations_lookup[instance_name]:
            sub_closure = convert_amr_projective(next_ctx, edge.target)
            next_ctx = next_ctx.bind_projective_instance(edge.target)
            result = sub_closure(result)
        return result

    return args_closure


def select_graph_root(amr_graph: penman.Graph) -> str:
    """
    Select the root of the graph, which is the instance with no edges pointing to it.
    This is not necessarily where the `top` of the graph is if the graph contains ARGX-of edges.
    """
    instance_counts = {instance.source: 0 for instance in amr_graph.instances()}
    for edge in amr_graph.edges():
        instance_counts[edge.target] += 1
    for instance in amr_graph.instances():
        if instance_counts[instance.source] == 0:
            return instance.source
    raise ValueError("No valid root found")


def convert_amr_graph(amr_graph: penman.Graph) -> Formula:
    relations_lookup = defaultdict(list)
    attributes_lookup = defaultdict(list)
    reference_counts: dict[str, int] = defaultdict(int)
    for edge in amr_graph.edges():
        relations_lookup[edge.source].append(edge)
        reference_counts[edge.target] += 1
    for attribute in amr_graph.attributes():
        attributes_lookup[attribute.source].append(attribute)

    projective_instances = frozenset(
        [name for name, count in reference_counts.items() if count > 1]
    )
    ctx = AmrContext(
        instance_lookup={
            instance.source: instance for instance in amr_graph.instances()
        },
        relations_lookup=relations_lookup,
        attributes_lookup=attributes_lookup,
        projective_instances=projective_instances,
    )
    graph_root = select_graph_root(amr_graph)
    assertive_amr = convert_amr_assertive(ctx, graph_root, INITIAL_CLOSURE)
    projective_amr = convert_amr_projective(ctx, graph_root)
    return projective_amr(assertive_amr)


def convert_amr_str(amr_str: str) -> Formula:
    return convert_amr_graph(penman.decode(amr_str, model=amr.model))
