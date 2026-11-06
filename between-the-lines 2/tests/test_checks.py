"""Checks for everything that does not need Streamlit.

Run with:  python tests/test_checks.py      (or: python -m pytest tests)
"""
import base64
import copy
import hashlib
import shutil
import subprocess
import tempfile
import json
import py_compile
import re
import sys
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cards  # noqa: E402
import model_adapter  # noqa: E402
import pipeline  # noqa: E402
import scene  # noqa: E402
import sketch  # noqa: E402
import storyboard  # noqa: E402

CAT = pipeline.load_catalogs(ROOT / "data")
SAMPLE = CAT["demo"]["sample"]
DEMO = CAT["demo"]["result"]
CONFIG = model_adapter.LiveConfig("http://localhost:1/v1/chat/completions", "stub-model")


def sample_lines():
    lines, errors = scene.parse_dialogue(SAMPLE["dialogue"], 2)
    assert errors == []
    return lines


# ------------------------------------------------------------ dialogue input

def test_sample_parses_and_keeps_text_exactly():
    lines = sample_lines()
    assert [l.id for l in lines] == ["L1", "L2"]
    assert lines[0].raw == "A: 너도 같이 갈래?"
    assert lines[1].raw == "B: 괜찮아. 먼저 가."


def test_empty_dialogue():
    for blank in ("", "   \n  \n"):
        lines, errors = scene.parse_dialogue(blank, 2)
        assert lines == [] and len(errors) == 1 and "대사를 입력" in errors[0]


def test_missing_speaker_label_names_the_line():
    _, errors = scene.parse_dialogue("A: 안녕\n다음에 보자", 2)
    assert len(errors) == 1 and "2번째 줄" in errors[0] and "화자 표시가 없습니다" in errors[0]


def test_speaker_outside_cast_two_characters():
    _, errors = scene.parse_dialogue("A: 안녕\nC: 나도 있어", 2)
    assert len(errors) == 1
    assert "2번째 줄" in errors[0] and "(C)" in errors[0] and "A와 B만" in errors[0]


def test_speaker_b_not_allowed_in_one_character_scene():
    _, errors = scene.parse_dialogue("A: 안녕\nB: 응", 1)
    assert len(errors) == 1 and "2번째 줄" in errors[0] and "A만" in errors[0]


def test_one_character_scene_ok():
    lines, errors = scene.parse_dialogue("A: 혼잣말\nA: 또 혼잣말", 1)
    assert errors == [] and len(lines) == 2


def test_two_character_scene_with_silent_b_is_allowed():
    lines, errors = scene.parse_dialogue("A: 거기 있어?\nA: 대답 좀 해 줘.", 2)
    assert errors == [] and {l.speaker for l in lines} == {"A"}


def test_every_bad_line_is_reported_with_its_own_number():
    _, errors = scene.parse_dialogue("A: 안녕\n안녕\nC: 응\nB:", 2)
    assert len(errors) == 3
    assert "2번째 줄" in errors[0] and "3번째 줄" in errors[1] and "4번째 줄" in errors[2]


def test_blank_lines_are_skipped_but_numbers_stay_true():
    _, errors = scene.parse_dialogue("A: 안녕\n\n\nC: 응", 2)
    assert "4번째 줄" in errors[0]


def test_lowercase_and_fullwidth_colon_accepted_text_kept():
    lines, errors = scene.parse_dialogue("a：안녕: 반가워", 2)
    assert errors == [] and lines[0].speaker == "A" and lines[0].text == "안녕: 반가워"


def test_snapshot_ignores_whitespace_only_changes():
    a = scene.snapshot(2, "A: 안녕\nB: 응", " 복도 ", "")
    b = scene.snapshot(2, "A: 안녕  \r\n\nB: 응\n", "복도", "  ")
    assert a == b
    assert a != scene.snapshot(2, "A: 안녕\nB: 응!", "복도", "")
    assert a != scene.snapshot(1, "A: 안녕\nB: 응", "복도", "")


# ------------------------------------------------------------ saved demo

