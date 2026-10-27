"""Source-locked QCVN 41:2024 full-text and sign/marking knowledge importer.

Run locally with approved PDF. Text stays in local SQLite, not in public Git.
Do not equate indexed passages, drawing filenames or inferred codes with
expert-approved automatic-CAD rules.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory
from collections import Counter
from pathlib import Path
from .linetypes import parse_lin

PDF_SHA = "84825a72c4605b65485f3d31a606525a9bc96c970a5200defc0781496ddbbd46"
ANNEX = {"A":77,"B":80,"C":98,"D":115,"E":130,"F":151,"G":158,
         "I":200,"K":206,"M":214,"N":339,"O":341,"P":345}
ARTICLE = re.compile(r"(?m)^\s*Điều\s+(\d{1,2})\s*\.\s*([^\n]+)")
SIGN = re.compile(r"(?<![\w.])((?:R\.[EGH]|S\.[EGH]),\s*\d+[a-z]?|(?:DP|IE|P|W|R|I|S)\.\d{2,3}[a-z]?)(?![\w])", re.I)
MARK = re.compile(r"(?i)\bVạch\s+([1-9]\.\d{1,2}(?:\.[a-z]|[a-z])?)\b")


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def annex_of(p: int) -> str | None:
    result=None
    for label,start in ANNEX.items():
        if p >= start: result=label
        else: break
    return result


def code_normalize(value: str) -> str:
    value=re.sub(r"\s+","",value).upper()
    prefix, rest=value.split(".",1)
    if prefix in {"R","S"} and "," in rest:
        family,num=rest.split(",",1)
        return f"{prefix}.{family},{num[:-1]}{num[-1].lower()}" if num[-1].isalpha() else f"{prefix}.{family},{num}"
    return f"{prefix}.{rest[:-1]}{rest[-1].lower()}" if rest[-1].isalpha() else f"{prefix}.{rest}"


def build(pdf_path: Path, out: Path, catalog: Path | None=None, lin: Path | None=None) -> dict:
    """Publish a complete new index only after extraction and checks succeed.

    SQLite is the authoritative artifact; coverage JSON is a derived report.
    A failed build leaves the last complete database available to agents.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".build-", dir=out) as work:
        staging = Path(work)
        result = _build_unpublished(pdf_path, staging, catalog, lin)
        (staging / "atgt-knowledge.sqlite").replace(out / "atgt-knowledge.sqlite")
        (staging / "knowledge-coverage.json").replace(out / "knowledge-coverage.json")
    return result


