"""Verified quantity ledger -> Book2 cell plan, independent of any Excel writer.

No quantities are inferred from placement proposals or sample workbook values.
Coverage must explicitly distinguish a measured zero from missing measurement.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import argparse
import json
from pathlib import Path

from .contracts import SignFace
from .takeoff import sign_summary

TEMPLATE_SHA = "19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985"
WORK_LABELS = {"install": "Lắp mới", "retain": "Giữ lại", "relocate": "Di dời",
               "replace_face": "Thay mặt biển", "replace_content": "Thay nội dung"}
SHAPES = {"circle": "BB tròn", "triangle": "BB tam giác", "square": "BB vuông",
          "rectangle": "BB chữ nhật", "octagon": "BB bát giác"}
# row, code, thickness, unit; each quantity belongs to exactly one row.
ROWS = [(r, code, "2", "m2") for r, code in enumerate(
    ("1.1", "1.2", "1.3", "2.1", "3.1a", "3.1b", "4.1", "4.2", "4.4", "5.1",
     "7.1", "7.2_mau2", "7.3", "7.6", "9.3", "speed_reducer"), 7)] + [
    (23, "speed_reducer", "6", "m2"), (24, "reflective_stud", None, "ck"),
    (25, "impact_barrel", None, "ck"), (26, "flexible_delineator", None, "ck"),
    (27, "movable_island", None, "ck"), (28, "pedestrian_paving", None, "m2")]


def decimal(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not a quantity")
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name}: invalid decimal") from exc
    if not n.is_finite():
        raise ValueError(f"{name}: non-finite decimal")
    return n


def col(index):
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def station_label(value):
    s = decimal(value, "station")
    if s < 0:
        raise ValueError("Negative station requires explicit project formatting")
    s = s.quantize(Decimal("0.01"))
    km = int(s // 1000)
    rest = s - km * 1000
    digits = f"{rest:06.2f}"
    return f"Km{km}+{digits}"


def key_of(item):
    thickness = item.get("thickness_mm")
    if thickness is not None:
        thickness = format(decimal(thickness, "thickness").normalize(), "f")
    return item["item_code"], thickness


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {field}")
    return value


def _verified(item, snapshot):
    if item.get("status") != "verified" or item.get("source_snapshot_id") != snapshot:
        raise ValueError("Unverified or stale quantity/sign face")
    _text(item.get("evidence"), "readback evidence")


def build_export_plan(data: dict, manual_posts: dict[str, str] | None = None) -> dict:
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported ledger schema")
    project = data["project"]
    project_id = _text(project.get("id"), "project id")
    title = _text(project.get("title"), "project title")
    snapshot = _text(data["snapshot"].get("id"), "snapshot id")
    if data["snapshot"].get("readback_verified") is not True:
        raise ValueError("CAD readback is required before export")
    _text(data["snapshot"].get("evidence"), "snapshot evidence")
    if data.get("sign_coverage_complete") is not True:
        raise ValueError("Sign survey coverage must be explicit before exporting totals")
    segments = data["segments"]
    if not 1 <= len(segments) <= 100:
        raise ValueError("Expected 1..100 explicit quantity segments")
    ids = set()
    by_alignment = defaultdict(list)
    for s in segments:
        sid = _text(s.get("id"), "segment id")
        if sid in ids:
            raise ValueError("Duplicate segment id")
        ids.add(sid)
        a, b = decimal(s["start_m"], "segment start"), decimal(s["end_m"], "segment end")
        if a >= b:
            raise ValueError("Invalid segment bounds")
        _text(s.get("label"), "segment label")
        by_alignment[_text(s.get("alignment_id"), "alignment id")].append((a, b))
    for ranges in by_alignment.values():
        ordered = sorted(ranges)
        if any(b > c for (_, b), (c, _) in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping quantity segments on one alignment")
    mapped = {(code, thickness): (row, unit) for row, code, thickness, unit in ROWS}
    coverage = {}
    for item in data.get("coverage", []):
        k = (item["segment_id"], *key_of(item))
        if k in coverage or k[0] not in ids or k[1:] not in mapped:
            raise ValueError("Duplicate or unknown quantity coverage")
        if type(item.get("complete")) is not bool:
            raise ValueError("Coverage complete must be boolean")
        _text(item.get("evidence"), "coverage evidence")
        coverage[k] = item["complete"]
    totals = defaultdict(Decimal)
    seen = set()
    for item in data.get("quantities", []):
        _verified(item, snapshot)
        identity = _text(item.get("measurement_id"), "measurement id")
        object_id = _text(item.get("object_id"), "CAD object id")
        k = (item["segment_id"], *key_of(item))
        record_key = (object_id, *k)
        if identity in seen or record_key in seen:
            raise ValueError("Duplicate measured object/segment/item")
        seen.update((identity, record_key))
        if k[0] not in ids or k[1:] not in mapped:
            raise ValueError("Unmapped quantity; add an explicit template row mapping")
        _, unit = mapped[k[1:]]
        if item["unit"] != unit:
            raise ValueError("Quantity unit does not match template row")
        amount = decimal(item["quantity"], "quantity")
        if amount < 0 or (unit == "ck" and amount != amount.to_integral()):
            raise ValueError("Invalid measured quantity")
        method = item.get("measurement_method")
        if unit == "ck":
            allowed = {"verified_count"}
        elif k[1] == "pedestrian_paving":
            allowed = {"measured_paving_area"}
        else:
            allowed = {"actual_painted_area", "paint_union_area"}
        if method not in allowed:
            raise ValueError("Unverified measurement method")
        if k[1] == "4.4" and method != "paint_union_area":
            raise ValueError("4.4 needs verified paint union area, not gross crossed-line lengths")
        totals[k] += amount

    clusters = {}
    for c in data.get("clusters", []):
        cid = _text(c.get("cluster_id"), "cluster id")
        if cid in clusters or c.get("side") not in {"left", "median", "right"}:
            raise ValueError("Duplicate cluster or invalid side")
        _text(c.get("alignment_id"), "cluster alignment")
        _text(c.get("alignment_label"), "cluster alignment label")
        decimal(c["station_m"], "cluster station")
        clusters[cid] = c
    faces = []
    by_cluster = defaultdict(list)
    for raw in data.get("faces", []):
        _verified(raw, snapshot)
        if raw["cluster_id"] not in clusters or raw["shape"] not in SHAPES or raw["work"] not in WORK_LABELS:
            raise ValueError("Face has unknown cluster, shape or work")
        face = SignFace(raw["face_id"], raw["cluster_id"], raw["sign_code"], raw["shape"],
                        decimal(raw["width_mm"], "width"), decimal(raw["height_mm"], "height"),
                        raw["work"], raw.get("asset_id"), raw["status"], raw.get("reference"))
        faces.append(face)
        by_cluster[face.cluster_id].append(face)
    summary = sign_summary(faces)
    if any(cid not in by_cluster for cid in clusters):
        raise ValueError("Cluster without verified sign faces")
    if set(manual_posts or {}) - clusters.keys():
        raise ValueError("Preserved manual classification has a removed cluster; reconcile it before export")

    values, formulas = [], []
    def value(target, row):
        values.append({"range": target, "values": [row]})
    def formula(target, expr):
        formulas.append({"range": target, "formulas": [[expr]]})
    total_col = col(6 + len(segments))
    last_segment = col(5 + len(segments))
    value("A1", [title]); value("A2", [project.get("subtitle", "")])
    value("F4", [s["label"] for s in segments] + ["Cộng"])
    for row, code, thickness, unit in ROWS:
        for i, s in enumerate(segments, 6):
            k = (s["id"], code, thickness)
            amount = totals[k] if coverage.get(k) is True else None
            value(f"{col(i)}{row}", [float(amount) if amount is not None else "Chưa đo đủ"])
        formula(f"{total_col}{row}", f'=IF(COUNT(F{row}:{last_segment}{row})={len(segments)},SUM(F{row}:{last_segment}{row}),"Chưa đủ")')
        value(f"D{row}", ["Diện tích sơn thực đo" if unit == "m2" and row < 24 else "Khối lượng thực đo"])
    for i in range(6, 7 + len(segments)):
        cc = col(i)
        formula(f"{cc}6", f'=IF(COUNT({cc}7:{cc}22)=16,SUM({cc}7:{cc}22),"Chưa đủ")')
    marking_spec = {"name": "KL VACH SON", "clear": [f"C6:D28", f"F6:{col(max(18,6+len(segments)))}29", "F4:R5"],
                    "unmerge": [f"A1:{col(max(9,6+len(segments)))}3", "F4:R5"],
                    "merges": [f"A1:{total_col}1", f"A2:{total_col}2", f"A3:{total_col}3"] + [f"{col(i)}4:{col(i)}5" for i in range(6,7+len(segments))],
                    "values": values, "formulas": formulas,
                    "print_area": f"A1:{total_col}30", "print_titles": "4:5",
                    "print_scale": 75 if len(segments) > 3 else None,
                    "print_repeat_columns": "A:E" if len(segments) > 3 else None,
                    "style_copies": [{"source":"F4:F28", "target":f"{col(i)}4:{col(i)}28"} for i in range(7,7+len(segments))],
                    "column_widths": [{"range":f"F:{total_col}", "width":18}],
                    "number_formats": [{"range":f"F24:{total_col}27","format":"0"}],
                    "row_heights": [{"range":"4:5", "height":25}]}

    values, formulas = [], []
    value("A1", [title]); value("A2", [project.get("subtitle", "")])
    value("Q1", ["ATGT_EXPORT_V1", project_id, snapshot])
    r = 7; number = 0; last_alignment = None; detail_rows = []
    for cid, cluster in sorted(clusters.items(), key=lambda pair:(pair[1]["alignment_id"], decimal(pair[1]["station_m"], "station"), pair[0])):
        if cluster["alignment_id"] != last_alignment:
            value(f"B{r}", [cluster["alignment_label"]]); r += 1
            last_alignment = cluster["alignment_id"]
        number += 1
        items = sorted(by_cluster[cid], key=lambda f:f.face_id)
        for start in range(0, len(items), 3):
            row = [None] * 20
            row[0] = number if start == 0 else None
            row[1] = station_label(cluster["station_m"])
            row[{"left":2,"median":3,"right":4}[cluster["side"]]] = "X"
            for slot, face in enumerate(items[start:start+3]):
                row[5 + slot * 3:8 + slot * 3] = [face.sign_code, SHAPES[face.shape], dimension_label(face.width_mm, face.height_mm)]
                row[17 + slot] = face.work
            row[14] = (manual_posts or {}).get(cid) if start == 0 else None
            row[15] = "Tiếp" if start else None
            row[16] = cid
            value(f"A{r}", row); detail_rows.append(r); r += 1
    if r > 10000:
        raise ValueError("Export exceeds 10000 detail rows; split by alignment")
    detail_end = max(8, r - 1)
    summary_title, summary_header, summary_first = detail_end + 2, detail_end + 3, detail_end + 4
    summary_end = summary_first + max(1, len(summary)) - 1
    value(f"A{summary_title}", ["BẢNG TỔNG HỢP MẶT BIỂN BÁO"])
    value(f"A{summary_header}", ["STT", "Mã biển, hình dạng, kích thước và công tác"])
    value(f"H{summary_header}", ["Số lượng"])
    for n, (key, count) in enumerate(sorted(summary.items()), summary_first):
        code, shape, width, height, work = key
        dims = dimension_label(width, height)
        value(f"A{n}", [n - summary_first + 1, f"{code} — {SHAPES[shape]} — {dims} mm — {WORK_LABELS[work]}"])
        pieces = []
        for cc, sc, dc, wc in (("F","G","H","R"),("I","J","K","S"),("L","M","N","T")):
            pieces.append(f'COUNTIFS(${cc}$8:${cc}${detail_end},{quote(code)},${sc}$8:${sc}${detail_end},{quote(SHAPES[shape])},${dc}$8:${dc}${detail_end},{quote(dims)},${wc}$8:${wc}${detail_end},{quote(work)})')
        formula(f"H{n}", "=" + "+".join(pieces))
    sign_spec = {"name":"THONG KE BIEN BAO ATGT", "clear":[f"A6:T{max(170,summary_end)}"],
                 "unmerge":[f"A6:T{max(170,summary_end)}"],
                 "merges":[f"A{summary_title}:I{summary_title}", f"B{summary_header}:G{summary_header}"] + [f"H{n}:I{n}" for n in range(summary_header,summary_end+1)] + [f"B{n}:G{n}" for n in range(summary_first,summary_end+1)],
                 "values":values, "formulas":formulas, "print_area":f"A1:P{summary_end}", "print_titles":"4:5",
                 "style_copies":[{"source":"A111:I111","target":f"A{summary_header}:I{summary_header}"}] + [{"source":"A112:I112","target":f"A{n}:I{n}"} for n in range(summary_first,summary_end+1) if n != 112] + [{"source":"A8:T8", "target":f"A{n}:T{n}"} for n in detail_rows if n != 8],
                 "column_widths":[{"range":"B:B","width":20},{"range":"F:N","width":15},{"range":"P:P","width":12}],
                 "row_heights":[{"range":f"{n}:{n}","height":24} for n in detail_rows],
                 "number_formats":[{"range":f"H{summary_first}:I{summary_end}","format":"0"}],
                 "hidden_columns":"Q:T"}
    return {"schema_version":1,"template_sha256":TEMPLATE_SHA,"project_id":project_id,"snapshot_id":snapshot,
            "data_kind":data.get("data_kind", "project"), "sheets":[marking_spec,sign_spec],
            "expected":{"sign_faces":len(faces),"clusters":len(clusters),"summary_counts":[{"row":n,"quantity":count} for n,(_,count) in enumerate(sorted(summary.items()),summary_first)]},
            "manual_post_policy":"manual only, keyed by Q cluster_id, excluded from summaries"}


def dimension_label(width, height):
    def number(d):
        return format(d.normalize(), "f")
    return number(width) if width == height else f"{number(width)}x{number(height)}"


def quote(s):
    return '"' + s.replace('"', '""') + '"'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.ledger.resolve() == a.output.resolve():
        p.error("Output must differ from ledger")
    result = build_export_plan(json.loads(a.ledger.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
