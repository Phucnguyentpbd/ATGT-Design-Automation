"""Inspect a COPY of a DWG in isolated AutoCAD 2027 Core Console (no live MCP).

Requires a Release build of cad/AtgtInspection. Source hash is verified after
the process exits. A timeout terminates only the child Core Console we own.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output-root", type=Path, default=Path("local-manifests/cad"))
    ap.add_argument("--autocad-root", type=Path, default=Path(r"C:\Program Files\Autodesk\AutoCAD 2027"))
    args = ap.parse_args()
    source = args.source.resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    plugin = root / "cad/AtgtInspection/bin/Release/net10.0-windows/AtgtInspection.dll"
    if not plugin.is_file():
        raise SystemExit("Build cad/AtgtInspection/AtgtInspection.csproj first")
    folder = (args.output_root / uuid.uuid4().hex[:12]).resolve()
    folder.mkdir(parents=True)
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    copy = folder / "source-copy.dwg"
    shutil.copyfile(source, copy)
    if hashlib.sha256(copy.read_bytes()).hexdigest() != checksum:
        raise RuntimeError("Source changed while copying; retry when stable")
    output = folder / "inspection.json"
    script = folder / "inspect.scr"
    script.write_text(f'_NETLOAD\n"{plugin.as_posix()}"\nATGTINSPECT\n_QUIT\n', encoding="ascii")
    env = {**os.environ, "ATGT_INSPECT_SOURCE": str(copy), "ATGT_INSPECT_OUTPUT": str(output)}
    failure = None
    exit_code = None
    with (folder / "console.log").open("wb") as log:
        # /isolate supplies a temporary user data directory/profile. Installed
        # vertical modules may still load; this does not guarantee fast startup.
        try:
            result = subprocess.run([str(args.autocad_root / "accoreconsole.exe"),
                                     "/s", str(script), "/product", "ACAD", "/l", "en-US", "/isolate",
                                     "ATGTInspection_" + folder.name, str(folder / "profile")],
                                    env=env, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            failure = "30-second timeout; owned Core Console process terminated"
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    evidence = {"source": str(source), "source_sha256_before": checksum,
                "source_sha256_after": after, "source_unchanged": checksum == after,
                "inspection": str(output), "exit_code": exit_code, "failure": failure}
    (folder / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))
    if not output.exists() or checksum != after or exit_code != 0:
        raise SystemExit("Inspection incomplete; see console.log and evidence.json")


if __name__ == "__main__":
    main()
