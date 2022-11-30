from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Callable, Optional
from typing_extensions import Literal

from penman.tree import Node, Tree

from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)
from amr_logic_converter.find_instance_depths import find_instance_depths
from amr_logic_converter.find_coreferent_instances import find_coreferent_instances
from amr_logic_converter.map_instances_lca import map_instances_lca
from amr_logic_converter.map_instances_to_nodes import map_instances_to_nodes


@dataclass
class OverrideInstanceScopeCallbackMeta:
    """Metadata passed to the OverrideInstanceScopeCallback wtih info about the node being processed"""

    amr_tree: Tree
    instance_name: str
    node: Node
    depth: int
    is_coreferent: bool
    is_default_hoisted: bool


OverrideInstanceScopeCallback = Callable[
    [OverrideInstanceScopeCallbackMeta], Optional[Literal["wide", "default"]]
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
    # a map of the scope (instance name of the node in the tree this variable should be scoped) to a list of instances
    # `None` as the scope means the instance should be scoped around the entire tree
    scope_instance_map: dict[str | None, list[str]]
    non_projective_instances: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_amr_tree(
        cls,
        amr_tree: Tree,
        override_instance_scope: Optional[OverrideInstanceScopeCallback] = None,
    ) -> AmrContext:
        instances = extract_instances_from_amr_tree(amr_tree)
        coreferent_instances = find_coreferent_instances(amr_tree, instances)
        instance_node_map = map_instances_to_nodes(amr_tree, instances)
        instance_depths_map = find_instance_depths(amr_tree, instances)
        instance_lca_map = map_instances_lca(amr_tree, instances)
        scope_instance_map = _build_scope_instance_map(
            amr_tree=amr_tree,
            instance_lca_map=instance_lca_map,
            instance_depths_map=instance_depths_map,
            instance_node_map=instance_node_map,
            coreferent_instances=coreferent_instances,
            override_scope_callback=override_instance_scope,
        )
        return cls(
            amr_tree=amr_tree,
            instances=instances,
            coreferent_instances=coreferent_instances,
            instance_node_map=instance_node_map,
            instance_depths_map=instance_depths_map,
            scope_instance_map=scope_instance_map,
        )

    def mark_instance_non_projective(self, instance_name: str) -> AmrContext:
        """Return a new context with the given instance marked as non-projective."""
        return replace(
            self,
            non_projective_instances=self.non_projective_instances | {instance_name},
        )

    def get_node_for_instance(self, instance_name: str) -> Node:
        return self.instance_node_map[instance_name]

    def is_instance_projective(self, instance_name: str) -> bool:
        return instance_name not in self.non_projective_instances

    def get_instance_depth(self, instance_name: str) -> int:
        return self.instance_depths_map[instance_name]

    def get_instances_at_node_scope(self, node: Node | None) -> list[str]:
        # None as the node means the widest possible scope
        return self.scope_instance_map[node[0] if node else None]


def _build_scope_instance_map(
    amr_tree: Tree,
    instance_lca_map: dict[str, str],
    instance_depths_map: dict[str, int],
    instance_node_map: dict[str, Node],
    coreferent_instances: frozenset[str],
    override_scope_callback: Optional[OverrideInstanceScopeCallback],
) -> dict[str | None, list[str]]:
    """
    Build a map of the scope (instance name of the node in the tree this variable should be scoped) to a list of instances
    Takes into account any overrides provided by the override_scope_callback
    """
    instance_scope_map = {}
    for instance, lca in instance_lca_map.items():
        scope: str | None = lca
        if override_scope_callback:
            meta = OverrideInstanceScopeCallbackMeta(
                instance_name=instance,
                node=instance_node_map[instance],
                depth=instance_depths_map[instance],
                is_coreferent=instance in coreferent_instances,
                is_default_hoisted=lca != instance,
                amr_tree=amr_tree,
            )
            if override_scope_callback(meta) == "wide":
                scope = None
        instance_scope_map[instance] = scope

    scope_instance_map: dict[str | None, list[str]] = defaultdict(list)
    for instance, scope in instance_scope_map.items():
        scope_instance_map[scope].append(instance)
    return scope_instance_map