def _catalog_assets(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data = data.get("sign_assets", data)
    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("Catalog requires asset rows")
    if data.get("total_dwg", len(assets)) != len(assets):
        raise ValueError("Catalog count mismatch")
    seen_ids, seen_paths = set(), set()
    normalized = []
    for asset in assets:
        relative = asset.get("relative_path", asset.get("source_relative_path", "")).replace("\\", "/")
        identity = asset.get("asset_id")
        checksum = asset.get("sha256", "")
        if (not relative or relative.startswith("/") or ":" in relative
                or ".." in relative.split("/") or not relative.lower().endswith(".dwg")):
            raise ValueError("Invalid relative DWG path")
        if not identity or identity in seen_ids or relative.casefold() in seen_paths:
            raise ValueError("Missing or duplicate catalog identity")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
            raise ValueError("Invalid DWG fingerprint")
        seen_ids.add(identity)
        seen_paths.add(relative.casefold())
        normalized.append({**asset, "source_relative_path": relative})
    return normalized


def _build_unpublished(pdf_path: Path, out: Path, catalog: Path | None=None, lin: Path | None=None) -> dict:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required: pip install pymupdf") from exc
    if digest(pdf_path)!=PDF_SHA:
        raise ValueError("Wrong QCVN PDF checksum; refusing to mix source versions")
    with fitz.open(pdf_path) as doc:
        if len(doc)!=403: raise ValueError("Expected exactly 403 QCVN pages")
        pages=[p.get_text(sort=True) for p in doc]
    out.mkdir(parents=True,exist_ok=True)
    dbpath=out/"atgt-knowledge.sqlite"
    if dbpath.exists(): dbpath.unlink()
    with closing(sqlite3.connect(dbpath)) as db:
        db.executescript("""
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE pages(page INTEGER PRIMARY KEY,annex TEXT,text TEXT NOT NULL,requires_visual_review INTEGER);
        CREATE VIRTUAL TABLE page_fts USING fts5(text,content='pages',content_rowid='page',tokenize='unicode61 remove_diacritics 2');
        CREATE TABLE articles(article INTEGER PRIMARY KEY,title TEXT,start_page INTEGER);
        CREATE TABLE annexes(label TEXT PRIMARY KEY,start_page INTEGER,end_page INTEGER);
        CREATE TABLE sign_index(code TEXT PRIMARY KEY,pages_json TEXT NOT NULL,count INTEGER,status TEXT);
        CREATE TABLE mark_index(code TEXT PRIMARY KEY,pages_json TEXT NOT NULL,count INTEGER,status TEXT);
        CREATE TABLE cad_assets(asset_id TEXT PRIMARY KEY,source_path TEXT,sha256 TEXT,candidate_codes_json TEXT,status TEXT);
        CREATE TABLE line_patterns(name TEXT PRIMARY KEY,description TEXT,pattern_json TEXT,source_sha256 TEXT,status TEXT);
        CREATE TABLE source_clauses(reference TEXT,page INTEGER,excerpt TEXT,status TEXT);
        CREATE INDEX clause_by_reference ON source_clauses(reference,page);
        """)
        db.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("schema_version", "1"), ("qcvn_pdf_sha256", PDF_SHA)])
        arts={}
        signs={}
        marks={}
        clauses=0
        visual=[]
        clause_rx=re.compile(r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\.\s+(.{15,})$")
        for n,txt in enumerate(pages,1):
            short=len(txt.strip())<200
            if short: visual.append(n)
            db.execute("INSERT INTO pages VALUES (?,?,?,?)",(n,annex_of(n),txt,int(short)))
            if n<=76:
                for m in ARTICLE.finditer(txt):
                    article=int(m[1])
                    if 1<=article<=84 and article not in arts:
                        arts[article]=(n," ".join(m[2].split())[:160])
                for line in txt.splitlines():
                    m=clause_rx.match(line)
                    if m:
                        db.execute("INSERT INTO source_clauses VALUES (?,?,?,?)",
                                   (m[1],n," ".join(m[2].split())[:220],"citation_only"))
                        clauses+=1
            for m in SIGN.finditer(txt):
                key=code_normalize(m[1]); signs.setdefault(key,[]).append(n)
            if 158<=n<=199:
                for m in MARK.finditer(txt):
                    key=m[1].lower()
                    key=re.sub(r"\.([a-z])$",r"\1",key)
                    marks.setdefault(key,[]).append(n)
        if set(arts)!=set(range(1,85)):
            raise ValueError(f"Article coverage gap: {set(range(1,85))-set(arts)}")
        db.execute("INSERT INTO page_fts(page_fts) VALUES ('rebuild')")
        for article,(page,title) in sorted(arts.items()):
            db.execute("INSERT INTO articles VALUES (?,?,?)",(article,title,page))
        annex_entries=list(ANNEX.items())
        for idx,(ann,start) in enumerate(annex_entries):
            end=annex_entries[idx+1][1]-1 if idx+1<len(annex_entries) else 403
            db.execute("INSERT INTO annexes VALUES (?,?,?)",(ann,start,end))
        for code,locs in signs.items():
            db.execute("INSERT INTO sign_index VALUES (?,?,?,?)",
                       (code,json.dumps(sorted(set(locs))),len(locs),"source_text_only"))
        for code,locs in marks.items():
            db.execute("INSERT INTO mark_index VALUES (?,?,?,?)",
                       (code,json.dumps(sorted(set(locs))),len(locs),"source_text_only"))
        grouped=Counter()
        candidates_single=ambiguous=unmatched=0
        if catalog is not None:
            for asset in _catalog_assets(catalog):
                path=asset["source_relative_path"]
                grouped[path.split("/")[0]]+=1
                stem=Path(path).stem
                variants=[]
                if re.fullmatch(r"\d{2,3}[a-z]?",stem,re.I):
                    variants=sorted(s for s in signs if re.fullmatch(r"(?:dp|ie|p|w|r|i|s)\."+stem,s,re.I))
                elif re.fullmatch(r"[EGH]\d{1,2}[a-z]?",stem,re.I):
                    family,num=stem[0].upper(),stem[1:]
                    prefix="R" if family=="E" else "S"
                    wanted=code_normalize(f"{prefix}.{family},{num}")
                    variants=[wanted] if wanted in signs else []
                if stem=="510": variants=sorted(s for s in signs if s.startswith("S.510"))
                if len(variants)==1: candidates_single+=1
                elif len(variants)>1: ambiguous+=1
                else: unmatched+=1
                db.execute("INSERT INTO cad_assets VALUES (?,?,?,?,?)",
                           (asset["asset_id"],path,asset["sha256"],json.dumps(variants),"unverified"))
        lin_count=0
        if lin is not None:
            for pattern in parse_lin(lin):
                db.execute("INSERT INTO line_patterns VALUES (?,?,?,?,?)",
                           (pattern.name, pattern.description, json.dumps([str(x) for x in pattern.elements_m]),
                            pattern.source_sha256, "unverified"))
                lin_count+=1
        db.commit()
        results={"qcvn_pdf_sha256":PDF_SHA,"pages":403,"articles":len(arts),"annexes":len(ANNEX),
                 "source_sign_codes":len(signs),"source_mark_codes":len(marks),
                 "clause_anchors":clauses,"needs_visual_review_pages":visual,
                 "dwg_count":sum(grouped.values()),"dwg_groups":dict(grouped),
                 "linetype_patterns":lin_count,
                 "suggested_single":candidates_single,"suggested_ambiguous":ambiguous,
                 "unmatched":unmatched,"approved_cad_rules":0,
                 "caution":"All rule/sign asset mappings remain unverified; no automated CAD write is authorised"}
        (out/"knowledge-coverage.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        db.close()
        return results


def lookup(dbfile: Path, text: str, limit: int=10) -> list[dict]:
    if not 1<=limit<=100: raise ValueError("limit out of range")
    safe='"'+text.replace('"','""')+'"'
    db=sqlite3.connect(dbfile)
    rows=db.execute("""SELECT p.page,p.annex,snippet(page_fts,0,'[',']','...',20)
        FROM page_fts JOIN pages p ON p.page=page_fts.rowid
        WHERE page_fts MATCH ? ORDER BY (CASE WHEN p.page<=76 THEN 0 ELSE 1 END),bm25(page_fts)
        LIMIT ?""",(safe,limit)).fetchall()
    db.close()
    return [{"page":p,"annex":a,"excerpt":" ".join(s.split())} for p,a,s in rows]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="action",required=True)
    b=sub.add_parser("build")
    b.add_argument("--pdf",required=True,type=Path)
    b.add_argument("--out",required=True,type=Path)
    b.add_argument("--catalog",type=Path)
    b.add_argument("--lin",type=Path)
    s=sub.add_parser("search")
    s.add_argument("--db",required=True,type=Path)
    s.add_argument("--text",required=True)
    a=ap.parse_args()
    if a.action=="build": result=build(a.pdf,a.out,a.catalog,a.lin)
    else:result=lookup(a.db,a.text)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
