from __future__ import annotations

from penman.tree import Node, Tree


def map_contained_coreferences(
    tree: Tree, instances: frozenset[str]
) -> dict[str, frozenset[str]]:
    """Find which instances are references within the definition of each given instance"""
    mutable_contained_coreferences_map: dict[str, set[str]] = {
        instance: set() for instance in instances
    }
    _map_instances_to_contained_corefences_inplace(
        tree.node, instances, mutable_contained_coreferences_map
    )
    return {k: frozenset(v) for k, v in mutable_contained_coreferences_map.items()}


def _map_instances_to_contained_corefences_inplace(
    node: Node,
    instances: frozenset[str],
    mutable_contained_coreferences_map: dict[str, set[str]],
    ancestor_instances: frozenset[str] = frozenset(),
) -> None:
    """Find all ancestors of all instances in the given AMR tree."""
    instance, instance_info = node
    _predicate, *edges = instance_info

    if instance in instances:
        for ancestor in ancestor_instances:
            mutable_contained_coreferences_map[ancestor].add(instance)

    next_ancestors = ancestor_instances | {instance}
    for i, (role, target) in enumerate(edges):
        if isinstance(target, tuple):
            _map_instances_to_contained_corefences_inplace(
                target, instances, mutable_contained_coreferences_map, next_ancestors
            )
        elif target in instances:
            _map_instances_to_contained_corefences_inplace(
                (target, ("",)),
                instances,
                mutable_contained_coreferences_map,
                next_ancestors,
            )
