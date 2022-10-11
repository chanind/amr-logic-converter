from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Union


@dataclass
class Const:
    node: Any

    def __str__(self) -> str:
        return str(self.node)


@dataclass
class Var:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class Predicate:
    node: Any
    args: tuple[Const | Var, ...]

    def __str__(self) -> str:
        return f"{str(self.node)}({', '.join(map(str, self.args))})"


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
