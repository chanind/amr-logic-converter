from amr_logic_converter.AmrLogicConverter import AmrLogicConverter
from syrupy.assertion import SnapshotAssertion


converter = AmrLogicConverter()


def test_convert_basic_amr() -> None:
    amr_str = """
    (e / give-01
        :ARG0 (x / person :named "Ms Ribble")
        :ARG2 (y / child)
        :ARG1 (z / envelope))
    """
    expected = '∃e(give-01(e) ^ ∃x(:ARG0(e, x) ^ person(x) ^ :named(x, "Ms Ribble")) ^ ∃y(:ARG2(e, y) ^ child(y)) ^ ∃z(:ARG1(e, z) ^ envelope(z)))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_basic_amr_with_role_inversion() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    expected = "∃y(book(y) ^ ∃e(:ARG1(e, y) ^ read-01(e) ^ ∃x(:ARG0(e, x) ^ girl(x))))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_skips_role_inversion_if_specified() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    expected = (
        "∃y(book(y) ^ ∃e(:ARG1-of(y, e) ^ read-01(e) ^ ∃x(:ARG0(e, x) ^ girl(x))))"
    )
    no_inversion_converter = AmrLogicConverter(invert_relations=False)
    logic = no_inversion_converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_negation() -> None:
    amr_str = """
    (e / giggle-01
        :polarity -
        :ARG0 (x / boy))
    """
    expected = "¬∃e(giggle-01(e) ^ ∃x(:ARG0(e, x) ^ boy(x)))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_negation_maintains_negation_scope_when_inverted() -> None:
    amr_str = """
    (x / boy
        :ARG0-of (e / giggle-01
        :polarity -))
    """
    expected = "∃x(boy(x) ^ ¬∃e(:ARG0(e, x) ^ giggle-01(e)))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :named "Mr Krupp")
        :ARG1 x)
    """

    expected = '∃x(∃e(dry-01(e) ^ :ARG0(e, x) ^ :ARG1(e, x)) ^ person(x) ^ :named(x, "Mr Krupp"))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_parse_amr_with_alignment_markers(snapshot: SnapshotAssertion) -> None:
    amr_str = """
    (e / give-01~2
        :ARG0 (x / person :named "Ms Ribble"~2)
        :ARG2 (y / child~3)
        :ARG1 (z / envelope~4))
    """
    expected = '∃e(give-01(e) ^ ∃x(:ARG0(e, x) ^ person(x) ^ :named(x, "Ms Ribble")) ^ ∃y(:ARG2(e, y) ^ child(y)) ^ ∃z(:ARG1(e, z) ^ envelope(z)))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected
    # alignments are included in the logic elements, just using a snapshot assert for convenience
    assert logic == snapshot
