"""Between the Lines: turn a short dialogue scene into a three-shot storyboard.

Run with:  streamlit run app.py

This file only draws the page. The logic lives in pipeline.py, scene.py,
storyboard.py, sketch.py, cards.py and model_adapter.py.
"""
from pathlib import Path

import streamlit as st

import cards
import pipeline
import scene
import sketch

try:
    import streamlit.components.v1 as components
except ImportError:  # very old Streamlit: the plain-image card is used instead
    components = None

st.set_page_config(page_title="Between the Lines", page_icon="🎬", layout="wide")
st.markdown(cards.CSS, unsafe_allow_html=True)


@st.cache_data
def get_catalogs():
    return pipeline.load_catalogs(Path(__file__).parent / "data")


CAT = get_catalogs()
SAMPLE = CAT["demo"]["sample"]

for key, value in {
    "cast_n": 2, "dialogue": "", "location": "indoor", "intention": "",
    "live": False, "output": None,
}.items():
    st.session_state.setdefault(key, value)


def load_sample(to_demo: bool = False):
    st.session_state.update(
        cast_n=SAMPLE["cast_count"], dialogue=SAMPLE["dialogue"],
        location=SAMPLE["location"], intention=SAMPLE["intention"], output=None,
    )
    if to_demo:
        st.session_state["live"] = False


def request_retry():
    st.session_state["_retry"] = True


def show_shot(index: int, shot: dict, lines) -> None:
    """One shot card. The panel is a Rough.js hand-drawn sketch inside an HTML component.

    If the component cannot be used (Rough.js file missing or changed, or no components API),
    the same card is shown with plain images instead, so the app still works."""
    template, angle = CAT["templates"][shot["template_id"]], CAT["angles"][shot["angle_id"]]
    dialogue = scene.dialogue_for_shot(shot, lines)
    if components is None or sketch.rough_source() is None:
        st.markdown(cards.shot_card(index, shot, template, angle, dialogue), unsafe_allow_html=True)
        return
    with st.container(border=True):
        st.markdown(cards.shot_header_html(index, template, angle), unsafe_allow_html=True)
        visual, details = st.columns([5, 6], gap="medium")
        with details:
            st.markdown(cards.shot_details_html(shot, template, angle, dialogue), unsafe_allow_html=True)
        with visual:
            try:
                components.html(cards.shot_sketch_html(index, shot, template, angle), height=sketch.FALLBACK_HEIGHT)
            except Exception:  # keep the page alive; show the panel as a plain image
                panel, _, _ = cards.panel_svgs(index, shot, template, angle)
                st.markdown(cards.svg_img(panel, f"샷 {index}"), unsafe_allow_html=True)


def live_help():
    with st.expander("라이브 모드 설정 방법"):
        st.markdown(pipeline.LIVE_SETUP_HELP)


st.title("Between the Lines")
st.caption("짧은 대사 장면을 카메라 앵글까지 정한 3컷 스토리보드로 바꿔 줍니다.")

left, right = st.columns([4, 8], gap="large")

# ------------------------------------------------------------ 장면 입력
with left:
    st.subheader("장면 입력")
    st.button("예시 불러오기", key="load_sample_btn", on_click=load_sample)
    badge_slot = st.empty()

    # Everything the user types sits in one form. Nothing is sent to the server, and the page
    # does not rerun, until the user presses the submit button. Moving from one field to the
    # next therefore cannot reset what was typed.
    with st.form("scene_form", clear_on_submit=False):
        st.toggle(
            "라이브 AI 모드 (내 컴퓨터의 로컬 모델)", key="live",
            help="‘스토리보드 만들기’를 누르면 적용돼요. 끄면 데모 모드입니다.",
        )
        st.radio("등장인물 수", [1, 2], key="cast_n", horizontal=True, format_func=lambda n: f"{n}명")
        st.text_area(
            "대사", key="dialogue", height=170,
            placeholder="A: 안녕\nB: 응",
            help="한 줄에 한 마디씩 “A: 대사” 또는 “B: 대사” 형식으로 적습니다.",
        )
        st.caption("한 줄에 한 마디씩 “A: 대사” 형식으로 적어요. 1명 장면에서는 A만, 2명 장면에서는 A와 B를 쓸 수 있어요.")
        st.selectbox(
            "장소", list(scene.LOCATIONS), key="location", format_func=scene.LOCATIONS.get,
            help="장면이 실내에서 일어나는지, 실외에서 일어나는지 골라 주세요.",
        )
        st.text_input(
            "연출 의도", key="intention", help="선택 사항입니다.",
            placeholder="B는 같이 가고 싶지만 붙잡지 못한다.",
        )
        generate_clicked = st.form_submit_button("스토리보드 만들기", type="primary")

    messages = st.container()

    with st.expander("카메라 앵글 한눈에 보기"):
        st.markdown(cards.angle_guide_html(CAT["angles"], CAT["angle_order"]), unsafe_allow_html=True)
        st.caption(CAT["disclaimer"])

