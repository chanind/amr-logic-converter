from __future__ import annotations

from penman import parse
from amr_logic_converter.extract_instances_from_amr_tree import (
    extract_instances_from_amr_tree,
)

from amr_logic_converter.map_contained_coreferences import map_contained_coreferences


def freeze_set_map(x: dict[str, set[str]]) -> dict[str, frozenset[str]]:
    return {k: frozenset(v) for k, v in x.items()}


def test_map_contained_coreferences_with_no_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - )))
    """
    tree = parse(amr_str)
    instances = extract_instances_from_amr_tree(tree)
    assert map_contained_coreferences(tree, instances) == freeze_set_map(
        {
            "e": {"x", "g"},
            "x": {"g"},
            "g": set(),
        }
    )


def test_map_contained_coreferences_with_coreference_in_single_branch() -> None:
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
    assert map_contained_coreferences(tree, instances) == freeze_set_map(
        {
            "e": {"x", "g", "z", "w"},
            "x": {"g"},
            "g": set(),
            "z": {"w", "z"},
            "w": {"z"},
        }
    )


def test_map_contained_coreferences_with_coreference_across_branch() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01))
        :ARG1 x)
    """
    tree = parse(amr_str)
    instances = extract_instances_from_amr_tree(tree)
    assert map_contained_coreferences(tree, instances) == freeze_set_map(
        {
            "e": {"x", "g"},
            "x": {"g"},
            "g": set(),
        }
    )
