"""Checks for everything that does not need Streamlit.

Run with:  python tests/test_checks.py      (or: python -m pytest tests)
"""
import base64
import copy
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
        (cast, dialogue, "교실", intention),
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
    return model_adapter.generate(CONFIG, sample_lines(), ["A", "B"], "복도", "의도",
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


def test_angle_comparison_marks_the_chosen_angle_once():
    shot = DEMO["shots"][1]
    h = cards.compare_html(shot, CAT["templates"][shot["template_id"]], CAT["angles"], CAT["angle_order"])
    assert h.count("이 샷의 선택") == 1 and h.count("<img") == 3


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
    for widget in ("text_area", "text_input", "radio", "toggle"):
        assert widget in inside, widget
    assert inside.count("form_submit_button") == 1         # one submit button, so Enter can never load the sample
    everything = st_calls(tree)
    for widget in ("text_area", "text_input", "toggle"):
        assert everything.count(widget) == inside.count(widget), f"{widget} used outside the form"


def test_live_setup_help_has_what_a_beginner_needs():
    text = pipeline.LIVE_SETUP_HELP
    for needed in ("ollama", "BTL_LLM_ENDPOINT", "BTL_LLM_MODEL", "같은 터미널", "streamlit run app.py", "라이선스"):
        assert needed in text, needed
    assert "예시 데모" in pipeline.NOT_CONFIGURED and "라이브 모드 설정 방법" in pipeline.NOT_CONFIGURED


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
