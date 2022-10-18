from amr_logic_converter.types import Const, And, Implies, Or


def test_const_strips_quotes_from_strings() -> None:
    const = Const('"foo"', "string")
    assert const.value == "foo"
    assert str(const) == '"foo"'


def test_and_spreads_nested_ands() -> None:
    and_ = And((And((Const("a", "symbol"), Const("b", "symbol"))),))
    assert and_.args == (Const("a", "symbol"), Const("b", "symbol"))
    assert str(and_) == "a ∧ b"


def test_or_spreads_nested_ors() -> None:
    or_ = Or((Or((Const("a", "symbol"), Const("b", "symbol"))),))
    assert or_.args == (Const("a", "symbol"), Const("b", "symbol"))
    assert str(or_) == "a ∨ b"


def test_or_adds_parens_to_nested_ands_when_printing() -> None:
    or_ = Or((And((Const("a", "symbol"), Const("b", "symbol"))), Const("c", "symbol")))
    assert str(or_) == "(a ∧ b) ∨ c"


def test_and_adds_parens_to_nested_ors_when_printing() -> None:
    and_ = And((Or((Const("a", "symbol"), Const("b", "symbol"))), Const("c", "symbol")))
    assert str(and_) == "(a ∨ b) ∧ c"


def test_imples_adds_parens_to_nested_clauses_when_printing() -> None:
    implies = Implies(
        And((Or((Const("a", "symbol"), Const("b", "symbol"))), Const("c", "symbol"))),
        Const("d", "symbol"),
    )
    assert str(implies) == "((a ∨ b) ∧ c) → d"
