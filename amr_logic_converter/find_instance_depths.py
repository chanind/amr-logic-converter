from __future__ import annotations
from collections import defaultdict

from penman.tree import Node, Tree


def find_instance_depths(tree: Tree, instances: frozenset[str]) -> dict[str, int]:
    """Return a map of instance to their lowest depth in the tree"""
    depths: dict[str, int] = defaultdict(int)
    _find_instance_depths_inplace(tree.node, instances, depths)
    return depths


def _find_instance_depths_inplace(
    node: Node, instances: frozenset[str], depths: dict[str, int], depth: int = 0
) -> None:
    """Find the corresponding best tree node for each instance, updating the reference_counts inplace"""
    instance, instance_info = node
    _predicate, *edges = instance_info
    if instance not in depths or depth < depths[instance]:
        depths[instance] = depth
    for _role, target in edges:
        if isinstance(target, tuple):
            _find_instance_depths_inplace(target, instances, depths, depth + 1)
        elif target in instances:
            _find_instance_depths_inplace((target, ("",)), instances, depths, depth + 1)
