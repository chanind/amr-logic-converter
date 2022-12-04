from __future__ import annotations
from typing import cast

import penman
import pytest
from syrupy.assertion import SnapshotAssertion

from amr_logic_converter import AmrLogicConverter
from amr_logic_converter.AmrLogicConverter import (
    OverrideConjunctionCallbackInfo,
    OverrideQuantificationCallbackInfo,
)
from amr_logic_converter.types import All, And, Clause, Implies, Not, Variable
from tests.test_utils import fmt_logic


converter = AmrLogicConverter(
    existentially_quantify_instances=True, capitalize_variables=False
)


def test_convert_basic_amr() -> None:
    amr_str = """
    (e / give-01
        :ARG0 (x / person :named "Ms Ribble")
        :ARG2 (y / child)
        :ARG1 (z / envelope))
    """
    expected = '∃e(give-01(e) ∧ ∃x(:ARG0(e, x) ∧ person(x) ∧ :named(x, "Ms Ribble")) ∧ ∃y(:ARG2(e, y) ∧ child(y)) ∧ ∃z(:ARG1(e, z) ∧ envelope(z)))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_works_with_amr_tree() -> None:
    amr_str = """
    (e / give-01
        :ARG0 (x / person :named "Ms Ribble")
        :ARG1 (z / envelope))
    """
    expected = '∃e(give-01(e) ∧ ∃x(:ARG0(e, x) ∧ person(x) ∧ :named(x, "Ms Ribble")) ∧ ∃z(:ARG1(e, z) ∧ envelope(z)))'
    logic = converter.convert(penman.parse(amr_str))
    assert str(logic) == expected


def test_convert_works_with_amr_graph() -> None:
    amr_str = """
    (e / give-01
        :ARG0 (x / person :named "Ms Ribble")
        :ARG1 (z / envelope))
    """
    expected = '∃e(give-01(e) ∧ ∃x(:ARG0(e, x) ∧ person(x) ∧ :named(x, "Ms Ribble")) ∧ ∃z(:ARG1(e, z) ∧ envelope(z)))'
    logic = converter.convert(penman.decode(amr_str))
    assert str(logic) == expected


def test_convert_errors_on_invalid_input() -> None:
    with pytest.raises(TypeError):
        converter.convert(17)


def test_convert_basic_amr_with_role_inversion() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    expected = "∃y(book(y) ∧ ∃e(:ARG1(e, y) ∧ read-01(e) ∧ ∃x(:ARG0(e, x) ∧ girl(x))))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_capitalized_variables_by_default() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    capitalized_converter = AmrLogicConverter(existentially_quantify_instances=True)
    expected = "∃Y(book(Y) ∧ ∃E(:ARG1(E, Y) ∧ read-01(E) ∧ ∃X(:ARG0(E, X) ∧ girl(X))))"
    logic = capitalized_converter.convert(amr_str)
    assert str(logic) == expected


def test__convert_amr_skips_role_inversion_if_specified() -> None:
    amr_str = """
    (y / book
        :ARG1-of (e / read-01
            :ARG0 (x / girl)))
    """
    expected = (
        "∃y(book(y) ∧ ∃e(:ARG1-of(y, e) ∧ read-01(e) ∧ ∃x(:ARG0(e, x) ∧ girl(x))))"
    )
    no_inversion_converter = AmrLogicConverter(
        invert_relations=False,
        existentially_quantify_instances=True,
        capitalize_variables=False,
    )
    logic = no_inversion_converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_negation() -> None:
    amr_str = """
    (e / giggle-01
        :polarity -
        :ARG0 (x / boy))
    """
    expected = "¬∃e(giggle-01(e) ∧ ∃x(:ARG0(e, x) ∧ boy(x)))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_negation_maintains_negation_scope_when_inverted() -> None:
    amr_str = """
    (x / boy
        :ARG0-of (e / giggle-01
            :polarity -))
    """
    expected = "∃x(boy(x) ∧ ¬∃e(:ARG0(e, x) ∧ giggle-01(e)))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_coreference_and_no_subattrs() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person)
        :ARG1 x)
    """

    expected = "∃e(∃x(dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ :ARG1(e, x)))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :named "Mr Krupp")
        :ARG1 x)
    """

    expected = '∃e(∃x(dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ :named(x, "Mr Krupp") ∧ :ARG1(e, x)))'
    logic = converter.convert(amr_str)
    print(logic)
    assert str(logic) == expected


