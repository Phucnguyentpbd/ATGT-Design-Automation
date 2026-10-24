"""Preview edge-marking rules: python -m atgt.planning_cli --input contexts.json --lin library.lin --output plan.json"""
import argparse
import json
from pathlib import Path
from .edge_rules import context_from_dict, propose_edge_marking
from .linetypes import parse_lin
from .box44_rules import propose_boxes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--kind", choices=("edge", "box44"), default="edge")
    p.add_argument("--lin", type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.output.resolve() in {a.input.resolve(), a.lin.resolve() if a.lin else None}:
        p.error("Output must differ from input sources")
    items = json.loads(a.input.read_text(encoding="utf-8"), parse_float=str)
    patterns = []
    if a.kind == "edge":
        if a.lin is None:
            p.error("--kind edge requires --lin")
        patterns = parse_lin(a.lin)
        proposals = [propose_edge_marking(context_from_dict(item), patterns) for item in items["intervals"]]
    else:
        proposals = []
        for item in items["junctions"]:
            for branch in item["branches"]:
                for key in ("minS", "midS", "maxS", "avgW"):
                    if isinstance(branch[key], str):
                        branch[key] = float(branch[key])
            if isinstance(item.get("width_m"), str):
                item["width_m"] = float(item["width_m"])
            proposals.append(propose_boxes(**item))
    result = {"schema_version": 1, "cad_execution_allowed": False,
              "lin_sha256": patterns[0].source_sha256 if patterns else None,
              "proposals": proposals}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(proposals)} proposals; {sum(p['status'] == 'blocked' for p in proposals)} blocked; no CAD writes")


if __name__ == "__main__":
    main()
