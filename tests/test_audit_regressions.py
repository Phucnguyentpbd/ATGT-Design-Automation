"""Behavioral regressions found during the 2026-10-24 source audit."""
from dataclasses import replace
from decimal import Decimal as D

import pytest

from atgt.contracts import Marking, SignFace
from atgt.knowledge import RuleStore
from atgt.takeoff import painted_area, segment_area, sign_summary
from atgt.validation import validate_sign_code


@pytest.mark.parametrize("changes", [
    {"painted_intervals_m": ((D(0), D(5)), (D(4), D(8)))},
    {"painted_intervals_m": ((D(-1), D(5)),)},
    {"width_m": D("-0.2")},
    {"width_m": D("NaN")},
])
def test_total_and_partition_both_reject_invalid_paint(changes):
    mark = replace(Marking("m", "3.1a", "r", D(0), D(10), D("0.2"), D(2),
                           ((D(0), D(10)),), "verified", "s"), **changes)
    for calculate in (painted_area, lambda m: segment_area(m, [(D(0), D(10))])):
        with pytest.raises(ValueError):
            calculate(mark)


def test_sign_takeoff_cannot_double_count_one_face():
    face = SignFace("f", "c", "P.102", "circle", D(700), D(700), "install", "a", "verified", "ref")
    with pytest.raises(ValueError, match="duplicate_face"):
        sign_summary([face, face])


@pytest.mark.parametrize("code", ["XYZ.102", "P.foo", "P.102.", "P.102-103"])
def test_only_canonical_sign_code_syntax_is_accepted(code):
    assert not validate_sign_code(code)


def test_only_latest_approved_rule_version_executes(tmp_path):
    store = RuleStore(tmp_path / "rules.sqlite")
    try:
        for v in (1, 2, 3):
            store.add_draft("edge", v, "a" * 64, "source", ("ordinary",), {"revision": v})
            if v < 3:
                store.approve("edge", v, "reviewer", source_checked=True)
        assert [r.version for r in store.executable("ordinary")] == [2]
    finally:
        store.close()
