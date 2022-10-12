from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from penman.surface import Alignment

from .parse_value_and_alignment import parse_value_and_alignment


@dataclass
class Const:
    value: str
    alignment: Alignment | None = None

    def __init__(self, element: str) -> None:
        self.value, self.alignment = parse_value_and_alignment(element)

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
        self.value, self.alignment = parse_value_and_alignment(element)
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
