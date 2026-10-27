"""Read-only, source-bound facade used by MCP. No CAD/file writer is exposed."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3

from .box44_rules import propose_boxes
from .edge_rules import context_from_dict, propose_edge_marking
from .linetypes import parse_lin
from .project_rules import ProjectRules
from .qcvn_ingest import PDF_SHA, code_normalize, digest
from .sign_placement_rules import (
    TCVN_4054_PDF_SHA,
    junction_context_from_dict,
    propose_junction_warnings,
    propose_sign_position,
    sign_context_from_dict,
)
from .validation import validate_sign_code

LIN_SHA = "e4484f094b128c53914b91b1c88bfc6b8b6263452a6767c1346f8427a3b15c99"


class ATGTService:
    def __init__(self, db_path: Path, lin_path: Path, lin_sha256: str = LIN_SHA,
                 tcvn4054_path: Path | None = None,
                 tcvn4054_sha256: str = TCVN_4054_PDF_SHA,
                 project_rules_path: Path | None = None):
        self.db_path = db_path.resolve(strict=True)
        self.lin_path = lin_path.resolve(strict=True)
        self.db_sha = digest(self.db_path)
        self.lin_sha = digest(self.lin_path)
        if self.lin_sha != lin_sha256:
            raise ValueError("LIN checksum mismatch; verify the configured library version")
        self.tcvn4054_path = tcvn4054_path.resolve(strict=True) if tcvn4054_path else None
        self.tcvn4054_sha = digest(self.tcvn4054_path) if self.tcvn4054_path else None
        if self.tcvn4054_sha is not None and self.tcvn4054_sha != tcvn4054_sha256:
            raise ValueError("TCVN 4054 checksum mismatch; verify the configured source version")
        self.project_rules = ProjectRules(project_rules_path) if project_rules_path else None
        self.patterns = parse_lin(self.lin_path)
        with self._db() as db:
            try:
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
            except sqlite3.OperationalError as exc:
                raise ValueError("Index has no source metadata; rebuild with atgt.qcvn_ingest") from exc
        if metadata.get("schema_version") != "1" or metadata.get("qcvn_pdf_sha256") != PDF_SHA:
            raise ValueError("Knowledge index is not bound to the locked QCVN 41:2024 PDF")

    @contextmanager
    def _db(self):
        if self.project_rules is not None:
            self.project_rules.assert_unchanged()
        tcvn_changed = (self.tcvn4054_path is not None and
                        digest(self.tcvn4054_path) != self.tcvn4054_sha)
        if digest(self.db_path) != self.db_sha or digest(self.lin_path) != self.lin_sha or tcvn_changed:
            raise ValueError("Configured sources changed; restart after verifying the new source versions")
        db = sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            yield db
        finally:
            db.close()

    def _envelope(self, **result):
        rules = self.project_rules.summary() if self.project_rules is not None else None
        return {"schema_version": 1, "cad_execution_allowed": False,
                "sources": {"pdf_sha256": PDF_SHA, "knowledge_sha256": self.db_sha,
                            "lin_sha256": self.lin_sha,
                            "tcvn4054_pdf_sha256": self.tcvn4054_sha,
                            "project_rules_sha256": rules["sha256"] if rules else None,
                            "project_ruleset_id": rules["ruleset_id"] if rules else None}, **result}

    @staticmethod
    def _page(items, total, offset, limit):
        more = offset + len(items) < total
        return {"items": items, "total_count": total, "has_more": more,
                "next_offset": offset + limit if more else None}

    def status(self):
        with self._db() as db:
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                      for name in ("pages", "articles", "cad_assets", "line_patterns")}
        return self._envelope(status="ready_read_only", counts=counts,
                              design_status="proposal_only", live_cad_verified=False,
                              scope=["ordinary", "divided_rural"],
                              project_rules=self.project_rules.summary() if self.project_rules else {
                                  "loaded": False,
                                  "reason": "Configure --rules before evaluating project rules"})

    def get_project_rules(self, section: str = "all"):
        with self._db():
            pass
        if self.project_rules is None:
            raise ValueError("Project rules are not configured; start the server with --rules")
        return self._envelope(
            ruleset_id=self.project_rules.ruleset_id,
            section=section,
            rules=self.project_rules.get(section),
            interpretation=("User-approved project rules; keep their provenance distinct from "
                            "QCVN/TCVN source requirements"))

    def search(self, query: str, limit: int = 5, offset: int = 0):
        query = query.strip()
        if not 1 <= len(query) <= 200 or not 1 <= limit <= 20 or not 0 <= offset <= 10000:
            raise ValueError("Use a nonempty query <=200 characters, limit 1..20 and offset 0..10000")
        # Literal phrase only; caller input is not FTS syntax or SQL.
        phrase = '"' + query.replace('"', '""') + '"'
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) FROM page_fts WHERE page_fts MATCH ?", (phrase,)).fetchone()[0]
            rows = db.execute("""SELECT p.page,p.annex,p.requires_visual_review,
                snippet(page_fts,0,'[',']','...',32) AS excerpt
                FROM page_fts JOIN pages p ON p.page=page_fts.rowid
                WHERE page_fts MATCH ? ORDER BY rank,p.page LIMIT ? OFFSET ?""",
                (phrase, limit, offset)).fetchall()
        items = [dict(r) | {"reference": f"page:{r['page']}", "status": "source_text_only"} for r in rows]
        return self._envelope(**self._page(items, total, offset, limit))

    def get(self, kind: str, key: str, offset: int = 0, limit: int = 4000):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 6000:
            raise ValueError("Text window must use offset 0..100000 and limit 1..6000")
        with self._db() as db:
            if kind == "page":
                if not key.isdigit() or not 1 <= int(key) <= 403:
                    raise ValueError("Page key must be a PDF page number from 1 to 403")
                row = db.execute("SELECT * FROM pages WHERE page=?", (int(key),)).fetchone()
                if row is None:
                    return self._envelope(found=False)
                text = row["text"]
                result = dict(row)
                result["text"] = text[offset:offset+limit]
                result.update(total_chars=len(text), has_more=offset+limit < len(text),
                              next_offset=offset+limit if offset+limit < len(text) else None)
            elif kind in {"sign", "marking"}:
                if kind == "sign":
                    if not validate_sign_code(key):
                        raise ValueError("Use the full canonical sign code, e.g. P.102")
                    key = code_normalize(key)
                elif not re.fullmatch(r"[1-9]\.\d{1,2}(?:\.[a-z]|[a-z])?", key):
                    raise ValueError("Invalid marking code; use e.g. 3.1a or 4.4")
                table = "sign_index" if kind == "sign" else "mark_index"
                row = db.execute(f"SELECT * FROM {table} WHERE code=?", (key,)).fetchone()
                if row is None:
                    return self._envelope(found=False)
                result = dict(row)
                result["pages"] = json.loads(result.pop("pages_json"))
            else:
                raise ValueError("Unknown source kind; use page, sign or marking")
        return self._envelope(found=True, kind=kind, record=result,
                              interpretation="Source evidence only; inspect figures and review the applicable rule")

    def resolve_asset(self, sign_code: str, limit: int = 10, offset: int = 0):
        if not validate_sign_code(sign_code):
            raise ValueError("Use the full canonical sign code, e.g. P.102")
        if not 1 <= limit <= 20 or not 0 <= offset <= 10000:
            raise ValueError("Use limit 1..20 and offset 0..10000")
        with self._db() as db:
            args = (sign_code,)
            where = "EXISTS (SELECT 1 FROM json_each(candidate_codes_json) WHERE value=?)"
            total = db.execute(f"SELECT COUNT(*) FROM cad_assets WHERE {where}", args).fetchone()[0]
            rows = db.execute(f"SELECT * FROM cad_assets WHERE {where} ORDER BY asset_id LIMIT ? OFFSET ?",
                              args + (limit, offset)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["candidate_codes"] = json.loads(item.pop("candidate_codes_json"))
            items.append(item)
        return self._envelope(**self._page(items, total, offset, limit), resolution="blocked",
                              reason="Filename candidates require sign mapping, units, orientation and geometry review")

    def evaluate(self, request: dict):
        # Keep source version check even when no text lookup is required.
        with self._db():
            pass
        if self.project_rules is None:
            raise ValueError("Project rules are not configured; load the versioned ruleset before evaluation")
        if request["kind"] == "edge":
            items = request["intervals"]
            proposals = [propose_edge_marking(context_from_dict(item), self.patterns) for item in items]
        elif request["kind"] == "box44":
            items = request["junctions"]
            proposals = []
            for item in deepcopy(items):
                for b in item["branches"]:
                    for key in ("minS", "midS", "maxS", "avgW"):
                        b[key] = float(b[key])
                item["width_m"] = float(item.get("width_m", .20))
                proposals.append(propose_boxes(**item))
        elif request["kind"] == "sign_placement":
            items = request["signs"]
            proposals = [propose_sign_position(
                sign_context_from_dict(item), tcvn_source_verified=self.tcvn4054_sha is not None)
                for item in items]
        else:
            items = request["corridors"]
            proposals = [propose_junction_warnings(
                junction_context_from_dict(item), tcvn_source_verified=self.tcvn4054_sha is not None)
                for item in items]
        snapshots = {item["snapshot_id"] for item in items}
        if len(snapshots) != 1:
            raise ValueError("One evaluation batch must use one drawing snapshot")
        return self._envelope(kind=request["kind"], snapshot_id=next(iter(snapshots)),
                              proposals=proposals, blocked_count=sum(p["status"] == "blocked" for p in proposals))

    def validate_plan(self, request: dict, candidate: dict):
        expected = self.evaluate(request)
        matches = candidate == expected
        issues = [] if matches else ["plan_differs_from_recomputed_rules_or_source_snapshot"]
        if expected["blocked_count"]:
            issues.append("one_or_more_contexts_lack_required_evidence")
        return self._envelope(matches_recomputed_plan=matches,
                              ready_for_geometry_review=not issues, issues=issues,
                              pending=["native_curve_geometry", "asset_geometry_review",
                                       "independent_design_review", "CAD_readback"],
                              validation_level="proposal_consistency_only")
