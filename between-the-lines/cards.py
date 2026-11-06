"""HTML builders for the storyboard cards. Plain Python, no Streamlit.

Every piece of text that comes from the user or from a model is escaped here.
SVG panels are embedded as <img> data URIs, which render reliably inside Streamlit.
"""
from __future__ import annotations

import base64
import html

import scene
import sketch
import storyboard

CSS = (
    "<style>"
    ".btl-badge{display:inline-block;border:1.5px solid #27508A;color:#27508A;border-radius:4px;padding:2px 10px;font-weight:600;font-size:.9rem}"
    ".btl-badge.live{background:#27508A;color:#fff}"
    ".btl-card{background:#fff;border:1px solid #CBD2DA;border-radius:4px;padding:16px;margin:0 0 16px}"
    ".btl-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 12px}"
    ".btl-num{display:inline-block;min-width:1.7em;text-align:center;border:1.5px solid #27508A;color:#27508A;border-radius:4px;font-weight:700}"
    ".btl-title{font-size:1.1rem;font-weight:700}"
    ".btl-chip{font-size:.82rem;border-radius:4px;padding:1px 8px;background:#E9ECF0;color:#18212C}"
    ".btl-body{display:flex;flex-wrap:wrap;gap:18px}"
    ".btl-visual{flex:1 1 300px;min-width:0}"
    ".btl-visual img{display:block;width:100%;height:auto;border:2px solid #18212C}"
    ".btl-angle{display:flex;gap:10px;align-items:center;margin-top:10px;font-size:.85rem;color:#46515F;line-height:1.4}"
    ".btl-angle img{width:112px;flex:none;border:1px solid #CBD2DA;background:#F3F4F6}"
    ".btl-rows-wrap{flex:1 1 300px;min-width:0}"
    ".btl-rows{margin:0}"
    ".btl-rows dt{font-weight:700;font-size:.82rem;color:#46515F;margin-top:10px}"
    ".btl-rows dt:first-child{margin-top:0}"
    ".btl-rows dd{margin:2px 0 0}"
    ".btl-sub{color:#46515F;font-size:.9rem}"
    ".btl-say{border-left:3px solid #27508A;padding-left:10px}"
    ".btl-silent{color:#46515F;font-style:italic}"
    ".btl-sugg{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 12px}"
    ".btl-sugg>div{flex:1 1 260px;background:#fff;border:1px solid #CBD2DA;border-top:3px solid #C0392B;border-radius:4px;padding:12px 14px}"
    ".btl-sugg h4{margin:0 0 2px;font-size:1rem}"
    ".btl-compare{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}"
    ".btl-compare>div{background:#fff;border:1px solid #CBD2DA;border-radius:4px;padding:10px}"
    ".btl-compare img{display:block;width:100%;height:auto;border:2px solid #18212C;margin-bottom:8px}"
    ".btl-compare p{margin:0 0 6px;font-size:.9rem}"
    "</style>"
)


def esc(value) -> str:
    return html.escape(str(value), quote=True).replace("\n", "<br>")


def svg_img(svg: str, alt: str) -> str:
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img alt="{html.escape(alt, quote=True)}" src="data:image/svg+xml;base64,{data}">'


def mode_badge(live: bool) -> str:
    if live:
        return '<span class="btl-badge live">현재 모드: 라이브 AI 모드</span>'
    return '<span class="btl-badge">현재 모드: 데모 모드</span>'


def result_badge(mode: str, model: str | None = None) -> str:
    if mode == "demo":
        return '<span class="btl-badge">데모 모드 · 저장된 예시 결과</span>'
    return f'<span class="btl-badge live">라이브 AI 모드 · {esc(model or "모델")}</span>'


def shot_header_html(index: int, template: dict, angle: dict) -> str:
    return (
        f'<div class="btl-head"><span class="btl-num">{index}</span>'
        f'<span class="btl-title">{esc(template["shot_size_ko"])}</span>'
        f'<span class="btl-chip">{esc(angle["name_ko"])}</span></div>'
    )


def _hints_text(shot: dict) -> str:
    """One line per character: the pose and the gaze that the drawing shows."""
    gaze, actions = shot.get("gaze") or {}, shot.get("actions") or {}
    rows = []
    for char in sorted(set(gaze) | set(actions)):
        if shot["roles"].get(char) == "absent":
            continue
        bits = []
        if char in actions:
            bits.append(scene.ACTIONS.get(actions[char], str(actions[char])))
        if char in gaze:
            bits.append(scene.GAZE_TARGETS.get(gaze[char], str(gaze[char])))
        rows.append(f"<b>{esc(char)}</b> {esc(' · '.join(bits))}")
    return "<br>".join(rows)