def test_saved_demo_is_valid_and_matches_the_brief():
    lines = sample_lines()
    assert scene.validate_model_output(DEMO, lines, ["A", "B"], CAT["templates"], CAT["angles"]) == []
    shots = DEMO["shots"]
    assert [s["template_id"] for s in shots] == ["medium_two_shot", "ots_close_up", "wide_empty_space"]
    assert [s["dialogue_line_ids"] for s in shots] == [["L1"], ["L2"], []]   # last shot is silent
    assert "“괜찮아.” 뒤에서 잠깐 멈추고" in shots[1]["acting_note"]
    assert DEMO["suggestions"]["before"]["kind"] == "action"
    assert "같이 가고 싶었는데." in DEMO["suggestions"]["after"]["text"]


def test_demo_angles_follow_the_directing_intention():
    angles = [s["angle_id"] for s in DEMO["shots"]]
    assert angles == ["eye_level", "high", "high"]      # equal, then B looks small and anxious
    assert DEMO["shots"][1]["angle_focus"] == "B"


def test_dialogue_comes_from_the_users_input():
    lines = sample_lines()
    shown = [[l.raw for l in scene.dialogue_for_shot(s, lines)] for s in DEMO["shots"]]
    assert shown == [["A: 너도 같이 갈래?"], ["B: 괜찮아. 먼저 가."], []]


# ------------------------------------------------------------ model output validation

def check(mutate):
    data = copy.deepcopy(DEMO)
    mutate(data)
    return scene.validate_model_output(data, sample_lines(), ["A", "B"], CAT["templates"], CAT["angles"])


def test_validation_rejects_wrong_shot_count():
    assert check(lambda d: d["shots"].pop())
    assert check(lambda d: d["shots"].append(copy.deepcopy(d["shots"][0])))


def test_validation_rejects_unknown_ids():
    assert check(lambda d: d["shots"][0].update(template_id="nope"))
    assert check(lambda d: d["shots"][0].update(angle_id="dutch"))
    assert check(lambda d: d["shots"][0].update(roles={"C": "left", "A": "right"}))
    assert check(lambda d: d["shots"][0].update(angle_focus="C"))
    assert check(lambda d: d["shots"][0].update(roles={"B": "figure", "A": "right"}))
    assert check(lambda d: d["shots"][0].update(roles={"B": "left"}))   # required role missing


def test_validation_rejects_bad_dialogue_references():
    assert check(lambda d: d["shots"][0].update(dialogue_line_ids=[]))                  # line dropped
    assert check(lambda d: d["shots"][2].update(dialogue_line_ids=["L2"]))              # line used twice
    assert check(lambda d: (d["shots"][0].update(dialogue_line_ids=["L2"]),
                            d["shots"][1].update(dialogue_line_ids=["L1"])))            # order swapped
    assert check(lambda d: d["shots"][0].update(dialogue_line_ids=["L1", "L9"]))        # unknown line


def test_validation_rejects_missing_text_and_suggestions():
    assert check(lambda d: d["shots"][1].update(acting_note=" "))
    assert check(lambda d: d["suggestions"].pop("after"))
    assert check(lambda d: d["suggestions"]["before"].update(kind="poem"))
    assert scene.validate_model_output("nope", sample_lines(), ["A", "B"], CAT["templates"], CAT["angles"])


# ------------------------------------------------------------ what the page shows

def make(cast, dialogue, location, intention, live=False, **kw):
    return pipeline.make_output(cast, dialogue, location, intention, live, CAT, **kw)


def sample_args():
    return (SAMPLE["cast_count"], SAMPLE["dialogue"], SAMPLE["location"], SAMPLE["intention"])


def test_demo_mode_shows_saved_result_for_the_unchanged_sample():
    out = make(*sample_args())
    assert out["kind"] == "result" and out["mode"] == "demo" and out["data"] is DEMO
    assert "데모 모드 · 저장된 예시 결과" in cards.result_badge("demo")


def test_demo_mode_never_returns_saved_result_for_edited_input():
    cast, dialogue, location, intention = sample_args()
    for edited in (
        (cast, dialogue.replace("갈래", "갈래요"), location, intention),
        (cast, dialogue, "outdoor", intention),
        (cast, dialogue, location, "A가 화가 났다."),
        (1, "A: 너도 같이 갈래?", location, intention),
    ):
        out = make(*edited)
        assert out["kind"] == "demo_custom" and "data" not in out, edited


