from __future__ import annotations

from penman.tree import Node, Tree


def map_instances_lca(tree: Tree, instances: frozenset[str]) -> dict[str, str]:
    """Find the lowest common ancestor of all instances in the given AMR tree."""
    ancestors_by_instance = _map_instances_to_common_ancestors(
        tree.node, None, instances, frozenset()
    )
    return {
        instance: max(ancestors, key=lambda a: a[0])[2]
        for instance, ancestors in ancestors_by_instance.items()
    }


def _map_instances_to_common_ancestors(
    node: Node,
    prefix: str | None,
    instances: frozenset[str],
    ancestors: frozenset[tuple[int, str | None, str]] = frozenset(),
) -> dict[str, frozenset[tuple[int, str | None, str]]]:
    """Find all ancestors of all instances in the given AMR tree."""
    instance, instance_info = node
    _predicate, *edges = instance_info
    depth = len(ancestors)
    cur_ancestors = ancestors | {(depth, prefix, instance)}
    ancestors_by_instance: dict[str, frozenset[tuple[int, str | None, str]]] = {}
    ancestors_by_instance[instance] = cur_ancestors
    for i, (role, target) in enumerate(edges):
        subprefix = f"{role}_{i}"
        submap: dict[str, frozenset[tuple[int, str | None, str]]] = {}
        if isinstance(target, tuple):
            submap = _map_instances_to_common_ancestors(
                target, subprefix, instances, cur_ancestors
            )
        elif target in instances:
            submap = _map_instances_to_common_ancestors(
                (target, ("",)), subprefix, instances, cur_ancestors
            )
        else:
            continue
        for subinstance, subancestors in submap.items():
            if subinstance in ancestors_by_instance:
                ancestors_by_instance[subinstance] &= subancestors
            else:
                ancestors_by_instance[subinstance] = subancestors
    return ancestors_by_instance
