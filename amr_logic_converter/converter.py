from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, cast
from typing_extensions import Literal
import penman
from penman.models import amr
from penman.tree import Tree, Node

from amr_logic_converter.types import And, Const, Exists, Formula, Not, Predicate, Var


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


def convert_amr_assertive(
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
    bound_var = Var(instance_name)
    polarity = True
    and_terms = [
        closure(instance_name),
        Predicate(instance_predicate[1], (bound_var,)),
    ]

    for role, target in edges:
        sub_closure = lambda u: normalize_predicate(
            Predicate(role, (bound_var, Var(u)))
        )
        # special case for the :polarity - attribute. When this is present,
        # the attribute should be removed but the entire expression should be negated
        if role == ":polarity" and target == "-":
            polarity = False
        elif type(target) is tuple:
            and_terms.append(convert_amr_assertive(ctx, target, sub_closure))
        elif target in ctx.instances:
            and_terms.append(sub_closure(target))
        else:
            and_terms.append(
                normalize_predicate(Predicate(role, (bound_var, Const(target))))
            )
    existence_expr = Exists(bound_var, body=And(tuple(t_elim(and_terms))))
    return existence_expr if polarity else Not(existence_expr)


def convert_amr_projective(
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
        return lambda u: convert_amr_assertive(non_projective_ctx, node, lambda x: u)

    def args_closure(p: Formula) -> Formula:
        # handle 8.3-8.5 from "Expressive Power of Abstract Meaning Representations"
        # ∥(x/P :RiAi)∥↑ = λp.∥A1∥↑(∥A2∥↑( ...∥An∥↑(p)))
        # don't need to worry about iterating over non-nodes since those are just λp.p
        result = p
        for edge in edges:
            if type(edge[1]) is tuple:
                sub_closure = convert_amr_projective(ctx, edge[1])
                result = sub_closure(result)
        return result

    return args_closure


def convert_amr_tree(amr_tree: Tree) -> Formula:
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
    assertive_amr = convert_amr_assertive(ctx, amr_tree.node, INITIAL_CLOSURE)
    projective_amr = convert_amr_projective(ctx, amr_tree.node)
    return projective_amr(assertive_amr)


def convert_amr_str(amr_str: str) -> Formula:
    return convert_amr_tree(penman.parse(amr_str))