def test_invalid_input_is_stopped_before_anything_is_generated():
    called = []
    out = make(2, "A: 안녕\nC: 응", "", "", live=True, generate=lambda *a, **k: called.append(1))
    assert out["kind"] == "invalid" and called == []


def test_live_mode_without_config_offers_the_demo():
    out = make(*sample_args(), live=True, load_config=lambda: None)
    assert out["kind"] == "live_error" and "예시 데모" in out["message"]


def test_live_mode_with_valid_stub_output():
    out = make(*sample_args(), live=True, load_config=lambda: CONFIG,
               generate=lambda *a, **k: copy.deepcopy(DEMO))
    assert out["kind"] == "result" and out["mode"] == "live" and out["model"] == "stub-model"


def test_live_mode_with_invalid_stub_output():
    bad = copy.deepcopy(DEMO)
    bad["shots"].pop()
    out = make(*sample_args(), live=True, load_config=lambda: CONFIG, generate=lambda *a, **k: bad)
    assert out["kind"] == "live_invalid" and out["problems"] and "다시 시도" in out["message"]
    assert "data" not in out


def test_live_mode_server_down():
    def boom(*a, **k):
        raise model_adapter.LiveModelError("라이브 AI 모드에 연결할 수 없습니다.")
    out = make(*sample_args(), live=True, load_config=lambda: CONFIG, generate=boom)
    assert out["kind"] == "live_error" and "연결할 수 없습니다" in out["message"]


# ------------------------------------------------------------ adapter

def reply(content):
    return {"choices": [{"message": {"content": content}}]}


def run_generate(post):
    return model_adapter.generate(CONFIG, sample_lines(), ["A", "B"], "indoor", "의도",
                                  CAT["templates"], CAT["angles"], post=post)


def test_config_comes_from_environment_only():
    assert model_adapter.load_config({}) is None
    assert model_adapter.load_config({"BTL_LLM_ENDPOINT": "http://x"}) is None
    cfg = model_adapter.load_config({"BTL_LLM_ENDPOINT": "http://x", "BTL_LLM_MODEL": "m", "BTL_LLM_TIMEOUT": "5"})
    assert (cfg.endpoint, cfg.model, cfg.timeout) == ("http://x", "m", 5.0)


def test_prompt_contains_the_brief_and_the_catalogs():
    sent = {}
    run_generate(lambda url, payload, timeout: (sent.update(payload), reply(json.dumps(DEMO)))[1])
    system, user = sent["messages"][0]["content"], sent["messages"][1]["content"]
    assert system.startswith("Turn the input scene into exactly three filmable shots.")
    assert "supplied dialogue line IDs" in system and "camera angle" in system
    scene_in = json.loads(user)
    assert [l["id"] for l in scene_in["dialogue_lines"]] == ["L1", "L2"]
    assert {t["id"] for t in scene_in["composition_templates"]} == set(CAT["templates"])
    assert {a["id"] for a in scene_in["camera_angles"]} == {"low", "eye_level", "high"}
    assert scene_in["location"] == "indoor"
    assert sent["model"] == "stub-model"


def test_json_is_extracted_from_fenced_or_chatty_replies():
    body = json.dumps(DEMO, ensure_ascii=False)
    assert run_generate(lambda *a: reply(body)) == DEMO
    assert run_generate(lambda *a: reply("```json\n" + body + "\n```")) == DEMO
    assert run_generate(lambda *a: reply("네, 여기 있어요.\n" + body + "\n끝")) == DEMO
    # reasoning models put their thoughts (which may contain braces) before the answer
    assert run_generate(lambda *a: reply("<think>{안 된다} 생각 중\n</think>\n" + body)) == DEMO


