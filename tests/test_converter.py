from amr_fol_converter.converter import convert_amr_str


def test_convert_basic_amr() -> None:
    amr_str = """
    (e / give-01
        :ARG0 (x / person :named "Ms Ribble")
        :ARG2 (y / child)
        :ARG1 (z / envelope))
    """
    expected = '∃e(give-01(e) ^ ∃x(:ARG0(e, x) ^ person(x) ^ :named(x, "Ms Ribble")) ^ ∃y(:ARG2(e, y) ^ child(y)) ^ ∃z(:ARG1(e, z) ^ envelope(z)))'
    logic = convert_amr_str(amr_str)
    assert str(logic) == expected


def test_convert_basic_amr_with_role_inversion() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    expected = "∃e(read-01(e) ^ ∃y(:ARG1(e, y) ^ book(y)) ^ ∃x(:ARG0(e, x) ^ girl(x)))"
    logic = convert_amr_str(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_negation() -> None:
    amr_str = """
    (e / giggle-01
        :polarity -
        :ARG0 (x / boy))
    """
    expected = "¬∃e(giggle-01(e) ^ ∃x(:ARG0(e, x) ^ boy(x)))"
    logic = convert_amr_str(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :named "Mr Krupp")
        :ARG1 x)
    """

    expected = '∃x(∃e(dry-01(e) ^ :ARG0(e, x) ^ :ARG1(e, x)) ^ person(x) ^ :named(x, "Mr Krupp"))'
    logic = convert_amr_str(amr_str)
    assert str(logic) == expected
