# Between the Lines

A small Streamlit prototype for a university design project. Film students and beginner filmmakers type a short dialogue scene (one or two characters) and get a three-shot storyboard. Each shot has a shot size, a **camera angle**, a camera position, character placement, an acting note and a reason tied to the directing intention. Optional before-scene and after-scene suggestions are shown separately and never added to the script.

The user interface is in Korean. Code and this README are in English.

## Camera language

The app treats the camera as the main tool for showing what a scene means. Each shot is chosen from two things: a composition template (what is in the frame) and a camera angle (where the camera stands).

| Camera angle | What the camera does | Usual effect on the audience |
| --- | --- | --- |
| Low angle | Sits below the character and looks up | The character looks large and in control |
| Eye level | Sits at the character's eye height | Neutral; characters look equal |
| High angle | Sits above the character and looks down | The character looks small, vulnerable, anxious |

The panels are drawn to match: a low angle shows a ceiling and looming figures, a high angle shows a wide floor and small figures. Each card also has a small side view of where the camera stands and a plan view (seen from above) of where the camera and the characters are. These effects are common conventions, not rules, and the app says so. Shot size (wide, medium, close-up) and frame composition (over-the-shoulder, empty space) are handled the same way.

In the sample scene the first shot is at eye level (A and B look equal), then the camera moves above B for the close-up and the wide shot, so B looks small and anxious while A is gone.

## Status

| Feature | State |
| --- | --- |
| Demo mode with the saved sample (default) | Working |
| Input checks with Korean error messages | Working, covered by tests |
| Three-shot cards, hand-drawn SVG panels (Rough.js), camera height and plan view drawings | Working, checked in headless Chromium inside a Streamlit-style iframe |
| Gaze arrows and character poses in the panels | Working, covered by tests and the browser check |
| AI suggestions in a separate section | Working |
| Edited input in demo mode never shows the saved result | Working, covered by tests |
| Live mode with a local model | **Scaffolded.** Adapter and output checks are tested against a stub server only. It has not been run against a real model. |
| `app.py` inside a running Streamlit server | **Not run in the environment where this was written** (no access to the Python package index). Run the first-launch check below. |
| Dutch angle, lens, camera movement | Planned |

### Known limits of the drawings

- Figures are simple schematic people. Hands and arms are drawn as simple limbs, so small poses are hard to read in wide shots, and in a close-up only the head position (lowered, turned away) is visible.
- Each character has one gaze and one pose per shot. A change inside the shot ("looks at A, then looks away") is described in the acting note, not drawn.
- The only prop is a door. Furniture, windows and outdoor backgrounds are not drawn; an outdoor scene still uses the indoor corridor template.
- The Streamlit HTML component is sandboxed. The sketch page asks the browser to resize its frame; if that is blocked, the frame keeps a fixed height that fits the content.

## Storyboard drawings (Rough.js)

Each panel is a quick film storyboard sketch that shows four things:

- **Framing**: wide, medium or over-the-shoulder close-up, written on the panel (`WS`, `MS`, `OTS CU`) together with the angle (`LOW`, `EYE`, `HIGH`).
- **Placement**: where A and B stand in the frame, plus a small plan view from above with the camera, its field of view and the door.
- **Gaze**: a dashed red line with an arrowhead from the character's head to what they look at (the other character, the door, away, down). The line passes behind the other figure when it crosses it. An absent character is a dashed outline marked "빈 자리".
- **Action**: a visible pose for each character (stand, hold the door, reach out, arms pulled in, head lowered, turned away, walking away).

