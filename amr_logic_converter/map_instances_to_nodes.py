from __future__ import annotations

from penman.tree import Node, Tree


def map_instances_to_nodes(tree: Tree, instances: frozenset[str]) -> dict[str, Node]:
    """Find the corresponding best tree node for each instance"""
    instance_node_mapping: dict[str, Node] = {}
    _map_instances_to_nodes_inplace(tree.node, instances, instance_node_mapping)
    return instance_node_mapping


def _map_instances_to_nodes_inplace(
    node: Node, instances: frozenset[str], instance_node_mapping: dict[str, Node]
) -> None:
    """Find the corresponding best tree node for each instance, updating the instance_node_mapping inplace"""
    instance, instance_info = node
    _predicate, *edges = instance_info
    if instance not in instance_node_mapping:
        instance_node_mapping[instance] = node
    for _role, target in edges:
        if isinstance(target, tuple):
            _map_instances_to_nodes_inplace(target, instances, instance_node_mapping)
        elif target in instances:
            _map_instances_to_nodes_inplace(
                (target, ("",)), instances, instance_node_mapping
            )
