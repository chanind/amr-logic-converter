from __future__ import annotations

from penman.tree import Node, Tree


def extract_instances_from_amr_tree(amr_tree: Tree) -> frozenset[str]:
    """Extract the set of instances in the given AMR tree."""
    instances: set[str] = set()
    _extract_instances_inplace(amr_tree.node, instances)
    return frozenset(instances)


def _extract_instances_inplace(node: Node, instances: set[str]) -> None:
    """Find the corresponding best tree node for each instance, updating the reference_counts inplace"""
    instance, instance_info = node
    predicate_branch, *edges = instance_info
    if predicate_branch[0] == "/" and len(predicate_branch) == 2:
        instances.add(instance)

    for role, target in edges:
        if isinstance(target, tuple):
            _extract_instances_inplace(target, instances)
