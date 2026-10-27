"""Preserve native print settings after Artifact Tool authoring; read manual O.

Artifact Tool currently preserves the source EMF but drops pageSetup. This
finisher repairs that missing capability without reauthoring cell values.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import posixpath
import re
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from .export_plan import TEMPLATE_SHA

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ET.register_namespace("", NS)
ET.register_namespace("r", RNS)


def tag(name):
    return "{" + NS + "}" + name


def read_cells(z, path):
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.iter(tag("t"))) for si in root]
    result = {}
    for cell in ET.fromstring(z.read(path)).iter(tag("c")):
        v = cell.find(tag("v"))
        if cell.get("t") == "inlineStr":
            value = "".join(t.text or "" for t in cell.iter(tag("t")))
        elif cell.get("t") == "s" and v is not None:
            value = strings[int(v.text)]
        else:
            value = v.text if v is not None else None
        result[cell.get("r")] = value
    return result


def read_manual_posts(path: Path, project_id: str) -> dict[str, str]:
    with ZipFile(path) as z:
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = [s for s in workbook.find(tag("sheets")) if s.get("name") == "THONG KE BIEN BAO ATGT"]
        if len(sheets) != 1:
            raise ValueError("Previous workbook has no unique sign sheet")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rel = next((r for r in rels if r.get("Id") == sheets[0].get("{"+RNS+"}id")), None)
        if rel is None or rel.get("TargetMode") == "External":
            raise ValueError("Invalid sign worksheet relationship")
        target = rel.get("Target", "")
        part = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/"+target)
        if not part.startswith("xl/"):
            raise ValueError("Sign worksheet part outside workbook")
        cells = read_cells(z, part)
    if cells.get("Q1") != "ATGT_EXPORT_V1" or cells.get("R1") != project_id:
        raise ValueError("Previous workbook is not an ATGT export for this project")
    result = {}
    for address, cluster in cells.items():
        if re.fullmatch(r"Q[2-9]\d*|Q1\d+", address or "") and cluster:
            value = cells.get("O" + address[1:])
            if value is not None and value.strip():
                if cluster in result and result[cluster] != value:
                    raise ValueError(f"Conflicting manual pole classification for cluster {cluster}")
                result[cluster] = value
    return result


def _xml(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _coordinates(address):
    match = re.fullmatch(r"([A-Z]+)(\d+)", address)
    if not match:
        raise ValueError(f"Invalid cell address: {address}")
    column = 0
    for c in match[1]: column = column * 26 + ord(c) - 64
    return column, int(match[2])


def prepare_template(template: Path, output: Path, plan: dict):
    """Remove sample data ONLY in declared replacement ranges before import.

    Artifact Tool's clear/copy retains shared-formula group constraints. Removing
    those groups in replaced ranges is a capability workaround; business values,
    new formulas and formatting are still authored by Artifact Tool.
    """
    if template.resolve() == output.resolve():
        raise ValueError("Never overwrite the template")
    if hashlib.sha256(template.read_bytes()).hexdigest() != TEMPLATE_SHA:
        raise ValueError("Template checksum mismatch")
    with ZipFile(template) as z:
        content = {name:z.read(name) for name in z.namelist()}
    for index,spec in enumerate(plan["sheets"],1):
        path=f"xl/worksheets/sheet{index}.xml"
        root=ET.fromstring(content[path])
        bounds=[]
        for address in spec["clear"]:
            a,b=address.split(":")
            bounds.append((*_coordinates(a),*_coordinates(b)))
        # Header external links are replaced by project title/subtitle.
        bounds.extend([(1,1,1,2)])
        for cell in root.iter(tag("c")):
            c,r=_coordinates(cell.get("r"))
            if any(c1<=c<=c2 and r1<=r<=r2 for c1,r1,c2,r2 in bounds):
                for child in list(cell):
                    if child.tag in {tag("f"),tag("v"),tag("is")}:
                        cell.remove(child)
                cell.attrib.pop("t",None)
        content[path]=_xml(root)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,"w",compression=ZIP_DEFLATED) as z:
        for name,value in content.items():z.writestr(name,value)


def finish_native_features(template: Path, authored: Path, output: Path, plan: dict):
    if template.resolve() in {authored.resolve(), output.resolve()}:
        raise ValueError("Never overwrite the source template")
    if hashlib.sha256(template.read_bytes()).hexdigest() != TEMPLATE_SHA:
        raise ValueError("Template checksum mismatch")
    with ZipFile(template) as src, ZipFile(authored) as generated:
        content = {name: generated.read(name) for name in generated.namelist()}
        media_source = sorted(hashlib.sha256(src.read(n)).hexdigest() for n in src.namelist() if n.startswith("xl/media/"))
        media_result = sorted(hashlib.sha256(generated.read(n)).hexdigest() for n in generated.namelist() if n.startswith("xl/media/"))
        if media_source != media_result:
            raise ValueError("Template embedded images were not preserved")
        wb = ET.fromstring(content["xl/workbook.xml"])
        names = wb.find(tag("definedNames"))
        if names is None:
            names = ET.SubElement(wb, tag("definedNames"))
        sheets = [s.get("name") for s in wb.find(tag("sheets"))]
        removed = 0
        for n in list(names):
            ref = n.text or ""
            broken = "#REF!" in ref or "[" in ref or "#NAME?" in ref
            if n.get("name") in {"_xlnm.Print_Area", "_xlnm.Print_Titles"} or broken:
                names.remove(n); removed += int(broken)
        for index, spec in enumerate(plan["sheets"]):
            if sheets[index] != spec["name"]:
                raise ValueError("Template sheet order differs from export contract")
            quoted = "'" + spec["name"].replace("'", "''") + "'!"
            for name, ref in (("_xlnm.Print_Area", spec["print_area"]), ("_xlnm.Print_Titles", spec["print_titles"])):
                n = ET.SubElement(names, tag("definedName"), {"name":name,"localSheetId":str(index)})
                absolute = re.sub(r"([A-Z]+)(\d+)", r"$\1$\2", ref) if name.endswith("Area") else re.sub(r"(\d+)", r"$\1", ref)
                n.text = quoted + absolute
                if name.endswith("Titles") and spec.get("print_repeat_columns"):
                    n.text += "," + quoted + re.sub(r"([A-Z]+)", r"$\1", spec["print_repeat_columns"])
            path = f"xl/worksheets/sheet{index+1}.xml"
            sheet = ET.fromstring(content[path])
            errors = [c.get("r") for c in sheet.iter(tag("c")) if c.get("t") == "e"]
            if errors:
                raise ValueError(f"Formula/cell errors in {spec['name']}: {errors[:10]}")
            original = ET.fromstring(src.read(path))
            # All old validation lists belong to sample-project entries/names.
            validations = sheet.find(tag("dataValidations"))
            if validations is not None:
                sheet.remove(validations)
            for element in ("printOptions", "pageMargins", "pageSetup", "headerFooter"):
                current = sheet.find(tag(element))
                if current is not None:
                    sheet.remove(current)
                old = original.find(tag(element))
                if old is not None:
                    node = deepcopy(old)
                    node.attrib.pop("{"+RNS+"}id", None)
                    if element == "pageSetup":
                        node.attrib.pop("scale", None)
                        node.set("fitToWidth", "1"); node.set("fitToHeight", "0")
                        if spec.get("print_scale"):
                            node.set("scale",str(spec["print_scale"]))
                            node.set("pageOrder","overThenDown")
                    # These elements belong before drawing/extLst in worksheet order.
                    following = {tag(s) for s in ("rowBreaks","colBreaks","customProperties","cellWatches","ignoredErrors","smartTags","drawing","legacyDrawing","legacyDrawingHF","picture","oleObjects","controls","webPublishItems","tableParts","extLst")}
                    before = next((i for i,c in enumerate(sheet) if c.tag in following), len(sheet))
                    sheet.insert(before, node)
            props = sheet.find(tag("sheetPr"))
            if props is None:
                props = ET.Element(tag("sheetPr"));sheet.insert(0,props)
            setup = props.find(tag("pageSetUpPr"))
            if setup is None:
                setup = ET.SubElement(props,tag("pageSetUpPr"))
            setup.set("fitToPage","0" if spec.get("print_scale") else "1")
            if spec.get("hidden_columns"):
                cols = sheet.find(tag("cols"))
                if cols is None:
                    raise ValueError("Expected worksheet column definitions")
                rebuilt = []
                for c in list(cols):
                    lo,hi=int(c.get("min")),int(c.get("max"))
                    for a,b in ((lo,min(hi,16)),(max(lo,17),min(hi,20)),(max(lo,21),hi)):
                        if a<=b:
                            cc=deepcopy(c);cc.set("min",str(a));cc.set("max",str(b))
                            if 17<=a<=20:cc.set("hidden","1")
                            rebuilt.append(cc)
                cols[:]=rebuilt
            content[path] = _xml(sheet)
        content["xl/workbook.xml"] = _xml(wb)
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, suffix=".xlsx", delete=False) as temp:
        staged=Path(temp.name)
    try:
        with ZipFile(staged,"w",compression=ZIP_DEFLATED) as z:
            for name,value in content.items(): z.writestr(name,value)
        staged.replace(output)
    finally:
        if staged.exists(): staged.unlink()
    return {"embedded_images_preserved":len(media_result),"broken_defined_names_removed":removed,
            "native_page_setup_restored":True,"cached_cell_errors":0}
