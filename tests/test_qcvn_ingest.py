"""CI smoke coverage for QCVN ingestion; real locked PDF remains outside public Git."""
from pathlib import Path
import pytest
from atgt.qcvn_ingest import ANNEX, PDF_SHA, annex_of, code_normalize, SIGN, MARK

@pytest.mark.parametrize("raw,expected",[
    ("P.102","P.102"), ("W.201A","W.201a"), ("DP.135","DP.135"),
    ("R.E,9A","R.E,9a"), ("R.E,10d","R.E,10d"),
    ("S.G,12A","S.G,12a"), ("S.H,6","S.H,6"), ("IE.450A","IE.450a")])
def test_code_normalization(raw,expected):
    assert code_normalize(raw)==expected

@pytest.mark.parametrize("annex,start",list(ANNEX.items()))
def test_annex_boundaries(annex,start):
    assert annex_of(start)==annex

def test_sign_codes_in_context():
    text='Biển P.102; R.E,9a; S.G,12b; DP.135; IE.450a'
    got={code_normalize(match[1]) for match in SIGN.finditer(text)}
    assert got=={"P.102","R.E,9a","S.G,12b","DP.135","IE.450a"}

def test_marking_variants():
    assert [m[1] for m in MARK.finditer("Vạch 1.1; vạch 2.1; Vạch 9.5.e")]==["1.1","2.1","9.5.e"]

def test_source_lock_defined():
    assert len(PDF_SHA)==64