def test_convert_amr_with_alignment_markers(snapshot: SnapshotAssertion) -> None:
    amr_str = """
    (e / give-01~2
        :ARG0 (x / person :named "Ms Ribble"~2)
        :ARG2 (y / child~3)
        :ARG1 (z / envelope~4))
    """
    expected = '∃e(give-01(e) ∧ ∃x(:ARG0(e, x) ∧ person(x) ∧ :named(x, "Ms Ribble")) ∧ ∃y(:ARG2(e, y) ∧ child(y)) ∧ ∃z(:ARG1(e, z) ∧ envelope(z)))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected
    # alignments are included in the logic elements, just using a snapshot assert for convenience
    assert logic == snapshot


def test_convert_amr_with_nested_coreference() -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - ))
        :ARG1 (
            z / dog
                :ARG0-of (w / wash-01
                    :ARG1 z)))
    """
    expected = "∃e(dry-01(e) ∧ ∃x(:ARG0(e, x) ∧ person(x) ∧ ¬∃g(:ARG0(g, x) ∧ giggle-01(g))) ∧ ∃z(:ARG1(e, z) ∧ dog(z) ∧ ∃w(:ARG0(w, z) ∧ wash-01(w) ∧ :ARG1(w, z))))"
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_with_only_coreference() -> None:
    amr_str = """
    (s / smurf
        :ARG0 s
        :ARG1 s)
    """
    expected = "∃s(smurf(s) ∧ :ARG0(s, s) ∧ :ARG1(s, s))"
    logic = converter.convert(amr_str)
    print(logic)
    assert str(logic) == expected


def test_convert_amr_leaves_off_existential_quantifiers_by_default(
    snapshot: SnapshotAssertion,
) -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - ))
        :ARG1 (
            z / dog
                :ARG0-of (w / wash-01
                    :ARG1 z)))
    """
    non_quantified_converter = AmrLogicConverter()
    expected = "dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ ¬(:ARG0(g, x) ∧ giggle-01(g)) ∧ :ARG1(e, z) ∧ dog(z) ∧ :ARG0(w, z) ∧ wash-01(w) ∧ :ARG1(w, z)"
    logic = non_quantified_converter.convert(amr_str)
    assert str(logic) == expected
    assert logic == snapshot


def test_convert_amr_can_replace_instances_with_variables(
    snapshot: SnapshotAssertion,
) -> None:
    amr_str = """
    (e / dry-01
        :ARG0 (x / person
            :ARG0-of (g / giggle-01
                :polarity - ))
        :ARG1 (
            z / dog
                :ARG0-of (w / wash-01
                    :ARG1 z)))
    """
    variables_converter = AmrLogicConverter(
        use_variables_for_instances=True,
        capitalize_variables=False,
    )
    expected = "dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ ¬(:ARG0(g, x) ∧ giggle-01(g)) ∧ :ARG1(e, z) ∧ dog(z) ∧ :ARG0(w, z) ∧ wash-01(w) ∧ :ARG1(w, z)"
    logic = variables_converter.convert(amr_str)
    assert str(logic) == expected
    assert logic == snapshot


def test_convert_amr_with_top_level_negation_and_deep_nesting() -> None:
    amr_str = """
    (b / bad-07~2
        :polarity -
        :ARG1 (e / dry-01
            :ARG0 (x / person
                :named "Mr Krupp")
            :ARG1 x))
    """
    expected = '¬∃b(bad-07(b) ∧ ∃e(∃x(:ARG1(b, e) ∧ dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ :named(x, "Mr Krupp") ∧ :ARG1(e, x))))'
    logic = converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_moves_coreferent_vars_to_widest_scope_with_maximally_hoist_coreferences_option() -> None:
    amr_str = """
    (b / bad-07~2
        :polarity -
        :ARG1 (e / dry-01
            :ARG0 (x / person
                :named "Mr Krupp")
            :ARG1 x))
    """
    expected = '∃x(¬∃b(bad-07(b) ∧ ∃e(:ARG1(b, e) ∧ dry-01(e) ∧ :ARG0(e, x) ∧ person(x) ∧ :named(x, "Mr Krupp") ∧ :ARG1(e, x))))'
    max_hoist_converter = AmrLogicConverter(
        existentially_quantify_instances=True,
        maximally_hoist_coreferences=True,
        capitalize_variables=False,
    )
    logic = max_hoist_converter.convert(amr_str)
    assert str(logic) == expected


