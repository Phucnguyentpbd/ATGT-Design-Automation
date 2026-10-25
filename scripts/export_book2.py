"""Export a verified ledger through Artifact Tool, preserving Book2 native printing.

Supply bundled Python/Node runtimes. --previous preserves only manual pole values
from an earlier ATGT export with the same project id, keyed by stable cluster ID.
"""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from atgt.book2_package import prepare_template, finish_native_features, read_manual_posts
from atgt.export_plan import build_export_plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",required=True,type=Path)
    p.add_argument("--template",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--node",required=True,type=Path)
    p.add_argument("--node-runtime",required=True,type=Path)
    p.add_argument("--previous",type=Path)
    p.add_argument("--evidence-dir",type=Path,default=Path("local-manifests/export"))
    a=p.parse_args()
    if a.output.resolve() in {a.template.resolve(),a.ledger.resolve(),a.previous.resolve() if a.previous else None}:
        p.error("Output must differ from all input files; use a distinct output version")
    data=json.loads(a.ledger.read_text(encoding="utf-8"))
    manual=read_manual_posts(a.previous,data["project"]["id"]) if a.previous else {}
    plan=build_export_plan(data,manual)
    a.evidence_dir.mkdir(parents=True,exist_ok=True)
    # Evidence remains reusable for troubleshooting, including rendered previews.
    with TemporaryDirectory(prefix="book2-",dir=a.evidence_dir) as temp:
        work=Path(temp);prepared=work/"prepared.xlsx";authored=work/"authored.xlsx"
        planfile=work/"plan.json";planfile.write_text(json.dumps(plan,ensure_ascii=False),encoding="utf-8")
        prepare_template(a.template,prepared,plan)
        builder=Path(__file__).with_suffix(".mjs")
        subprocess.run([str(a.node),str(builder),str(a.template),str(planfile),str(authored),str(a.node_runtime),str(prepared)],check=True,timeout=120)
        proof=finish_native_features(a.template,authored,a.output,plan)
        for file in work.glob("*.png"):
            (a.evidence_dir/file.name).write_bytes(file.read_bytes())
        (a.evidence_dir/"plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
        (a.evidence_dir/"formula-inventory.ndjson").write_bytes(Path(str(authored)+".formulas.ndjson").read_bytes())
    proof.update({"output":str(a.output.resolve()),"data_kind":data.get("data_kind","project"),
                  "expected":plan["expected"],"manual_clusters_preserved":len(manual),"native_excel_verified":False})
    (a.evidence_dir/"export-evidence.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False))


if __name__ == "__main__":main()
