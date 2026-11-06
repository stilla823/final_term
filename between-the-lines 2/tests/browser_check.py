"""Optional browser check for the Rough.js sketch component. Needs Playwright and Chromium.

Run with:  python tests/browser_check.py

It loads each demo shot the way Streamlit does (HTML inside a sandboxed iframe with
allow-scripts and allow-same-origin) and checks that Rough.js ran without errors, that the
shapes were redrawn, that the iframe resized itself, and that the plain SVG is kept when Rough.js
is not available. It does not start Streamlit.
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cards  # noqa: E402
import pipeline  # noqa: E402
import sketch  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed; skipping the browser check.")
    sys.exit(0)

CAT = pipeline.load_catalogs(ROOT / "data")
SHOTS = CAT["demo"]["result"]["shots"]
SANDBOX = "allow-forms allow-modals allow-popups allow-same-origin allow-scripts allow-downloads"


def page_for(shot, index, use_rough=True):
    t, a = CAT["templates"][shot["template_id"]], CAT["angles"][shot["angle_id"]]
    panel, side, top = cards.panel_svgs(index, shot, t, a)
    return sketch.sketch_html(panel, side, top, cards.SIDE_CAPTION, cards.TOP_CAPTION, use_rough=use_rough)


def parent(inner, width):
    return (f'<html><body style="margin:0"><div style="width:{width}px">'
            f'<iframe id="f" sandbox="{SANDBOX}" height="{sketch.FALLBACK_HEIGHT}" style="width:100%;border:0" '
            f'srcdoc="{html.escape(inner, quote=True)}"></iframe></div></body></html>')


def main():
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for i, shot in enumerate(SHOTS, start=1):
            for width in (300, 380, 520):
                page = browser.new_page(viewport={"width": 700, "height": 600})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.set_content(parent(page_for(shot, i), width))
                page.wait_for_timeout(400)
                frame = page.frame_locator("#f").locator("html")
                state = frame.get_attribute("data-sketch")
                inner = page.frames[1]
                rough_paths = inner.evaluate("document.querySelectorAll('svg[data-seed] path[stroke]').length")
                left_over = inner.evaluate("document.querySelectorAll('[data-sk]').length")
                content_h = inner.evaluate("Math.ceil(document.documentElement.getBoundingClientRect().height)")
                iframe_h = page.evaluate("document.getElementById('f').getBoundingClientRect().height")
                ok = state == "rough" and rough_paths > 50 and left_over == 0 and not errors \
                    and abs(iframe_h - content_h) <= 2 and iframe_h <= sketch.FALLBACK_HEIGHT
                print(("ok  " if ok else "FAIL"), f"shot {i} width {width}: state={state} paths={rough_paths} "
                      f"left={left_over} content={content_h} iframe={iframe_h} errors={errors}")
                if not ok:
                    failures.append((i, width))
                page.close()
        # No Rough.js: the plain SVG must still be a drawing.
        page = browser.new_page(viewport={"width": 700, "height": 600})
        page.set_content(page_for(SHOTS[0], 1, use_rough=False))
        shapes = page.evaluate("document.querySelectorAll('svg[data-seed] [data-sk]').length")
        state = page.evaluate("document.documentElement.getAttribute('data-sketch')")
        ok = shapes > 30 and state is None
        print(("ok  " if ok else "FAIL"), f"plain fallback: shapes={shapes} state={state}")
        if not ok:
            failures.append("fallback")
        browser.close()
    print("\nbrowser check:", "FAILED" if failures else "passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
