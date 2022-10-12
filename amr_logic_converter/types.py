from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from penman.surface import Alignment


def parse_element(element: str) -> tuple[str, Alignment | None]:
    """Break apart a const element into alignment and value."""
    # based on https://github.com/goodmami/penman/blob/f3b0c423a60f82b13fffeec73fa1a77bf75cd4dc/penman/layout.py#L211
    # this is a private method in penman, so copying it here in case the internal penman API changes
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


@dataclass
class Const:
    value: str
    alignment: Alignment | None = None

    def __init__(self, element: str) -> None:
        self.value, self.alignment = parse_element(element)

    def __str__(self) -> str:
        return self.value


@dataclass
class Var:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class Predicate:
    value: str
    args: tuple[Const | Var, ...]
    alignment: Alignment | None = None

    def __init__(self, element: str, args: tuple[Const | Var, ...]) -> None:
        self.value, self.alignment = parse_element(element)
        self.args = args

    def __str__(self) -> str:
        return f"{str(self.value)}({', '.join(map(str, self.args))})"


@dataclass
class And:
    args: tuple["Formula", ...]

    def __str__(self) -> str:
        return f"{' ^ '.join(map(str, self.args))}"


@dataclass
class Not:
    body: "Formula"

    def __str__(self) -> str:
        return f"¬{str(self.body)}"


@dataclass
class Exists:
    var: Var
    body: "Formula"

    def __str__(self) -> str:
        return f"∃{str(self.var)}({str(self.body)})"


Formula = Union[Const, Var, Predicate, Not, Exists, And]