The hand-drawn look comes from [Rough.js](https://github.com/rough-stuff/rough) (MIT). How it works:

1. `storyboard.py` writes plain SVG. Every shape has a `data-sk` attribute and ordinary SVG attributes (fill, stroke, dash). This SVG is already a complete, clean drawing.
2. `sketch.py` wraps the SVG in a small HTML page with Rough.js (version 4.6.6, unmodified, checked against a SHA-256 hash) and a short script that redraws each marked shape with Rough.js. A fixed seed per panel keeps the lines the same on every rerun.
3. `app.py` shows that page with `st.components.v1.html`. The page resizes its iframe to fit when the browser allows it, and has a fixed fallback height otherwise.
4. If Rough.js does not match its checksum, or the component cannot be shown, the app falls back to the same card with plain (not hand-drawn) images and prints the reason under the storyboard.

**Rough.js is inside the code.** It is embedded in `rough_bundle.py` (the official file stored as text, with its license), so there is nothing to download, install or upload separately. The app only needs the `.py` files, `data/`, `requirements.txt` and `.streamlit/`. `vendor/rough/` keeps the readable original and `tools/embed_rough.py` rebuilds `rough_bundle.py` from it.

Each shot in `data/demo.json` (and in a live model reply) has optional `gaze`, `actions` and `props` fields, for example `"gaze": {"B": "door"}, "actions": {"A": "hold_door"}`. The allowed values are in `scene.py` (`GAZE_TARGETS`, `ACTIONS`). If they are missing, characters look at each other and stand still. If they are present but not one of the allowed values, the reply is rejected like any other invalid reply.

The Rough.js license notice is in `THIRD_PARTY_NOTICES.md`, `vendor/rough/LICENSE` and the header of `rough_bundle.py`, and is also written into every sketch page.

## Setup

Python 3.10 or newer.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the address Streamlit prints (usually http://localhost:8501).

### First-launch check

1. The page opens in demo mode with the label "현재 모드: 데모 모드".
2. Press **예시 불러오기**, then **스토리보드 만들기**. Three cards appear with three different panels, the second line `B: 괜찮아. 먼저 가.` appears exactly, and the third card shows "대사 없음".
3. Below the cards, the separate "AI 연출 제안" section appears.
4. Change one character of the dialogue and press **스토리보드 만들기** again. You get a message that custom scenes need live AI mode, and no storyboard.
5. In a two-character scene, type `C: 안녕`. The error names the line and says only A and B are available.

Each card shows the panel as a hand-drawn sketch with two small diagrams under it. If a panel area stays empty or is cut off, your Streamlit version may block HTML components; the app then shows the plain-image card instead. If the images are broken in that fallback, switch the renderer in `cards.py` from `<img>` data URIs to `st.html`.

## Loading the sample

Press **예시 불러오기**. It fills the form with the sample scene from `data/demo.json`:

- Characters: 2
- Location: 실내 (indoor)
- Directing intention: B는 같이 가고 싶지만 붙잡지 못한다.
- Dialogue: `A: 너도 같이 갈래?` / `B: 괜찮아. 먼저 가.`

## Demo mode and live mode

| | Demo mode (default) | Live mode |
| --- | --- | --- |
| Needs | Nothing | A local model server |
| Works for | The unchanged sample scene only | Any valid scene |
| Result | Saved by hand in `data/demo.json` | Generated by the model, then checked |
| Label | "데모 모드 · 저장된 예시 결과" | "라이브 AI 모드 · model name" |

If you edit the sample in demo mode, the app explains that custom scenes need live mode and offers to reload the sample. It never shows the saved storyboard as if it were made for your edited input.

### Live mode

Live mode talks to a locally running model through an OpenAI-compatible chat endpoint (for example Ollama or llama.cpp's server). Configure it outside the code with two environment variables, then switch on the toggle in the app:

```bash
# macOS / Linux
export BTL_LLM_ENDPOINT=http://localhost:11434/v1/chat/completions
export BTL_LLM_MODEL=your-model-name

# Windows PowerShell
$env:BTL_LLM_ENDPOINT = "http://localhost:11434/v1/chat/completions"
$env:BTL_LLM_MODEL = "your-model-name"
```

Set them in the **same terminal** you use to run `streamlit run app.py`, before you start it; a terminal opened later does not see them. The same steps, with the Ollama install, are shown in the app under "라이브 모드 설정 방법" whenever live mode is not set up.

`BTL_LLM_TIMEOUT` (seconds, default 120) is optional. The model code lives only in `model_adapter.py`.

The input fields are inside one Streamlit form, so nothing you type is sent or reset until you press **스토리보드 만들기**.

Before anything is shown, the reply is checked: exactly three shots; valid character, template and camera angle IDs; roles that fit the template; and dialogue line IDs that cover every original line exactly once and in order. The dialogue on screen is looked up from the user's input by ID, so the model cannot rewrite it. If a check fails, the app says so and offers to retry or load the demo.

**Proposed model:** not chosen yet. Pick a model with a license that allows free use, check that it runs on your computer and writes acceptable Korean, then record its name and license here.

Live mode cannot work on Streamlit Community Cloud, because the cloud server cannot reach a model running on your own computer. Use live mode locally.

## Data and licenses

Everything in the default demo was created for this project. No film stills, published scripts or third-party images are used.

| Item | File | Source | License |
| --- | --- | --- | --- |
| Sample scene and saved result | `data/demo.json` | Written by the author | CC BY 4.0 |
| Composition templates | `data/templates.json` | Designed by the author | CC BY 4.0 |
| Camera angle catalog | `data/camera_grammar.json` | Author's own summary of common film-grammar conventions | CC BY 4.0 |
| Panel drawings | `storyboard.py`, `sketch.py` | Drawn in code | MIT (with the code) |
| Hand-drawn rendering | `rough_bundle.py` (readable copy: `vendor/rough/rough.js`) | [Rough.js](https://github.com/rough-stuff/rough) 4.6.6 by Preet Shihn, unmodified | MIT, see `THIRD_PARTY_NOTICES.md` |
| Code | `*.py` | Author | MIT, see `LICENSE` |

The user's scene is kept only in the current browser session and is not saved.

## Project layout

```
app.py              Streamlit page (draws what pipeline.py returns)
pipeline.py         Decides what to show: invalid, demo, edited input, live, error
scene.py            Dialogue parsing and checks, validation of model output
storyboard.py       SVG panels: template x camera angle x gaze x action, plus camera height and plan view diagrams
sketch.py           Wraps the SVG with Rough.js into the HTML page the app shows
rough_bundle.py     Rough.js 4.6.6 embedded as text, with its license (generated, do not edit)
cards.py            HTML for cards, suggestions and the angle reference box
model_adapter.py    Live mode: prompt, local model call, JSON extraction
data/               Templates, camera angle catalog, sample scene and saved result
tests/              Checks that do not need Streamlit
docs/index.html     Design Spec page for GitHub Pages
vendor/rough/       Readable copy of Rough.js 4.6.6 (unmodified), its LICENSE and how it was checked
tools/              embed_rough.py rebuilds rough_bundle.py; bake_spec_panels.py rebuilds the sketches inside docs/index.html
THIRD_PARTY_NOTICES.md
```

## Tests

```bash
python tests/test_checks.py
python tests/browser_check.py     # optional: needs Playwright and Chromium
```

These cover dialogue input and error messages, the saved demo, validation of model output, the demo-versus-edited-input rule, the live adapter against a stub, HTML escaping, that every template, angle, gaze and action draws valid SVG, that gaze and actions change the picture, that the bundled Rough.js is the pinned file with its license, and that the fallback works. They do not start Streamlit. `browser_check.py` loads each demo shot in a sandboxed iframe like the one Streamlit uses and checks that Rough.js ran without errors, that every marked shape was redrawn, and that the iframe resizes to fit.

## Publishing

- **Design Spec page (GitHub Pages):** in the repository settings open Pages, choose "Deploy from a branch", branch `main`, folder `/docs`. The page has no JavaScript; its sketches are baked in. After changing `storyboard.py`, run `python tools/bake_spec_panels.py` to refresh them.
- **One repository for everything:** keep a single repository. To update, open it on GitHub, choose Add file, Upload files, drag in the contents of the unzipped project (files with the same name are replaced), and commit. Pages and Streamlit Community Cloud redeploy by themselves.
- **"Error installing requirements" on Streamlit Cloud:** `requirements.txt` must be in the top folder and contain only the word `streamlit`. Delete any other dependency file you did not add on purpose (`Pipfile`, `pyproject.toml`, `environment.yml`, `uv.lock`, `packages.txt`). Under Manage app, Settings, choose Python 3.12, then reboot the app. The last `ERROR:` line in the Manage app terminal names the exact cause.
- **Running app (Streamlit Community Cloud):** GitHub Pages cannot run Python. Sign in at share.streamlit.io with GitHub, choose "Create app", pick this repository and branch, set the main file to `app.py`, and deploy. The cloud app runs in demo mode.
