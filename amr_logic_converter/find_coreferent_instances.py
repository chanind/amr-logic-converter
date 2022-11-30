from __future__ import annotations
from collections import defaultdict

from penman.tree import Node, Tree


def find_coreferent_instances(tree: Tree, instances: frozenset[str]) -> frozenset[str]:
    """Find which of the instances provided are projective (co-referenced in multiple places in the tree)"""
    reference_counts: dict[str, int] = defaultdict(int)
    _count_instance_references_inplace(tree.node, instances, reference_counts)
    return frozenset(
        instance for instance, count in reference_counts.items() if count > 1
    )


def _count_instance_references_inplace(
    node: Node, instances: frozenset[str], reference_counts: dict[str, int]
) -> None:
    """Find the corresponding best tree node for each instance, updating the reference_counts inplace"""
    instance, instance_info = node
    _predicate, *edges = instance_info
    reference_counts[instance] += 1
    for _role, target in edges:
        if isinstance(target, tuple):
            _count_instance_references_inplace(target, instances, reference_counts)
        elif target in instances:
            _count_instance_references_inplace(
                (target, ("",)), instances, reference_counts
            )