def shot_details_html(shot: dict, template: dict, angle: dict, dialogue_lines) -> str:
    focus = shot.get("angle_focus")
    focus_text = f" ({esc(focus)} 기준)" if focus else ""
    if dialogue_lines:
        said = "<br>".join(esc(line.raw) for line in dialogue_lines)
        dialogue = f'<dd class="btl-say">{said}</dd>'
    else:
        dialogue = '<dd class="btl-silent">대사 없음</dd>'
    hints = _hints_text(shot)
    hints_row = f'<dt>동작과 시선 (그림의 붉은 화살표)</dt><dd>{hints}</dd>' if hints else ""
    return (
        '<dl class="btl-rows">'
        f'<dt>샷 크기</dt><dd><b>{esc(template["shot_size_ko"])}</b><br><span class="btl-sub">{esc(template["effect_ko"])}</span></dd>'
        f'<dt>카메라 앵글</dt><dd><b>{esc(angle["name_ko"])}</b>{focus_text}<br>'
        f'<span class="btl-sub">{esc(angle["effect_ko"])}</span></dd>'
        f'<dt>카메라 위치</dt><dd>{esc(shot["camera_position"])}</dd>'
        f'<dt>인물 위치와 행동</dt><dd>{esc(shot["placement_and_action"])}</dd>'
        f'{hints_row}'
        f'<dt>대사</dt>{dialogue}'
        f'<dt>연기 노트</dt><dd>{esc(shot["acting_note"])}</dd>'
        f'<dt>연출 이유</dt><dd>{esc(shot["reason"])}</dd>'
        "</dl>"
    )


def panel_svgs(index: int, shot: dict, template: dict, angle: dict) -> tuple[str, str, str]:
    """(panel, camera height diagram, plan view) for one shot, as plain SVG strings."""
    kwargs = dict(props=shot.get("props", ()))
    panel = storyboard.render_panel(
        shot["template_id"], shot["angle_id"], shot["roles"],
        alt=f"샷 {index}: {template['shot_size_ko']}, {angle['name_ko']}",
        gaze=shot.get("gaze"), actions=shot.get("actions"), **kwargs,
    )
    side = storyboard.angle_diagram(shot["angle_id"])
    top = storyboard.blocking_diagram(shot["template_id"], shot["angle_id"], shot["roles"], gaze=shot.get("gaze"), **kwargs)
    return panel, side, top


SIDE_CAPTION = "카메라 높이 (옆에서 본 모습)"
TOP_CAPTION = "인물과 카메라 배치 (위에서 본 모습)"


def shot_sketch_html(index: int, shot: dict, template: dict, angle: dict) -> str:
    """The hand-drawn panel page for st.components.v1.html (panel plus the two small diagrams)."""
    panel, side, top = panel_svgs(index, shot, template, angle)
    return sketch.sketch_html(panel, side, top, SIDE_CAPTION, TOP_CAPTION)


def shot_card(index: int, shot: dict, template: dict, angle: dict, dialogue_lines) -> str:
    """The whole card as one HTML string, with plain (not hand-drawn) images.

    The app uses this when the Rough.js component cannot be shown."""
    panel, side, top = panel_svgs(index, shot, template, angle)
    alt = f"샷 {index}: {template['shot_size_ko']}, {angle['name_ko']}"
    return (
        '<div class="btl-card">'
        f"{shot_header_html(index, template, angle)}"
        '<div class="btl-body">'
        f'<div class="btl-visual">{svg_img(panel, alt)}'
        f'<div class="btl-angle">{svg_img(side, "카메라 높이 그림")}'
        f'<span><b>{esc(angle["name_ko"])}</b> · {esc(angle["camera_ko"])}</span></div>'
        f'<div class="btl-angle">{svg_img(top, "인물과 카메라 배치 그림")}<span>{esc(TOP_CAPTION)}</span></div></div>'
        f"<div class=\"btl-rows-wrap\">{shot_details_html(shot, template, angle, dialogue_lines)}</div>"
        "</div></div>"
    )


def suggestions_html(suggestions: dict) -> str:
    kinds = {"action": "행동 제안", "dialogue": "대사 제안"}
    parts = []
    for slot, title in (("before", "장면 시작 전"), ("after", "장면 끝난 후")):
        item = suggestions[slot]
        parts.append(
            f'<div><h4>{title}</h4><p class="btl-sub" style="margin:0 0 8px">{kinds[item["kind"]]}</p>'
            f'<p style="margin:0 0 8px">{esc(item["text"])}</p>'
            f'<p class="btl-sub" style="margin:0"><b>바뀌는 점</b> {esc(item["effect"])}</p></div>'
        )
    return f'<div class="btl-sugg">{"".join(parts)}</div>'


def assumptions_html(assumptions: list[str]) -> str:
    if not assumptions:
        return ""
    items = " ".join(esc(a) for a in assumptions)
    return f'<p class="btl-sub"><b>가정</b> {items}</p>'


def angle_guide_html(angles: dict, order: list[str]) -> str:
    cells = []
    for angle_id in order:
        angle = angles[angle_id]
        cells.append(
            "<div>"
            f'{svg_img(storyboard.angle_diagram(angle_id), angle["name_ko"])}'
            f'<p><b>{esc(angle["name_ko"])}</b></p>'
            f'<p class="btl-sub">{esc(angle["camera_ko"])}</p>'
            f'<p class="btl-sub">{esc(angle["effect_ko"])}</p>'
            "</div>"
        )
    return f'<div class="btl-compare">{"".join(cells)}</div>'
