from __future__ import annotations
from penman.surface import Alignment


def parse_value_and_alignment(element: str) -> tuple[str, Alignment | None]:
    """Break apart a const element into alignment and value."""
    # based on https://github.com/goodmami/penman/blob/f3b0c423a60f82b13fffeec73fa1a77bf75cd4dc/penman/layout.py#L211
    # this is a private method in penman, so copying it here in case the internal penman API changes
    # TODO: replace this by extracting this info directly from a penman graph
    value = element
    alignment = None
    if "~" in element:
        if element.startswith('"'):
            # need to handle alignments on strings differently
            # because strings may contain ~ inside the quotes (e.g., URIs)
            pivot = element.rindex('"') + 1
            if pivot < len(element):
                alignment = Alignment.from_string(element[pivot:])
                value = element[:pivot]
        else:
            value, _, alignment = element.partition("~")
            alignment = Alignment.from_string(alignment)
    return value, alignment
