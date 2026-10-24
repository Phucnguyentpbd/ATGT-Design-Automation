"""CI smoke coverage for QCVN ingestion; real locked PDF remains outside public Git."""
from pathlib import Path
import pytest
from atgt.qcvn_ingest import ANNEX, PDF_SHA, annex_of, code_normalize, SIGN, MARK


@pytest.fixture
def locked_pdf(tmp_path, monkeypatch):
    # Real PDF parser / SQLite / FTS boundary; no fake ingestion implementation.
    import fitz
    from atgt import qcvn_ingest as ingest
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        for n in range(403):
            page = doc.new_page()
            if n < 42:
                for i in (0, 1):
                    page.insert_text((40, 40 + i * 25), f"ARTICLE {2*n+i+1}. Title")
            if n == 80:
                page.insert_text((40, 40), "P.102")
        doc.save(pdf)
    # The test PDF is an explicit locked fixture, not a production-source bypass.
    monkeypatch.setattr(ingest, "PDF_SHA", ingest.digest(pdf))
    import re
    monkeypatch.setattr(ingest, "ARTICLE", re.compile(r"(?m)^ARTICLE (\d+)\. ([^\n]+)"))
    return pdf


def test_failed_rebuild_preserves_previous_searchable_index(tmp_path, locked_pdf):
    from atgt.qcvn_ingest import build, digest, lookup
    out = tmp_path / "knowledge"
    build(locked_pdf, out)
    db = out / "atgt-knowledge.sqlite"
    before = digest(db)
    bad = tmp_path / "bad.lin"
    bad.write_text("*BAD, incomplete\n", encoding="utf-8")
    with pytest.raises(ValueError):
        build(locked_pdf, out, lin=bad)
    assert digest(db) == before
    assert lookup(db, "P.102")[0]["page"] == 81


def test_native_inventory_flows_into_knowledge_without_archive(tmp_path, locked_pdf):
    import json
    import sqlite3
    from atgt.assets import scan_dwg_library
    from atgt.qcvn_ingest import build
    source = tmp_path / "signs"
    source.mkdir()
    (source / "102.dwg").write_bytes(b"AC1021native-inventory")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"sign_assets": scan_dwg_library(source)}))
    out = tmp_path / "knowledge"
    result = build(locked_pdf, out, catalog=catalog)
    assert result["dwg_count"] == 1
    with sqlite3.connect(out / "atgt-knowledge.sqlite") as db:
        assert db.execute("SELECT candidate_codes_json,status FROM cad_assets").fetchone() == ('["P.102"]', 'unverified')

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