def test_adapter_errors_are_user_facing():
    def expect(post, text):
        try:
            run_generate(post)
        except model_adapter.LiveModelError as error:
            assert text in str(error), str(error)
        else:
            raise AssertionError("expected LiveModelError")

    def refused(*a):
        raise urllib.error.URLError("refused")

    def http500(*a):
        raise urllib.error.HTTPError("http://x", 500, "err", {}, None)

    def not_json(*a):
        raise ValueError("bad body")

    expect(refused, "연결할 수 없습니다")
    expect(http500, "오류(500)")
    expect(not_json, "읽지 못했습니다")
    expect(lambda *a: {"unexpected": 1}, "형식을 읽지 못했습니다")
    expect(lambda *a: reply("그냥 문장입니다"), "JSON")


# ------------------------------------------------------------ renderer and cards

def test_every_template_and_angle_draws_well_formed_distinct_svg():
    seen = set()
    cases = [("medium_two_shot", {"B": "left", "A": "right"}, ["door"]),
             ("ots_close_up", {"B": "subject", "A": "foreground"}, []),
             ("wide_empty_space", {"B": "figure", "A": "absent"}, []),
             ("wide_empty_space", {"A": "figure"}, []),
             ("single_medium", {"A": "figure"}, [])]
    for template, roles, props in cases:
        per_angle = []
        for angle in storyboard.ANGLE_IDS:
            svg = storyboard.render_panel(template, angle, roles, props)
            ET.fromstring(svg)                          # raises if malformed
            per_angle.append(svg)
        assert len(set(per_angle)) == 3, template        # the angle changes the picture
        seen.update(per_angle)
    for angle in storyboard.ANGLE_IDS:
        ET.fromstring(storyboard.angle_diagram(angle))
    assert len(seen) == 15


def test_demo_panels_are_three_different_pictures():
    svgs = [storyboard.render_panel(s["template_id"], s["angle_id"], s["roles"], s.get("props", ())) for s in DEMO["shots"]]
    assert len(set(svgs)) == 3
    assert "빈 자리" in svgs[2] and "빈 자리" not in svgs[0]


def test_unknown_ids_raise():
    for call in (lambda: storyboard.render_panel("x", "low", {}), lambda: storyboard.render_panel("medium_two_shot", "x", {})):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def render_cards(lines):
    out = []
    for i, shot in enumerate(DEMO["shots"], start=1):
        out.append(cards.shot_card(i, shot, CAT["templates"][shot["template_id"]], CAT["angles"][shot["angle_id"]],
                                   scene.dialogue_for_shot(shot, lines)))
    return out


def test_cards_show_dialogue_exactly_and_last_shot_silent():
    html = render_cards(sample_lines())
    assert len(html) == 3
    assert "A: 너도 같이 갈래?" in html[0] and "B: 괜찮아. 먼저 가." in html[1]
    assert "대사 없음" in html[2] and "대사 없음" not in html[0] + html[1]
    for h in html:                                       # all seven parts plus the angle
        for label in ("샷 크기", "카메라 앵글", "카메라 위치", "인물 위치와 행동", "대사", "연기 노트", "연출 이유"):
            assert f"<dt>{label}</dt>" in h
    assert not re.search(r"\n\s*\n", "".join(html))      # blank lines would break Markdown HTML blocks


def test_user_text_is_escaped():
    lines, _ = scene.parse_dialogue('A: <script>alert(1)</script> & "인용"\nB: ok', 2)
    shot = {**DEMO["shots"][0], "dialogue_line_ids": ["L1", "L2"], "reason": "<b>x</b>"}
    h = cards.shot_card(1, shot, CAT["templates"]["medium_two_shot"], CAT["angles"]["eye_level"],
                        scene.dialogue_for_shot(shot, lines))
    assert "<script>" not in h and "&lt;script&gt;" in h and "<b>x</b>" not in h


def test_svg_images_decode_back_to_valid_svg():
    h = cards.svg_img(storyboard.render_panel("single_medium", "low", {"A": "figure"}), 'alt "x"')
    data = re.search(r"base64,([^\"]+)", h).group(1)
    ET.fromstring(base64.b64decode(data).decode("utf-8"))
    assert "&quot;" in h


def test_suggestions_are_a_separate_block_with_effects():
    h = cards.suggestions_html(DEMO["suggestions"])
    assert "장면 시작 전" in h and "장면 끝난 후" in h and h.count("바뀌는 점") == 2
    assert "행동 제안" in h and "대사 제안" in h


