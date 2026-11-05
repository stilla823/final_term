"""Scene parsing and validation for Between the Lines.

Everything here is plain Python (no Streamlit), so it can be tested on its own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SPEAKERS = ("A", "B")
LINE_RE = re.compile(r"^\s*([A-Za-z])\s*[:：]\s*(.*?)\s*$")
SHOT_COUNT = 3
SHOT_TEXT_FIELDS = ("camera_position", "placement_and_action", "acting_note", "reason")


@dataclass(frozen=True)
class Line:
    id: str       # "L1", "L2", ...
    speaker: str  # "A" or "B"
    text: str     # the words after the speaker label
    raw: str      # the line exactly as typed (outer whitespace removed)
    number: int   # 1-based line number in the text field


def cast_for(cast_count: int) -> list[str]:
    return list(SPEAKERS[:cast_count])


def _cast_phrase(cast: list[str]) -> str:
    return "A만" if len(cast) == 1 else "A와 B만"


def _short(raw: str, limit: int = 24) -> str:
    raw = raw.strip()
    return raw if len(raw) <= limit else raw[:limit] + "…"


def parse_dialogue(dialogue: str, cast_count: int) -> tuple[list[Line], list[str]]:
    """Return (lines, errors). Errors are Korean messages that name the line."""
    cast = cast_for(cast_count)
    if not dialogue.strip():
        return [], ["대사를 입력해 주세요. 한 줄에 한 마디씩 “A: 대사” 형식으로 적습니다."]

    lines: list[Line] = []
    errors: list[str] = []
    for number, raw in enumerate(dialogue.splitlines(), start=1):
        if not raw.strip():
            continue
        match = LINE_RE.match(raw)
        if not match:
            example = "“A: 대사”" if len(cast) == 1 else "“A: 대사” 또는 “B: 대사”"
            errors.append(
                f"{number}번째 줄 “{_short(raw)}”에 화자 표시가 없습니다. {example} 형식으로 써 주세요."
            )
            continue
        speaker, text = match.group(1).upper(), match.group(2)
        if speaker not in cast:
            errors.append(
                f"{number}번째 줄 “{_short(raw)}”에 선택한 인원에 없는 화자({speaker})가 있습니다. "
                f"{len(cast)}명 장면에서는 {_cast_phrase(cast)} 쓸 수 있어요."
            )
            continue
        if not text:
            errors.append(f"{number}번째 줄에 대사가 없습니다. “{speaker}:” 뒤에 대사를 적어 주세요.")
            continue
        lines.append(Line(f"L{len(lines) + 1}", speaker, text, raw.strip(), number))

    if errors:
        return [], errors
    if not lines:
        return [], ["대사를 입력해 주세요. 한 줄에 한 마디씩 “A: 대사” 형식으로 적습니다."]
    return lines, []


def snapshot(cast_count: int, dialogue: str, location: str, intention: str) -> tuple:
    """A comparable fingerprint of the form. Whitespace differences are ignored."""
    body = tuple(raw.strip() for raw in dialogue.replace("\r\n", "\n").split("\n") if raw.strip())
    return (int(cast_count), body, location.strip(), intention.strip())


def _text_ok(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_model_output(data, lines: list[Line], cast: list[str], templates: dict, angles: dict) -> list[str]:
    """Return a list of problems. An empty list means the output can be shown.

    `templates` and `angles` map id -> catalog entry.
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["응답이 JSON 객체가 아닙니다."]

    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) != SHOT_COUNT:
        got = len(shots) if isinstance(shots, list) else "없음"
        problems.append(f"샷이 정확히 {SHOT_COUNT}개여야 하는데 {got}개입니다.")
        shots = shots if isinstance(shots, list) else []

    used_ids: list[str] = []
    for i, shot in enumerate(shots, start=1):
        tag = f"샷 {i}"
        if not isinstance(shot, dict):
            problems.append(f"{tag}: 객체가 아닙니다.")
            continue

        template = templates.get(shot.get("template_id"))
        if template is None:
            problems.append(f"{tag}: 알 수 없는 구도 템플릿 ID({shot.get('template_id')!r})입니다.")

        if shot.get("angle_id") not in angles:
            problems.append(f"{tag}: 알 수 없는 앵글 ID({shot.get('angle_id')!r})입니다.")

        focus = shot.get("angle_focus")
        if focus is not None and focus not in cast:
            problems.append(f"{tag}: angle_focus({focus!r})가 등장인물에 없습니다.")

        roles = shot.get("roles")
        if not isinstance(roles, dict):
            problems.append(f"{tag}: roles가 객체가 아닙니다.")
        else:
            for char in roles:
                if char not in cast:
                    problems.append(f"{tag}: 등장인물에 없는 인물({char!r})이 있습니다.")
            if template is not None:
                values = list(roles.values())
                for role in values:
                    if role not in template["roles"]:
                        problems.append(f"{tag}: 이 템플릿에 없는 역할({role!r})입니다.")
                if len(set(values)) != len(values):
                    problems.append(f"{tag}: 같은 역할이 두 번 쓰였습니다.")
                for needed in template["required_roles"]:
                    if needed not in values:
                        problems.append(f"{tag}: 필요한 역할({needed})이 빠졌습니다.")

        for field in SHOT_TEXT_FIELDS:
            if not _text_ok(shot.get(field)):
                problems.append(f"{tag}: {field}가 비어 있습니다.")

        ids = shot.get("dialogue_line_ids")
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            problems.append(f"{tag}: dialogue_line_ids가 문자열 목록이 아닙니다.")
        else:
            used_ids.extend(ids)

    expected = [line.id for line in lines]
    if used_ids != expected:
        problems.append(f"대사 ID가 원래 대사와 맞지 않습니다. 기대: {expected}, 응답: {used_ids}.")

    suggestions = data.get("suggestions")
    for slot in ("before", "after"):
        item = suggestions.get(slot) if isinstance(suggestions, dict) else None
        if not isinstance(item, dict):
            problems.append(f"AI 연출 제안({slot})이 없습니다.")
            continue
        if item.get("kind") not in ("action", "dialogue"):
            problems.append(f"AI 연출 제안({slot}): kind는 action 또는 dialogue여야 합니다.")
        for field in ("text", "effect"):
            if not _text_ok(item.get(field)):
                problems.append(f"AI 연출 제안({slot}): {field}가 비어 있습니다.")

    assumptions = data.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(isinstance(x, str) for x in assumptions):
        problems.append("assumptions가 문자열 목록이 아닙니다.")

    return problems


def dialogue_for_shot(shot: dict, lines: list[Line]) -> list[Line]:
    """Look up the user's own lines by ID. The model never supplies dialogue text."""
    by_id = {line.id: line for line in lines}
    return [by_id[i] for i in shot["dialogue_line_ids"] if i in by_id]
