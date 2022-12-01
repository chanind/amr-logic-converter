from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from typing_extensions import Literal
from penman.surface import Alignment

from .parse_symbol_and_alignment import parse_symbol_and_alignment


ConstantType = Literal["string", "symbol", "instance"]


@dataclass
class Constant:
    value: str
    type: ConstantType
    alignment: Alignment | None = None

    def __init__(self, element: str, type: ConstantType) -> None:
        self.type = type
        self.value, self.alignment = parse_symbol_and_alignment(element)
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
class Variable:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class Atom:
    predicate: Predicate
    terms: tuple[Term, ...]

    def __str__(self) -> str:
        terms_str = ", ".join([str(term) for term in self.terms])
        return f"{str(self.predicate)}({terms_str})"

    @property
    def alignment(self) -> Alignment | None:
        """Helper to make accessing the predicate alignment easier"""
        return self.predicate.alignment

    @property
    def symbol(self) -> str:
        """Helper to make accessing the predicate symbol easier"""
        return self.predicate.symbol


@dataclass
class Predicate:
    symbol: str
    alignment: Alignment | None = None

    @classmethod
    def from_amr_str(cls, amr_str: str) -> Predicate:
        symbol, alignment = parse_symbol_and_alignment(amr_str)
        return cls(symbol, alignment)

    def __call__(self, *terms: Term) -> Atom:
        return Atom(self, terms)

    def __str__(self) -> str:
        return self.symbol


@dataclass
class And:
    args: tuple["Clause", ...]

    def __init__(self, *args: "Clause") -> None:
        # automatically reduce repeated ANDs
        simplified_args: list["Clause"] = []
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
    args: tuple["Clause", ...]

    def __init__(self, *args: "Clause") -> None:
        # automatically reduce repeated ORs
        simplified_args: list["Clause"] = []
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
    body: "Clause"

    def __str__(self) -> str:
        if type(self.body) in [And, Or, Implies]:
            return f"¬({str(self.body)})"
        return f"¬{str(self.body)}"


@dataclass
class Implies:
    antecedent: "Clause"
    consequent: "Clause"

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
    param: Variable
    body: "Clause"

    def __str__(self) -> str:
        return f"∃{str(self.param)}({str(self.body)})"


@dataclass
class All:
    param: Variable
    body: "Clause"

    def __str__(self) -> str:
        return f"∀{str(self.param)}({str(self.body)})"


Clause = Union[Atom, Not, Exists, All, And, Or, Implies]
Term = Union[Constant, Variable]
