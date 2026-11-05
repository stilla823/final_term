"""HTML builders for the storyboard cards. Plain Python, no Streamlit.

Every piece of text that comes from the user or from a model is escaped here.
SVG panels are embedded as <img> data URIs, which render reliably inside Streamlit.
"""
from __future__ import annotations

import base64
import html

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
    ".btl-rows{flex:1 1 300px;min-width:0;margin:0}"
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
    ".btl-compare>div.on{border:2px solid #27508A}"
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


def shot_card(index: int, shot: dict, template: dict, angle: dict, dialogue_lines) -> str:
    panel = storyboard.render_panel(
        shot["template_id"], shot["angle_id"], shot["roles"], shot.get("props", ()),
    )
    alt = f"샷 {index}: {template['shot_size_ko']}, {angle['name_ko']}"
    focus = shot.get("angle_focus")
    focus_text = f" ({esc(focus)} 기준)" if focus else ""
    if dialogue_lines:
        said = "<br>".join(esc(line.raw) for line in dialogue_lines)
        dialogue = f'<dd class="btl-say">{said}</dd>'
    else:
        dialogue = '<dd class="btl-silent">대사 없음</dd>'
    return (
        '<div class="btl-card">'
        f'<div class="btl-head"><span class="btl-num">{index}</span>'
        f'<span class="btl-title">{esc(template["shot_size_ko"])}</span>'
        f'<span class="btl-chip">{esc(angle["name_ko"])}</span></div>'
        '<div class="btl-body">'
        f'<div class="btl-visual">{svg_img(panel, alt)}'
        f'<div class="btl-angle">{svg_img(storyboard.angle_diagram(shot["angle_id"]), "카메라 높이 그림")}'
        f'<span><b>{esc(angle["name_ko"])}</b> · {esc(angle["camera_ko"])}</span></div></div>'
        '<dl class="btl-rows">'
        f'<dt>샷 크기</dt><dd><b>{esc(template["shot_size_ko"])}</b><br><span class="btl-sub">{esc(template["effect_ko"])}</span></dd>'
        f'<dt>카메라 앵글</dt><dd><b>{esc(angle["name_ko"])}</b>{focus_text}<br>'
        f'<span class="btl-sub">{esc(angle["effect_ko"])}</span></dd>'
        f'<dt>카메라 위치</dt><dd>{esc(shot["camera_position"])}</dd>'
        f'<dt>인물 위치와 행동</dt><dd>{esc(shot["placement_and_action"])}</dd>'
        f'<dt>대사</dt>{dialogue}'
        f'<dt>연기 노트</dt><dd>{esc(shot["acting_note"])}</dd>'
        f'<dt>연출 이유</dt><dd>{esc(shot["reason"])}</dd>'
        "</dl></div></div>"
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


def compare_html(shot: dict, template: dict, angles: dict, order: list[str]) -> str:
    cells = []
    for angle_id in order:
        angle = angles[angle_id]
        panel = storyboard.render_panel(shot["template_id"], angle_id, shot["roles"], shot.get("props", ()))
        chosen = angle_id == shot["angle_id"]
        mark = " (이 샷의 선택)" if chosen else ""
        css_class = "on" if chosen else ""
        alt = template["shot_size_ko"] + ", " + angle["name_ko"]
        cells.append(
            f'<div class="{css_class}">'
            f'{svg_img(panel, alt)}'
            f'<p><b>{esc(angle["name_ko"])}</b>{mark}</p>'
            f'<p class="btl-sub">{esc(angle["effect_ko"])}</p>'
            f'<p class="btl-sub"><b>이럴 때</b> {esc(angle["use_ko"])}</p>'
            "</div>"
        )
    return f'<div class="btl-compare">{"".join(cells)}</div>'


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