def test_angle_comparison_is_gone_but_suggestions_and_angle_guide_stay():
    assert not hasattr(cards, "compare_html")
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "앵글 비교" not in source and "compare" not in source
    assert "AI 연출 제안" in source and "angle_guide_html" in source


def test_location_is_a_two_choice_select_box():
    assert scene.LOCATIONS == {"indoor": "실내", "outdoor": "실외"}
    assert SAMPLE["location"] == "indoor"
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.selectbox(" in source and 'key="location"' in source
    assert '"location": "indoor"' in source                       # the form starts on a valid choice
    assert "실내" in DEMO["assumptions"][0]                         # the saved demo states its place assumption


def test_app_file_compiles_and_uses_required_labels():
    py_compile.compile(str(ROOT / "app.py"), doraise=True)
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for label in ("장면 입력", "스토리보드", "AI 연출 제안", "예시 불러오기", "스토리보드 만들기", "장소", "연출 의도", "등장인물 수"):
        assert f'"{label}"' in source, label
    assert "B는 같이 가고 싶지만 붙잡지 못한다." in source


def test_all_inputs_are_inside_one_form_so_leaving_a_field_cannot_reset_it():
    import ast
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))

    def st_calls(node):
        return [n.func.attr for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"]

    forms = [n for n in ast.walk(tree) if isinstance(n, ast.With)
             and any(isinstance(i.context_expr, ast.Call) and getattr(i.context_expr.func, "attr", "") == "form"
                     for i in n.items)]
    assert len(forms) == 1
    inside = st_calls(forms[0])
    for widget in ("text_area", "text_input", "radio", "toggle", "selectbox"):
        assert widget in inside, widget
    assert inside.count("form_submit_button") == 1         # one submit button, so Enter can never load the sample
    everything = st_calls(tree)
    for widget in ("text_area", "text_input", "toggle", "selectbox"):
        assert everything.count(widget) == inside.count(widget), f"{widget} used outside the form"


def test_live_setup_help_has_what_a_beginner_needs():
    text = pipeline.LIVE_SETUP_HELP
    for needed in ("ollama", "BTL_LLM_ENDPOINT", "BTL_LLM_MODEL", "같은 터미널", "streamlit run app.py", "라이선스"):
        assert needed in text, needed
    assert "예시 데모" in pipeline.NOT_CONFIGURED and "라이브 모드 설정 방법" in pipeline.NOT_CONFIGURED


# ------------------------------------------------------ Rough.js and the sketch page

def demo_shot(i):
    return DEMO["shots"][i]


def test_bundled_rough_js_is_the_pinned_unmodified_file_with_its_license():
    data = (ROOT / "vendor" / "rough" / "rough.js").read_bytes()
    assert hashlib.sha256(data).hexdigest() == sketch.ROUGH_SHA256
    assert b"</script" not in data.lower()
    assert sketch.rough_source() is not None
    license_text = (ROOT / "vendor" / "rough" / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text and "Preet Shihn" in license_text
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Preet Shihn" in notices and "Permission is hereby granted" in notices and sketch.ROUGH_VERSION in notices
    readme = (ROOT / "vendor" / "rough" / "README.md").read_text(encoding="utf-8")
    assert sketch.ROUGH_SHA256 in readme and "github.com/rough-stuff/rough" in readme


def test_sketch_page_embeds_rough_notice_script_and_all_three_drawings():
    shot = demo_shot(0)
    panel, side, top = cards.panel_svgs(1, shot, CAT["templates"][shot["template_id"]], CAT["angles"][shot["angle_id"]])
    page = cards.shot_sketch_html(1, shot, CAT["templates"][shot["template_id"]], CAT["angles"][shot["angle_id"]])
    assert page.count("<svg") == 3 and panel in page and side in page and top in page
    assert "MIT License, Copyright (c) 2019 Preet Shihn" in page
    assert "rough.svg(" in page and "<script>" in page
    assert "https://" not in page.replace("https://github.com/rough-stuff/rough", "").replace("http://www.w3.org/2000/svg", "")


def test_sketch_page_without_rough_is_still_a_plain_drawing():
    plain = sketch.sketch_html("<svg data-seed='1'></svg>", "<svg></svg>", "<svg></svg>", "a", "b", use_rough=False)
    assert "<script" not in plain and "<svg" in plain


def test_sketch_page_falls_back_if_the_bundle_is_changed():
    real = sketch.ROUGH_FILE
    with tempfile.TemporaryDirectory() as folder:
        fake = Path(folder) / "rough.js"
        fake.write_text("alert(1)", encoding="utf-8")
        sketch.ROUGH_FILE = fake
        sketch.rough_source.cache_clear()
        try:
            assert sketch.rough_source() is None
            assert "<script" not in sketch.sketch_html("<svg></svg>", "<svg></svg>", "<svg></svg>", "a", "b")
        finally:
            sketch.ROUGH_FILE = real
            sketch.rough_source.cache_clear()
    assert sketch.rough_source() is not None


def test_roughify_script_is_valid_javascript():
    node = shutil.which("node")
    if node is None:
        return  # the browser check covers this when node is not installed
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "sketch.js"
        target.write_text(sketch.SCRIPT, encoding="utf-8")
        result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_every_drawn_shape_is_marked_for_rough_and_uses_plain_svg_attributes():
    svg = storyboard.render_panel("medium_two_shot", "eye_level", {"B": "left", "A": "right"}, ["door"],
                                  gaze={"A": "partner", "B": "door"}, actions={"A": "hold_door"})
    root = ET.fromstring(svg)
    shapes = [e for e in root.iter() if e.tag.split("}")[1] in ("rect", "circle", "ellipse", "line", "polygon", "path")]
    marked = [e for e in shapes if "data-sk" in e.attrib]
    assert len(marked) >= 30 and len(marked) >= len(shapes) - 1     # only the paper rectangle is left plain
    assert all(e.get("data-sk") in ("bg", "s", "fine") for e in marked)
    assert root.get("data-seed", "").isdigit()
    assert svg == storyboard.render_panel("medium_two_shot", "eye_level", {"B": "left", "A": "right"}, ["door"],
                                          gaze={"A": "partner", "B": "door"}, actions={"A": "hold_door"})  # stable seed


# ------------------------------------------------- gaze, action, framing, placement

def test_gaze_and_action_change_the_drawing():
    roles = {"B": "left", "A": "right"}
    base = storyboard.render_panel("medium_two_shot", "eye_level", roles, ["door"])
    seen = {base}
    for gaze in ({"B": "door"}, {"B": "away"}, {"B": "down"}):
        seen.add(storyboard.render_panel("medium_two_shot", "eye_level", roles, ["door"], gaze=gaze))
    for action in scene.ACTIONS:
        seen.add(storyboard.render_panel("medium_two_shot", "eye_level", roles, ["door"], actions={"A": action}))
    assert len(seen) == 1 + 3 + len(scene.ACTIONS) - 1          # "stand" is the default pose, so it equals the base


def test_gaze_arrow_is_drawn_only_when_a_character_looks_at_something():
    arrow = f'stroke="{storyboard.ACCENT}"'
    one = storyboard.render_panel("single_medium", "eye_level", {"A": "figure"})      # alone: nothing to look at
    assert arrow not in one
    assert arrow in storyboard.render_panel("single_medium", "eye_level", {"A": "figure"}, gaze={"A": "away"})
    for shot in DEMO["shots"]:
        svg = storyboard.render_panel(shot["template_id"], shot["angle_id"], shot["roles"], shot.get("props", ()),
                                      gaze=shot.get("gaze"), actions=shot.get("actions"))
        assert arrow in svg, shot["template_id"]


def test_every_template_angle_gaze_and_action_combination_draws_valid_svg():
    templates = {
        "medium_two_shot": {"B": "left", "A": "right"}, "single_medium": {"A": "figure"},
        "ots_close_up": {"B": "subject", "A": "foreground"}, "wide_empty_space": {"B": "figure", "A": "absent"},
    }
    count = 0
    for template, roles in templates.items():
        for angle in storyboard.ANGLE_IDS:
            for gaze in list(scene.GAZE_TARGETS):
                for action in scene.ACTIONS:
                    who = next(c for c, r in roles.items() if r != "absent")
                    for props in ((), ("door",)):
                        ET.fromstring(storyboard.render_panel(template, angle, roles, props, gaze={who: gaze}, actions={who: action}))
                        ET.fromstring(storyboard.blocking_diagram(template, angle, roles, props, gaze={who: gaze}))
                        count += 1
    assert count == 4 * 3 * 4 * 7 * 2


def test_panel_names_the_framing_and_the_angle():
    svg = storyboard.render_panel("ots_close_up", "high", {"B": "subject", "A": "foreground"})
    assert "OTS CU" in svg and "HIGH" in svg
    assert "WS" in storyboard.render_panel("wide_empty_space", "low", {"A": "figure"})


def test_plan_view_shows_placement_and_camera_and_marks_the_empty_spot():
    top = storyboard.blocking_diagram("wide_empty_space", "high", {"B": "figure", "A": "absent"}, gaze={"B": "partner"})
    assert ">B<" in top and ">A<" in top and 'stroke-dasharray="3 2"' in top
    door = storyboard.blocking_diagram("medium_two_shot", "eye_level", {"B": "left", "A": "right"}, ["door"])
    assert "문" in door and "문" not in storyboard.blocking_diagram("medium_two_shot", "eye_level", {"B": "left", "A": "right"})


def test_demo_shots_carry_gaze_and_actions_that_the_card_prints():
    lines = sample_lines()
    for shot in DEMO["shots"]:
        assert shot["gaze"] and shot["actions"]
    html_text = cards.shot_details_html(DEMO["shots"][0], CAT["templates"]["medium_two_shot"], CAT["angles"]["eye_level"],
                                        scene.dialogue_for_shot(DEMO["shots"][0], lines))
    assert "문을 잡는다" in html_text and "문 쪽을 본다" in html_text and "상대를 본다" in html_text
    third = cards.shot_details_html(DEMO["shots"][2], CAT["templates"]["wide_empty_space"], CAT["angles"]["high"], [])
    assert "<b>B</b>" in third and "<b>A</b>" not in third          # the absent character has no pose


def test_validation_checks_gaze_actions_and_props_when_present():
    lines, cast = sample_lines(), ["A", "B"]

    def problems(change):
        data = copy.deepcopy(DEMO)
        change(data["shots"][0])
        return scene.validate_model_output(data, lines, cast, CAT["templates"], CAT["angles"])

    assert problems(lambda s: None) == []
    assert problems(lambda s: (s.pop("gaze"), s.pop("actions"), s.pop("props"))) == []      # all optional
    assert any("gaze" in p for p in problems(lambda s: s.update(gaze={"A": "ceiling"})))
    assert any("actions" in p for p in problems(lambda s: s.update(actions={"A": "dance"})))
    assert any("gaze" in p for p in problems(lambda s: s.update(gaze={"C": "door"})))
    assert any("actions" in p for p in problems(lambda s: s.update(actions="stand")))
    assert any("props" in p for p in problems(lambda s: s.update(props="door")))


def test_prompt_lists_every_gaze_and_action_id_the_drawing_understands():
    for key in list(scene.GAZE_TARGETS) + list(scene.ACTIONS):
        assert key in model_adapter.FORMAT_NOTES, key
    assert '"gaze"' in model_adapter.FORMAT_NOTES and '"actions"' in model_adapter.FORMAT_NOTES


def test_fallback_card_still_contains_panel_diagrams_and_text():
    lines = sample_lines()
    html_text = "".join(render_cards(lines))
    assert html_text.count("data:image/svg+xml;base64,") >= 9      # panel + height + plan view for each of 3 shots
    assert "동작과 시선" in html_text and "<script" not in html_text


def test_app_uses_the_component_and_keeps_the_plain_fallback():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "components.html(" in source and "sketch.rough_source()" in source and "cards.shot_card(" in source
    py_compile.compile(str(ROOT / "app.py"), doraise=True)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok  ", name)
        except Exception as error:  # noqa: BLE001
            failed += 1
            print("FAIL", name, "->", repr(error))
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
