"""Versioned SQLite rule registry. Draft rules cannot be executed."""
from __future__ import annotations

import json
import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    source_sha256: str
    citation: str
    road_types: tuple[str, ...]
    payload: dict[str, Any]
    status: str
    reviewer: str | None = None


class RuleStore:
    def __init__(self, db_path: str | Path):
        self.connection = sqlite3.connect(str(db_path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT NOT NULL, version INTEGER NOT NULL,
                source_sha256 TEXT NOT NULL, citation TEXT NOT NULL,
                road_types_json TEXT NOT NULL, payload_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('draft','approved','retired')),
                reviewer TEXT, PRIMARY KEY(rule_id,version))
        """)
        self.connection.commit()

    def close(self):
        self.connection.close()

    def add_draft(self, rule_id: str, version: int, source_sha256: str,
                  citation: str, road_types: tuple[str, ...], payload: dict) -> None:
        if not rule_id or version < 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256) or not citation:
            raise ValueError("Draft requires ID, version, SHA-256 source and citation")
        if not road_types or any(r not in {"ordinary", "divided_rural", "urban", "expressway"} for r in road_types):
            raise ValueError("Invalid road scope")
        try:
            with self.connection:
                self.connection.execute("""INSERT INTO rules
                    (rule_id,version,source_sha256,citation,road_types_json,payload_json,status)
                    VALUES (?,?,?,?,?,?,'draft')""", (rule_id, version, source_sha256, citation,
                        json.dumps(road_types), json.dumps(payload, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Rule version already exists; create a new version") from exc

    def approve(self, rule_id: str, version: int, reviewer: str, source_checked: bool = False) -> None:
        """Requires explicit specialist review; never automatic ingestion."""
        if not reviewer.strip() or not source_checked:
            raise ValueError("Specialist review of source/table/figures required")
        with self.connection:
            cur = self.connection.execute("""UPDATE rules SET status='approved',reviewer=?
                WHERE rule_id=? AND version=? AND status='draft'""", (reviewer, rule_id, version))
            if cur.rowcount != 1:
                raise ValueError("Missing or non-draft rule")

    def get(self, rule_id: str, version: int) -> Rule | None:
        row = self.connection.execute("SELECT * FROM rules WHERE rule_id=? AND version=?", (rule_id, version)).fetchone()
        return None if row is None else self._from_row(row)

    def search(self, term: str, include_drafts: bool = True) -> list[Rule]:
        rows = self.connection.execute("SELECT * FROM rules ORDER BY rule_id,version").fetchall()
        return [self._from_row(row) for row in rows if (include_drafts or row["status"] == "approved")
                and (term.casefold() in row["rule_id"].casefold() or term.casefold() in row["citation"].casefold())]

    def executable(self, road_type: str) -> list[Rule]:
        """Never execute urban/expressway rules in the first automation release."""
        if road_type not in {"ordinary", "divided_rural"}:
            return []
        # Select the version before filtering its road scope. A new approved
        # version may deliberately remove a road type from the previous scope.
        rows = self.connection.execute("""SELECT r.* FROM rules r
            WHERE r.status='approved' AND r.version=(SELECT MAX(v.version)
                FROM rules v WHERE v.rule_id=r.rule_id AND v.status='approved')
            ORDER BY r.rule_id""").fetchall()
        return [r for row in rows if road_type in (r := self._from_row(row)).road_types]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Rule:
        return Rule(row["rule_id"], row["version"], row["source_sha256"], row["citation"],
                    tuple(json.loads(row["road_types_json"])), json.loads(row["payload_json"]),
                    row["status"], row["reviewer"])