def test_convert_amr_allows_overriding_scope_of_instances() -> None:
    amr_str = """
    (b / bad-07~2
        :polarity -
        :ARG1 (e / dry-01
            :ARG0 (x / person
                :named "Mr Krupp")
            :ARG1 x))
    """
    expected = '∃E(¬∃B(bad-07(B) ∧ ∃X(:ARG1(B, E) ∧ dry-01(E) ∧ :ARG0(E, X) ∧ person(X) ∧ :named(X, "Mr Krupp") ∧ :ARG1(E, X))))'
    override_scope_converter = AmrLogicConverter(
        existentially_quantify_instances=True,
        override_is_projective=lambda info: True if info.instance_name == "e" else None,
    )
    logic = override_scope_converter.convert(amr_str)
    print(logic)
    assert str(logic) == expected


def test_convert_amr_allows_overriding_quantification() -> None:
    amr_str = """
    (b / bad-07~2
        :polarity -
        :ARG1 (e / dry-01
            :ARG0 (x / person
                :named "Mr Krupp")
            :ARG1 x))
    """
    expected = '¬∃B(bad-07(B) ∧ ∀E(∃X(:ARG1(B, E) ∧ dry-01(E) ∧ :ARG0(E, X) ∧ person(X) ∧ :named(X, "Mr Krupp") ∧ :ARG1(E, X))))'
    override_scope_converter = AmrLogicConverter(
        existentially_quantify_instances=True,
        override_quantification=lambda clause, info: All(
            cast(Variable, info.bound_instance), clause
        )
        if info.instance_name == "e"
        else None,
    )
    logic = override_scope_converter.convert(amr_str)
    print(logic)
    assert str(logic) == expected


def test_convert_amr_allows_overriding_conjunction() -> None:
    amr_str = """
    (b / bad-07~2
        :polarity -
        :ARG1 (e / dry-01
            :ARG0 (x / person
                :named "Mr Krupp")
            :ARG1 x))
    """
    expected_with_quantifiers = '¬((∃E(∃X(:ARG1(B, E) ∧ dry-01(E) ∧ :ARG0(E, X) ∧ person(X) ∧ :named(X, "Mr Krupp") ∧ :ARG1(E, X)))) → bad-07(B))'
    expected_without_quantifiers = '¬((:ARG1(B, E) ∧ dry-01(E) ∧ :ARG0(E, X) ∧ person(X) ∧ :named(X, "Mr Krupp") ∧ :ARG1(E, X)) → bad-07(B))'

    def override_conjunction(info: OverrideConjunctionCallbackInfo) -> Clause | None:
        if info.instance_name != "b":
            return None
        antecedents = [*info.subterms]
        if info.closure_term:
            antecedents.append(info.closure_term)
        return Implies(And(*antecedents), info.predicate_term)

    def override_quantification(
        clause: Clause, info: OverrideQuantificationCallbackInfo
    ) -> Clause | None:
        if info.instance_name != "b":
            return None
        return Not(clause) if info.is_negated else clause

    override_scope_with_quantifiers_converter = AmrLogicConverter(
        existentially_quantify_instances=True,
        override_conjunction=override_conjunction,
        override_quantification=override_quantification,
    )
    with_quantifiers_logic = override_scope_with_quantifiers_converter.convert(amr_str)
    assert str(with_quantifiers_logic) == expected_with_quantifiers

    override_scope_without_quantifiers_converter = AmrLogicConverter(
        use_variables_for_instances=True,
        override_conjunction=override_conjunction,
        override_quantification=override_quantification,
    )
    without_quantifiers_logic = override_scope_without_quantifiers_converter.convert(
        amr_str
    )
    assert str(without_quantifiers_logic) == expected_without_quantifiers


def test_convert_amr_with_conditionals() -> None:
    amr_str = """
    (s / sing-01
        :ARG0 (b / boy)
        :condition (g / give-01
            :ARG1 (m / money)
            :ARG2 b))
    """
    expected = """
    ∃S(
        ∃B(
            ∃G(
                give-01(G) ∧
                ∃M(
                    :ARG1(G, M) ∧ money(M)
                ) ∧
                :ARG2(G, B) ∧
                boy(B)
            ) → (
                sing-01(S) ∧ :ARG0(S, B)
            )
        )
    )
    """
    implication_converter = AmrLogicConverter(
        existentially_quantify_instances=True,
        use_implies_for_conditions=True,
        use_variables_for_instances=True,
    )
    logic = implication_converter.convert(amr_str)
    assert fmt_logic(str(logic)) == fmt_logic(expected)
