from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zipfile import ZipFile

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_sources.py"
spec = spec_from_file_location("source_audit", MODULE_PATH)
assert spec is not None and spec.loader is not None
audit_module = module_from_spec(spec)
spec.loader.exec_module(audit_module)


def test_dwg_header_and_checksum(tmp_path):
    file = tmp_path / "sample.dwg"
    file.write_bytes(b"AC1021\x00fixture")
    result = audit_module.audit(None, None, [file])
    assert result["sources"]["drawing_1"]["dwg_header"] == "AC1021"
    assert result["sources"]["drawing_1"]["geometry_verified"] is False
    assert len(result["sources"]["drawing_1"]["sha256"]) == 64


def test_pdf_fingerprint_does_not_assume_match(tmp_path):
    file = tmp_path / "qcvn.pdf"
    file.write_bytes(b"%PDF-1.7\nexample")
    result = audit_module.audit(file, None, [])
    assert result["sources"]["qcvn"]["header_is_pdf"] is True
    assert result["sources"]["qcvn"]["matches_locked_sha256"] is False


def test_workbook_checks_uses_package_metadata(tmp_path):
    file = tmp_path / "template.xlsx"
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with ZipFile(file, "w") as archive:
        archive.writestr("xl/workbook.xml",
            f'<workbook xmlns="{ns}"><sheets><sheet name="KL VACH SON"/></sheets>'
            '<definedNames><definedName name="n">A1</definedName></definedNames></workbook>')
        archive.writestr("xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{ns}"><sheetData><row r="1">'
            '<c r="A1" t="e"><v>#REF!</v></c></row></sheetData></worksheet>')
        archive.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
    checks = audit_module.workbook_checks(file)
    assert checks["sheet_names"] == ["KL VACH SON"]
    assert checks["external_link_parts"] == 1
    assert checks["defined_names"] == 1
    assert checks["cached_ref_errors"] == 1
