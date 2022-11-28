from __future__ import annotations

from penman import parse
from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)

from amr_logic_converter.map_instances_lca import map_instances_lca


def test_map_instances_lca_with_no_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - )))
    """
    tree = parse(amr_str)
    instances = extract_instances_from_amr_tree(tree)
    assert map_instances_lca(tree, instances) == {
        "e": "e",
        "x": "x",
        "g": "g",
    }


def test_map_instances_lca_with_coreference_in_single_branch() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - ))
        :ARG1 (
            z / dog
                :ARG0-of (w / wash-01
                    :ARG1 z)))
    """
    tree = parse(amr_str)
    instances = extract_instances_from_amr_tree(tree)
    assert map_instances_lca(tree, instances) == {
        "e": "e",
        "x": "x",
        "g": "g",
        "z": "z",
        "w": "w",
    }


def test_map_instances_lca_with_coreference_across_branch() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01))
        :ARG1 x)
    """
    tree = parse(amr_str)
    instances = extract_instances_from_amr_tree(tree)
    assert map_instances_lca(tree, instances) == {
        "e": "e",
        "x": "e",
        "g": "g",
    }
