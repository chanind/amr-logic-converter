from amr_logic_converter.types import Const, And


def test_const_strips_quotes_from_strings() -> None:
    const = Const('"foo"', "string")
    assert const.value == "foo"
    assert str(const) == '"foo"'


def test_and_spreads_nested_ands() -> None:
    and_ = And((And((Const("a", "symbol"), Const("b", "symbol"))),))
    assert and_.args == (Const("a", "symbol"), Const("b", "symbol"))
    assert str(and_) == "a ^ b"
