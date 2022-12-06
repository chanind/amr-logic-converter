from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from penman.tree import Node, Tree

from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)
from amr_logic_converter.find_instance_depths import find_instance_depths
from amr_logic_converter.find_coreferent_instances import find_coreferent_instances
from amr_logic_converter.map_contained_coreferences import map_contained_coreferences
from amr_logic_converter.map_instances_lca import map_instances_lca
from amr_logic_converter.map_instances_to_nodes import map_instances_to_nodes


@dataclass
class OverrideIsProjectiveCallbackInfo:
    """Metadata passed to the OverrideIsProjectiveCallback wtih info about the node being processed"""

    amr_tree: Tree
    instance_name: str
    node: Node
    depth: int
    is_coreferent: bool
    is_default_hoisted: bool


OverrideIsProjectiveCallback = Callable[
    [OverrideIsProjectiveCallbackInfo], Optional[bool]
]


@dataclass
class AmrContext:
    """
    Helper class to keep track of relevant information about the AMR tree being processed.
    """

    amr_tree: Tree
    instances: frozenset[str]
    coreferent_instances: frozenset[str]
    instance_node_map: dict[str, Node]
    instance_depths_map: dict[str, int]
    # a map of which instances are corefereneced within the AMR defining a given instance
    contained_coreferences_map: dict[str, frozenset[str]]
    # a map of the scope (instance name of the node in the tree this variable should be scoped) to a list of instances
    # `None` as the scope means the instance should be scoped around the entire tree
    scope_instance_map: dict[str | None, set[str]]
    rendered_instances: set[str] = field(default_factory=set)
    quantified_instances: set[str] = field(default_factory=set)

    @classmethod
    def from_amr_tree(
        cls,
        amr_tree: Tree,
        override_is_projective: Optional[OverrideIsProjectiveCallback] = None,
    ) -> AmrContext:
        instances = extract_instances_from_amr_tree(amr_tree)
        coreferent_instances = find_coreferent_instances(amr_tree, instances)
        instance_node_map = map_instances_to_nodes(amr_tree, instances)
        instance_depths_map = find_instance_depths(amr_tree, instances)
        instance_lca_map = map_instances_lca(amr_tree, instances)
        contained_coreferences_map = map_contained_coreferences(amr_tree, instances)
        scope_instance_map = _build_scope_instance_map(
            amr_tree=amr_tree,
            instance_lca_map=instance_lca_map,
            instance_depths_map=instance_depths_map,
            instance_node_map=instance_node_map,
            coreferent_instances=coreferent_instances,
            override_is_projective_callback=override_is_projective,
        )
        return cls(
            amr_tree=amr_tree,
            instances=instances,
            coreferent_instances=coreferent_instances,
            instance_node_map=instance_node_map,
            instance_depths_map=instance_depths_map,
            scope_instance_map=scope_instance_map,
            contained_coreferences_map=contained_coreferences_map,
        )

    def mark_instance_rendered(self, instance_name: str) -> None:
        """Mark the instance as rendered in-place."""
        self.rendered_instances.add(instance_name)

    def mark_instances_quantified(self, instance_names: Iterable[str]) -> None:
        """Mark the instances as quantified in-place."""
        self.quantified_instances.update(instance_names)

    def get_node_for_instance(self, instance_name: str) -> Node:
        return self.instance_node_map[instance_name]

    def is_instance_rendered(self, instance_name: str) -> bool:
        return instance_name in self.rendered_instances

    def is_instance_quantified(self, instance_name: str) -> bool:
        return instance_name in self.quantified_instances

    def get_instance_depth(self, instance_name: str) -> int:
        return self.instance_depths_map[instance_name]

    def get_instances_at_scope(self, node: Node | None) -> set[str]:
        # None as the node means the widest possible scope
        return self.scope_instance_map[node[0] if node else None]

    def get_instances_to_quantify_at_scope(self, scope: Node | None) -> set[str]:
        """Get the instances that should be quantified at the given scope."""
        instances = self.get_instances_at_scope(scope)
        return instances - self.quantified_instances


def _build_scope_instance_map(
    amr_tree: Tree,
    instance_lca_map: dict[str, str],
    instance_depths_map: dict[str, int],
    instance_node_map: dict[str, Node],
    coreferent_instances: frozenset[str],
    override_is_projective_callback: Optional[OverrideIsProjectiveCallback],
) -> dict[str | None, set[str]]:
    """
    Build a map of the scope (instance name of the node in the tree this variable should be scoped) to a list of instances
    Takes into account any overrides provided by the override_is_projective_callback
    """
    instance_scope_map = {}
    for instance, lca in instance_lca_map.items():
        scope: str | None = lca
        if override_is_projective_callback:
            info = OverrideIsProjectiveCallbackInfo(
                instance_name=instance,
                node=instance_node_map[instance],
                depth=instance_depths_map[instance],
                is_coreferent=instance in coreferent_instances,
                is_default_hoisted=lca != instance,
                amr_tree=amr_tree,
            )
            if override_is_projective_callback(info) is True:
                scope = None
        instance_scope_map[instance] = scope

    scope_instance_map: dict[str | None, set[str]] = defaultdict(set)
    for instance, scope in instance_scope_map.items():
        scope_instance_map[scope].add(instance)
    return scope_instance_map