snapshot = scene.snapshot(
    st.session_state["cast_n"], st.session_state["dialogue"],
    st.session_state["location"], st.session_state["intention"],
)

retry_requested = st.session_state.pop("_retry", False)
if generate_clicked or retry_requested:
    with st.spinner("스토리보드를 만드는 중…" if st.session_state["live"] else "확인하는 중…"):
        st.session_state["output"] = pipeline.make_output(
            st.session_state["cast_n"], st.session_state["dialogue"],
            st.session_state["location"], st.session_state["intention"],
            st.session_state["live"], CAT,
        )

# The label shows the mode the app is actually in (the last one that was submitted).
badge_slot.markdown(cards.mode_badge(st.session_state["live"]), unsafe_allow_html=True)

out = st.session_state["output"]
fresh = out is not None and out["snapshot"] == snapshot

with messages:
    if fresh and out["kind"] == "invalid":
        for message in out["errors"]:
            st.error(message)

# ------------------------------------------------------------ 스토리보드
with right:
    st.subheader("스토리보드")

    if out is None:
        st.caption("왼쪽에서 장면을 입력하고 ‘스토리보드 만들기’를 누르면 샷 3개가 여기에 나타납니다. 처음이라면 ‘예시 불러오기’를 눌러 보세요.")
    elif not fresh:
        st.info("입력이 바뀌었어요. ‘스토리보드 만들기’를 다시 눌러 주세요.")
    elif out["kind"] == "invalid":
        st.info("왼쪽의 안내에 따라 대사를 고친 뒤 다시 눌러 주세요.")
    elif out["kind"] == "demo_custom":
        st.warning(
            "데모 모드에서는 저장된 예시 장면만 보여 드려요. "
            "내가 쓴 장면으로 만들려면 라이브 AI 모드가 필요합니다."
        )
        st.button("예시 다시 불러오기", key="reload_btn", on_click=load_sample)
        live_help()
    elif out["kind"] in ("live_error", "live_invalid"):
        st.error(out["message"])
        if out["kind"] == "live_invalid":
            with st.expander("자세한 원인"):
                for problem in out["problems"]:
                    st.write("- " + problem)
        c1, c2 = st.columns(2)
        c1.button("다시 시도", key="retry_btn", on_click=request_retry)
        c2.button("예시 불러오기", key="demo_btn", on_click=load_sample, kwargs={"to_demo": True})
        live_help()
    else:
        data, lines = out["data"], out["lines"]
        st.markdown(cards.result_badge(out["mode"], out["model"]), unsafe_allow_html=True)
        for i, shot in enumerate(data["shots"], start=1):
            show_shot(i, shot, lines)
        st.markdown(cards.assumptions_html(data.get("assumptions", [])), unsafe_allow_html=True)

        st.subheader("AI 연출 제안")
        st.caption("원래 대본과 별개의 선택 사항입니다. 스토리보드에 자동으로 넣지 않았어요.")
        st.markdown(cards.suggestions_html(data["suggestions"]), unsafe_allow_html=True)

st.divider()
st.caption("샘플 장면, 구도 템플릿, 앵글 설명은 이 프로젝트를 위해 직접 만든 것입니다. 패널은 코드로 그린 도식이며 실제 이미지가 아닙니다. 손그림 느낌은 Rough.js(MIT 라이선스)로 그렸어요.")
