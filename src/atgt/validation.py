"""Fail-closed preflight: unverified rules/assets cannot trigger CAD."""
import re
from dataclasses import dataclass
from .contracts import ProjectContext, SignFace

SIGN_RE = re.compile(r"^(?:[A-Z]+(?:\.[A-Z]+)?)\.[A-Za-z0-9,.-]+$")
ALLOWED_AUTOMATION = {"ordinary", "divided_rural"}

@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    severity: str = "blocked"

def validate_sign_code(code: str) -> bool:
    return bool(SIGN_RE.fullmatch(code)) and not code.split(".")[0].isdigit()

def validate_project(context: ProjectContext) -> list[Issue]:
    errors = []
    if not context.source_locks:
        errors.append(Issue("missing_sources", "No locked source versions"))
    if not context.snapshot_id:
        errors.append(Issue("missing_snapshot", "No verified drawing snapshot"))
    for s in context.segments:
        if s.road_type not in ALLOWED_AUTOMATION:
            errors.append(Issue("unsupported_road_type", f"{s.segment_id}: {s.road_type}"))
        if not s.direction_evidence:
            errors.append(Issue("missing_direction", f"{s.segment_id}: traffic direction lacks evidence"))
    return errors

def validate_faces(faces: list[SignFace]) -> list[Issue]:
    issues = []
    ids = set()
    for face in faces:
        if face.face_id in ids:
            issues.append(Issue("duplicate_face", face.face_id))
        ids.add(face.face_id)
        if not validate_sign_code(face.sign_code):
            issues.append(Issue("noncanonical_code", face.sign_code))
        if face.width_mm <= 0 or face.height_mm <= 0:
            issues.append(Issue("invalid_dimensions", face.face_id))
        if not face.asset_id or not face.reference or face.status != "verified":
            issues.append(Issue("unverified_face", face.face_id))
    return issues
