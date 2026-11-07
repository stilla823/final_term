"""Write rough_bundle.py: the pinned Rough.js build, embedded in a normal Python file.

The app needs no extra folder or download. Rough.js travels inside rough_bundle.py, together with its
MIT license text. The source of truth is vendor/rough/rough.js (official roughjs 4.6.6 build, see
vendor/rough/README.md). Run this only when you update that file:

    python tools/embed_rough.py
"""
import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vendor" / "rough" / "rough.js"
LICENSE = (ROOT / "vendor" / "rough" / "LICENSE").read_text(encoding="utf-8").strip()
VERSION = "4.6.6"

data = SRC.read_bytes()
digest = hashlib.sha256(data).hexdigest()
b64 = base64.b64encode(data).decode("ascii")
chunks = [b64[i:i + 96] for i in range(0, len(b64), 96)]
body = "\n".join(f'    "{c}"' for c in chunks)

text = f'''"""Rough.js {VERSION}, embedded so the app needs no extra files or downloads.

Rough.js is a library for hand-drawn style graphics: https://github.com/rough-stuff/rough
This is the official, unmodified browser build (`bundled/rough.js` from the `roughjs` {VERSION} package),
stored below as base64 text. Its SHA-256 is checked before use, so a damaged or edited copy is never run.
The readable file is in vendor/rough/rough.js; tools/embed_rough.py regenerates this module from it.

The license below applies to the embedded Rough.js code (not to the rest of this project).

{LICENSE}
"""
import base64
import hashlib

VERSION = "{VERSION}"
SHA256 = "{digest}"
LICENSE_TEXT = """{LICENSE}"""

_DATA = (
{body}
)


def source():
    """The Rough.js code as text, or None if the embedded copy does not match SHA256."""
    try:
        raw = base64.b64decode("".join(_DATA))
    except ValueError:
        return None
    if hashlib.sha256(raw).hexdigest() != SHA256:
        return None
    return raw.decode("utf-8")
'''
(ROOT / "rough_bundle.py").write_text(text, encoding="utf-8")
print("wrote rough_bundle.py", len(text), "bytes; sha256", digest)
