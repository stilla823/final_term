"""Decides what the page should show. Plain Python so every branch can be tested.

app.py only draws what this module returns.
"""
from __future__ import annotations

import json
from pathlib import Path

import model_adapter
import scene

NOT_CONFIGURED = (
    "라이브 AI 모드는 내 컴퓨터에서 돌아가는 AI 모델이 있어야 쓸 수 있어요. "
    "지금은 모델 설정이 없어서 만들지 못했습니다. 아래 ‘라이브 모드 설정 방법’을 보거나 예시 데모를 불러오세요."
)

LIVE_SETUP_HELP = """라이브 모드는 **내 컴퓨터에서 돌아가는 AI 모델**이 있어야 쓸 수 있어요. 처음 한 번만 설정하면 됩니다.

1. [ollama.com](https://ollama.com)에서 Ollama를 설치하고 실행합니다.
2. 터미널(Windows는 PowerShell)에서 모델을 내려받습니다. 아래 모델 이름은 예시예요. 쓰기 전에 모델의 라이선스와 한국어 성능을 직접 확인하세요.

   `ollama pull qwen3:8b`
3. **앱을 실행할 같은 터미널에서** 주소와 모델 이름을 설정합니다.

   macOS / Linux:

   `export BTL_LLM_ENDPOINT=http://localhost:11434/v1/chat/completions`

   `export BTL_LLM_MODEL=qwen3:8b`

   Windows PowerShell:

   `$env:BTL_LLM_ENDPOINT = "http://localhost:11434/v1/chat/completions"`

   `$env:BTL_LLM_MODEL = "qwen3:8b"`
4. 같은 터미널에서 `streamlit run app.py`를 다시 실행하고, 라이브 AI 모드를 켠 뒤 ‘스토리보드 만들기’를 누릅니다.

설정하지 않아도 ‘예시 불러오기’로 데모 모드는 쓸 수 있어요."""
BAD_FORMAT = "스토리보드를 만들지 못했습니다. 모델 응답이 형식에 맞지 않았어요. 다시 시도하거나 예시 데모를 불러오세요."


def load_catalogs(data_dir: Path) -> dict:
    read = lambda name: json.loads((data_dir / name).read_text(encoding="utf-8"))
    demo, templates, grammar = read("demo.json"), read("templates.json"), read("camera_grammar.json")
    return {
        "demo": demo,
        "templates": {t["id"]: t for t in templates["templates"]},
        "angles": {a["id"]: a for a in grammar["angles"]},
        "angle_order": [a["id"] for a in grammar["angles"]],
        "disclaimer": grammar["disclaimer_ko"],
    }


def sample_snapshot(catalogs: dict) -> tuple:
    s = catalogs["demo"]["sample"]
    return scene.snapshot(s["cast_count"], s["dialogue"], s["location"], s["intention"])


def make_output(cast_count, dialogue, location, intention, live, catalogs,
                load_config=model_adapter.load_config, generate=model_adapter.generate) -> dict:
    """Return an output dict. `kind` is one of: invalid, demo_custom, live_error, live_invalid, result."""
    snap = scene.snapshot(cast_count, dialogue, location, intention)
    lines, errors = scene.parse_dialogue(dialogue, cast_count)
    if errors:
        return {"kind": "invalid", "errors": errors, "snapshot": snap}

    cast = scene.cast_for(cast_count)

    if not live:
        if snap != sample_snapshot(catalogs):
            # Never show the saved storyboard as if it were made for edited input.
            return {"kind": "demo_custom", "snapshot": snap}
        return {"kind": "result", "mode": "demo", "model": None, "snapshot": snap,
                "data": catalogs["demo"]["result"], "lines": lines}

    config = load_config()
    if config is None:
        return {"kind": "live_error", "message": NOT_CONFIGURED, "snapshot": snap}
    try:
        data = generate(config, lines, cast, location, intention, catalogs["templates"], catalogs["angles"])
    except model_adapter.LiveModelError as error:
        return {"kind": "live_error", "message": str(error), "snapshot": snap}
    problems = scene.validate_model_output(data, lines, cast, catalogs["templates"], catalogs["angles"])
    if problems:
        return {"kind": "live_invalid", "message": BAD_FORMAT, "problems": problems, "snapshot": snap}
    return {"kind": "result", "mode": "live", "model": config.model, "snapshot": snap,
            "data": data, "lines": lines}
