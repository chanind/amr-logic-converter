from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable
from typing_extensions import Literal
import penman
from penman.models import amr
from penman.graph import Instance, Edge, Attribute

from amr_fol_converter.types import And, Const, Exists, Formula, Predicate, Var


INITIAL_CLOSURE: Callable[[str], Literal[True]] = lambda u: True


@dataclass
class AmrContext:
    instance_lookup: dict[str, Instance]
    relations_lookup: dict[str, list[Edge]]
    attributes_lookup: dict[str, list[Attribute]]


def t_elim(and_terms: list[Formula | Literal[True]]) -> list[Formula]:
    """
    remove True terms from a list of terms to be ANDed together
    """
    return [term for term in and_terms if term is not True]


def convert_amr_recursive(
    ctx: AmrContext,
    instance_name: str,
    closure: Callable[[str], Formula | Literal[True]],
) -> Formula:
    instance = ctx.instance_lookup[instance_name]
    bound_var = Var(instance_name)
    and_terms = [
        closure(instance_name),
        Predicate(instance.target, (bound_var,)),
    ]
    for attribute in ctx.attributes_lookup[instance_name]:
        and_terms.append(
            Predicate(attribute.role, (bound_var, Const(attribute.target)))
        )
    for edge in ctx.relations_lookup[instance_name]:
        sub_closure = lambda u: Predicate(edge.role, (bound_var, Var(u)))
        and_terms.append(convert_amr_recursive(ctx, edge.target, sub_closure))
    return Exists(bound_var, body=And(tuple(t_elim(and_terms))))


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
    for edge in amr_graph.edges():
        relations_lookup[edge.source].append(edge)
    for attribute in amr_graph.attributes():
        attributes_lookup[attribute.source].append(attribute)
    ctx = AmrContext(
        instance_lookup={
            instance.source: instance for instance in amr_graph.instances()
        },
        relations_lookup=relations_lookup,
        attributes_lookup=attributes_lookup,
    )
    return convert_amr_recursive(ctx, select_graph_root(amr_graph), INITIAL_CLOSURE)


def convert_amr_str(amr_str: str) -> Formula:
    return convert_amr_graph(penman.decode(amr_str, model=amr.model))
