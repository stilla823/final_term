"""Live mode: a small adapter for a locally running, OpenAI-compatible model server.

Nothing else in the app knows how the model is called. Configure it outside the
source code with two environment variables:

    BTL_LLM_ENDPOINT   e.g. http://localhost:11434/v1/chat/completions   (Ollama)
    BTL_LLM_MODEL      the model name your server knows

Status: implemented and tested against a stub server only. It has not been run
against a real model yet.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

SYSTEM_PROMPT = (
    "Turn the input scene into exactly three filmable shots. Use only the characters provided. "
    "Preserve the original dialogue and its order by referencing the supplied dialogue line IDs. "
    "Choose a composition template from the supplied catalog for each shot. "
    "Choose a camera angle from the supplied catalog for each shot and say which character the angle is about. "
    "For every shot, return the template ID, character placement, camera position, visible action, acting note, "
    "and a brief reason for the directing choice. "
    "Ground the choices in the directing intention when one is provided. "
    "If you assume a location or an emotional interpretation, state the assumption. "
    "Return optional before-scene and after-scene suggestions in separate fields. "
    "Return structured JSON."
)

FORMAT_NOTES = """
Camera angle guide (conventions, not rules; pick the angle for a reason that fits the directing intention):
- low: the camera looks up. The character looks larger, powerful, in control.
- eye_level: neutral. The characters look equal.
- high: the camera looks down. The character looks smaller, vulnerable, anxious, isolated.
"roles" maps each character ID to a role of the chosen template. Use only the roles the template lists and include every required role.
"gaze" maps each character who is in the frame to what that character looks at: partner (the other character, or the empty spot where they stood), door, away (looks aside, away from the other character) or down. "actions" maps each character in the frame to one pose: stand, hold_door, reach_out, hug_self, turn_away, head_down or walk_away. The storyboard drawing shows exactly these, so the Korean descriptions must agree with them. "props" may contain "door" when the scene has a door; leave it empty otherwise.
"dialogue_line_ids" lists the supplied line IDs spoken in that shot, in order. Across the three shots every line ID must appear exactly once, in the original order. A silent shot has an empty list. Never write dialogue text yourself.
"location" is "indoor" or "outdoor": the user only chose inside or outside. If you assume a more specific place, state it in "assumptions".
Write every descriptive field in Korean. Reply with one JSON object and nothing else, shaped like this:
{
  "assumptions": ["..."],
  "shots": [
    {"template_id": "...", "angle_id": "...", "angle_focus": "A or B or null", "roles": {"A": "..."},
     "gaze": {"A": "partner"}, "actions": {"A": "stand"}, "props": [],
     "dialogue_line_ids": ["L1"], "camera_position": "...", "placement_and_action": "...",
     "acting_note": "...", "reason": "..."}
  ],
  "suggestions": {
    "before": {"kind": "action or dialogue", "text": "...", "effect": "..."},
    "after": {"kind": "action or dialogue", "text": "...", "effect": "..."}
  }
}
"""

ANGLE_HINTS = {
    "low": "camera looks up; character looks larger, powerful, in control",
    "eye_level": "neutral; characters look equal",
    "high": "camera looks down; character looks smaller, vulnerable, anxious",
}


class LiveModelError(Exception):
    """Raised with a Korean, user-facing message."""


@dataclass(frozen=True)
class LiveConfig:
    endpoint: str
    model: str
    timeout: float = 120.0


def load_config(env=None) -> LiveConfig | None:
    env = os.environ if env is None else env
    endpoint = env.get("BTL_LLM_ENDPOINT", "").strip()
    model = env.get("BTL_LLM_MODEL", "").strip()
    if not endpoint or not model:
        return None
    try:
        timeout = float(env.get("BTL_LLM_TIMEOUT", "120"))
    except ValueError:
        timeout = 120.0
    return LiveConfig(endpoint, model, timeout)


def build_messages(lines, cast, location, intention, templates: dict, angles: dict) -> list[dict]:
    scene = {
        "characters": cast,
        "location": location.strip() or None,
        "directing_intention": intention.strip() or None,
        "dialogue_lines": [{"id": l.id, "speaker": l.speaker, "text": l.text} for l in lines],
        "composition_templates": [
            {"id": t["id"], "shot_size": t["shot_size"], "roles": t["roles"], "required_roles": t["required_roles"]}
            for t in templates.values()
        ],
        "camera_angles": [
            {"id": a["id"], "meaning": ANGLE_HINTS.get(a["id"], a["effect_ko"])} for a in angles.values()
        ],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT + "\n" + FORMAT_NOTES},
        {"role": "user", "content": json.dumps(scene, ensure_ascii=False, indent=2)},
    ]


def extract_json(text: str) -> dict:
    """Parse the model's reply. Tolerates a code fence or a sentence around the object."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)  # reasoning models
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    for candidate in (cleaned, cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise LiveModelError("모델 응답을 JSON으로 읽지 못했습니다.")


def _post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never proxy a local server
    else:
        opener = urllib.request.build_opener()
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def generate(config: LiveConfig, lines, cast, location, intention, templates: dict, angles: dict, post=None) -> dict:
    """Ask the model for a storyboard. Returns the parsed, still unvalidated JSON."""
    post = post or _post
    payload = {
        "model": config.model,
        "messages": build_messages(lines, cast, location, intention, templates, angles),
        "temperature": 0.4,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    try:
        reply = post(config.endpoint, payload, config.timeout)
    except urllib.error.HTTPError as error:
        raise LiveModelError(
            f"모델 서버가 오류({error.code})를 돌려보냈습니다. 모델 이름과 주소 설정을 확인해 주세요."
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise LiveModelError(
            "라이브 AI 모드에 연결할 수 없습니다. 모델 서버가 켜져 있는지, 모델 주소와 이름 설정이 맞는지 확인하거나 예시 데모를 불러오세요."
        ) from error
    except ValueError as error:
        raise LiveModelError("모델 서버의 응답을 읽지 못했습니다.") from error
    try:
        content = reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LiveModelError("모델 응답 형식을 읽지 못했습니다.") from error
    return extract_json(content)
