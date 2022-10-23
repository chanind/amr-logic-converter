from amr_logic_converter.types import Const, And, Implies, Or, Predicate


def test_const_strips_quotes_from_strings() -> None:
    const = Const('"foo"', "string")
    assert const.value == "foo"
    assert str(const) == '"foo"'


def test_and_spreads_nested_ands() -> None:
    and_ = And(
        (
            And(
                (
                    Predicate("P", (Const("a", "symbol"),)),
                    Predicate("P", (Const("b", "symbol"),)),
                )
            ),
        ),
    )
    assert and_.args == (
        Predicate("P", (Const("a", "symbol"),)),
        Predicate("P", (Const("b", "symbol"),)),
    )
    assert str(and_) == "P(a) ∧ P(b)"


def test_or_spreads_nested_ors() -> None:
    or_ = Or(
        (
            Or(
                (
                    Predicate("P", (Const("a", "symbol"),)),
                    Predicate("P", (Const("b", "symbol"),)),
                )
            ),
        )
    )
    assert or_.args == (
        Predicate("P", (Const("a", "symbol"),)),
        Predicate("P", (Const("b", "symbol"),)),
    )
    assert str(or_) == "P(a) ∨ P(b)"


def test_or_adds_parens_to_nested_ands_when_printing() -> None:
    or_ = Or(
        (
            And(
                (
                    Predicate("P", (Const("a", "symbol"),)),
                    Predicate("P", (Const("b", "symbol"),)),
                )
            ),
            Predicate(
                "P",
                (Const("c", "symbol"),),
            ),
        )
    )

    assert str(or_) == "(P(a) ∧ P(b)) ∨ P(c)"


def test_and_adds_parens_to_nested_ors_when_printing() -> None:
    and_ = And(
        (
            Or(
                (
                    Predicate("P", (Const("a", "symbol"),)),
                    Predicate("P", (Const("b", "symbol"),)),
                )
            ),
            Predicate("P", (Const("c", "symbol"),)),
        )
    )
    assert str(and_) == "(P(a) ∨ P(b)) ∧ P(c)"


def test_imples_adds_parens_to_nested_clauses_when_printing() -> None:
    implies = Implies(
        And(
            (
                Or(
                    (
                        Predicate("P", (Const("a", "symbol"),)),
                        Predicate("P", (Const("b", "symbol"),)),
                    )
                ),
                Predicate("P", (Const("c", "symbol"),)),
            )
        ),
        Predicate("P", (Const("d", "symbol"),)),
    )
    assert str(implies) == "((P(a) ∨ P(b)) ∧ P(c)) → P(d)"
