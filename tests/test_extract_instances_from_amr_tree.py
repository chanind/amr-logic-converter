from __future__ import annotations

import pytest
import penman
from penman.models import amr

from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)


def extract_instances_via_penman(amr_tree: penman.Tree) -> frozenset[str]:
    """Extract the set of instances in the given AMR tree."""
    instances = set()
    amr_graph = penman.interpret(amr_tree, model=amr.model)
    for edge in amr_graph.edges():
        instances.add(edge.source)
        instances.add(edge.target)
    return frozenset(instances)


@pytest.mark.parametrize(
    "amr_str",
    [
        """
    (s / sing-01
        :ARG0 (b / boy)
        :condition (g / give-01
            :ARG1 (m / money)
            :ARG2 b))
    """,
        """
    (p3 / possible-01~2
        :ARG1 (u / understand-01~2
            :ARG1 (u2 / upset-01~8
                :ARG0 (g / get-01~13
                    :ARG0 (y / you~4)
                    :ARG1 (p4 / present~18
                        :mod (f / festival~17
                            :name (n / name~17
                                :op1 "Christmas"~17)))
                    :ARG4 (p2 / person~15
                        :ARG0-of (h2 / have-rel-role-91~15
                            :ARG1 y
                            :ARG2 (n2 / nephew~15)))
                    :polarity -~12)
                :ARG1 (p / person~5
                    :ARG0-of (h / have-rel-role-91~5
                        :ARG1 y
                        :ARG2 (s / sibling~5))))))
    """,
    ],
)
def test_extract_instances_from_amr_tree_matches_penman(amr_str: str) -> None:
    """Test that extract_instances_from_amr_tree matches penman."""
    tree = penman.parse(amr_str)
    assert extract_instances_from_amr_tree(tree) == extract_instances_via_penman(tree)
