"""Hand-drawn rendering of the storyboard panels with Rough.js. Plain Python, no Streamlit.

`storyboard.py` produces plain SVG whose shapes carry `data-sk` attributes. This module wraps
that SVG in a small self-contained HTML page together with the bundled Rough.js library
(`vendor/rough/rough.js`) and a short script that redraws each marked shape in a hand-drawn style.
Streamlit shows the page through `st.components.v1.html`, which runs it in an iframe.

If Rough.js is missing, changed, or fails in the browser, the plain SVG stays on screen. It is
still a complete drawing, only without the sketchy line work.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

ROUGH_FILE = Path(__file__).with_name("vendor") / "rough" / "rough.js"
ROUGH_VERSION = "4.6.6"
ROUGH_SHA256 = "6853af8619532f3939b156cd16824d2e14f31e71d3df306ad5558eeafacab194"
ROUGH_NOTICE = (
    "Rough.js v4.6.6 - https://github.com/rough-stuff/rough - "
    "MIT License, Copyright (c) 2019 Preet Shihn. Full text: THIRD_PARTY_NOTICES.md and vendor/rough/LICENSE."
)

# Height used when the browser does not let the iframe resize itself. The content is capped at
# MAX_WIDTH, so it can never be taller than this.
MAX_WIDTH = 380
FALLBACK_HEIGHT = 360


@lru_cache(maxsize=1)
def rough_source() -> str | None:
    """The bundled Rough.js code, or None if it is missing or is not the pinned file."""
    try:
        data = ROUGH_FILE.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(data).hexdigest() != ROUGH_SHA256:
        return None
    source = data.decode("utf-8")
    if "</script" in source.lower():          # would end the inline <script> early
        return None
    return source


# Redraws every [data-sk] shape with Rough.js. Attributes written by storyboard.py decide the look:
# fill, stroke, stroke-width, stroke-dasharray, opacity, transform, data-fs (solid or hachure).
# data-seed makes the result identical on every rerun, so panels do not jitter.
SCRIPT = r"""
(function () {
  var LOOK = {bg: {roughness: 0.7, bowing: 0.6}, s: {roughness: 1.0, bowing: 1.0},
              fine: {roughness: 0.5, bowing: 0.5, disableMultiStroke: true}};
  function num(el, name) { var v = parseFloat(el.getAttribute(name)); return isNaN(v) ? 0 : v; }
  function points(el) {
    var raw = (el.getAttribute('points') || '').trim().split(/[\s,]+/).map(parseFloat), out = [];
    for (var i = 0; i + 1 < raw.length; i += 2) out.push([raw[i], raw[i + 1]]);
    return out;
  }
  function draw(rc, el, opts) {
    switch (el.tagName.toLowerCase()) {
      case 'rect': return rc.rectangle(num(el, 'x'), num(el, 'y'), num(el, 'width'), num(el, 'height'), opts);
      case 'circle': return rc.circle(num(el, 'cx'), num(el, 'cy'), num(el, 'r') * 2, opts);
      case 'ellipse': return rc.ellipse(num(el, 'cx'), num(el, 'cy'), num(el, 'rx') * 2, num(el, 'ry') * 2, opts);
      case 'line': return rc.line(num(el, 'x1'), num(el, 'y1'), num(el, 'x2'), num(el, 'y2'), opts);
      case 'polygon': return rc.polygon(points(el), opts);
      case 'polyline': return rc.linearPath(points(el), opts);
      case 'path': return rc.path(el.getAttribute('d'), opts);
    }
    return null;
  }
  function roughify(svg) {
    var rc = rough.svg(svg), seed = parseInt(svg.getAttribute('data-seed') || '1', 10), failed = 0;
    Array.prototype.slice.call(svg.querySelectorAll('[data-sk]')).forEach(function (el, i) {
      try {
        var look = LOOK[el.getAttribute('data-sk')] || LOOK.s;
        var fill = el.getAttribute('fill') || 'none', stroke = el.getAttribute('stroke') || 'none';
        var opts = {seed: seed + i, roughness: look.roughness, bowing: look.bowing,
                    disableMultiStroke: !!look.disableMultiStroke,
                    fill: fill === 'none' ? undefined : fill, stroke: stroke,
                    strokeWidth: parseFloat(el.getAttribute('stroke-width')) || 1};
        if (fill !== 'none') {
          opts.fillStyle = el.getAttribute('data-fs') === 'hachure' ? 'hachure' : 'solid';
          opts.hachureGap = 4; opts.fillWeight = 0.8;
        }
        var dash = el.getAttribute('stroke-dasharray');
        if (dash) opts.strokeLineDash = dash.split(/[\s,]+/).map(parseFloat);
        var g = draw(rc, el, opts);
        if (!g) return;
        ['opacity', 'transform'].forEach(function (a) { if (el.hasAttribute(a)) g.setAttribute(a, el.getAttribute(a)); });
        el.parentNode.replaceChild(g, el);
      } catch (e) { failed++; }
    });
    return failed;
  }
  function fit() {
    try {
      var h = document.documentElement.getBoundingClientRect().height;
      if (window.frameElement && h > 40) window.frameElement.style.height = Math.ceil(h) + 'px';
    } catch (e) { /* cross-origin or sandboxed: the fixed height from Python is used */ }
  }
  var state = 'plain';
  try {
    var failed = 0;
    Array.prototype.forEach.call(document.querySelectorAll('svg[data-seed]'), function (s) { failed += roughify(s); });
    state = failed ? 'partial' : 'rough';
  } catch (e) { state = 'plain'; }
  document.documentElement.setAttribute('data-sketch', state);
  fit();
  if (window.ResizeObserver) new ResizeObserver(fit).observe(document.body);
  window.addEventListener('load', fit);
})();
"""

STYLE = (
    "html,body{margin:0;padding:0;background:#fff;font-family:'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif}"
    f".wrap{{max-width:{MAX_WIDTH}px;padding:2px}}"
    ".panel svg{display:block;width:100%;height:auto;border:2px solid #18212C;background:#FBFAF7}"
    ".diagrams{display:flex;gap:8px;margin-top:8px}"
    ".diagrams figure{flex:1 1 0;min-width:0;margin:0}"
    ".diagrams svg{display:block;width:100%;height:auto;border:1px solid #CBD2DA;background:#fff}"
    ".diagrams figcaption{font-size:11px;color:#46515F;line-height:1.35;margin-top:3px}"
)


def sketch_html(panel_svg: str, side_svg: str, top_svg: str, side_caption: str, top_caption: str, use_rough: bool = True) -> str:
    """One self-contained page: the panel on top, the camera-height and plan diagrams under it."""
    source = rough_source() if use_rough else None
    body = (
        f'<div class="wrap"><div class="panel">{panel_svg}</div><div class="diagrams">'
        f"<figure>{side_svg}<figcaption>{side_caption}</figcaption></figure>"
        f"<figure>{top_svg}<figcaption>{top_caption}</figcaption></figure></div></div>"
    )
    scripts = f"<!-- {ROUGH_NOTICE} --><script>{source}</script><script>{SCRIPT}</script>" if source else ""
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{STYLE}</style></head><body>{body}{scripts}</body></html>"
    )
