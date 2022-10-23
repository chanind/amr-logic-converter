from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from typing_extensions import Literal
from penman.surface import Alignment

from .parse_value_and_alignment import parse_value_and_alignment


ConstType = Literal["string", "symbol", "instance"]


@dataclass
class Const:
    value: str
    type: ConstType
    alignment: Alignment | None = None

    def __init__(self, element: str, type: ConstType) -> None:
        self.type = type
        self.value, self.alignment = parse_value_and_alignment(element)
        # remove explicit quotes from string literals
        if (
            self.type == "string"
            and self.value.startswith('"')
            and self.value.endswith('"')
        ):
            self.value = self.value[1:-1]

    def __str__(self) -> str:
        if self.type == "string":
            return f'"{self.value}"'
        return self.value


@dataclass
class Param:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class Predicate:
    value: str
    args: tuple[Const | Param, ...]
    alignment: Alignment | None = None

    def __init__(self, element: str, args: tuple[Const | Param, ...]) -> None:
        self.value, self.alignment = parse_value_and_alignment(element)
        self.args = args

    def __str__(self) -> str:
        return f"{str(self.value)}({', '.join(map(str, self.args))})"


@dataclass
class And:
    args: tuple["Formula", ...]

    def __init__(self, args: tuple["Formula", ...]) -> None:
        # automatically reduce repeated ANDs
        simplified_args: list["Formula"] = []
        for arg in args:
            if type(arg) is And:
                simplified_args.extend(arg.args)
            else:
                simplified_args.append(arg)
        self.args = tuple(simplified_args)

    def __str__(self) -> str:
        arg_strs = []
        for arg in self.args:
            if type(arg) in [Or, Implies]:
                arg_strs.append(f"({str(arg)})")
            else:
                arg_strs.append(str(arg))
        return f"{' ∧ '.join(arg_strs)}"


@dataclass
class Or:
    args: tuple["Formula", ...]

    def __init__(self, args: tuple["Formula", ...]) -> None:
        # automatically reduce repeated ORs
        simplified_args: list["Formula"] = []
        for arg in args:
            if type(arg) is Or:
                simplified_args.extend(arg.args)
            else:
                simplified_args.append(arg)
        self.args = tuple(simplified_args)

    def __str__(self) -> str:
        arg_strs = []
        for arg in self.args:
            if type(arg) in [And, Implies]:
                arg_strs.append(f"({str(arg)})")
            else:
                arg_strs.append(str(arg))
        return f"{' ∨ '.join(arg_strs)}"


@dataclass
class Not:
    body: "Formula"

    def __str__(self) -> str:
        if type(self.body) is And:
            return f"¬({str(self.body)})"
        return f"¬{str(self.body)}"


@dataclass
class Implies:
    antecedent: "Formula"
    consequent: "Formula"

    def __str__(self) -> str:
        antecedent_str = str(self.antecedent)
        consequent_str = str(self.consequent)
        if type(self.antecedent) in [And, Or, Implies]:
            antecedent_str = f"({antecedent_str})"
        if type(self.consequent) in [And, Or, Implies]:
            consequent_str = f"({consequent_str})"
        return f"{antecedent_str} → {consequent_str}"


@dataclass
class Exists:
    param: Param
    body: "Formula"

    def __str__(self) -> str:
        return f"∃{str(self.param)}({str(self.body)})"


Formula = Union[Predicate, Not, Exists, And, Or]
