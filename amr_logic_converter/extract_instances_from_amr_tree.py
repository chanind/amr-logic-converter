from __future__ import annotations

import penman
from penman.models import amr


def extract_instances_from_amr_tree(amr_tree: penman.Tree) -> frozenset[str]:
    """Extract the set of instances in the given AMR tree."""
    instances = set()
    amr_graph = penman.interpret(amr_tree, model=amr.model)
    for edge in amr_graph.edges():
        instances.add(edge.source)
        instances.add(edge.target)
    return frozenset(instances)
