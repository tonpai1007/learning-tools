"""Thai word-break hints for DOCX output.

Thai is written without spaces between words. Word only wraps Thai at word
boundaries when Thai proofing support is installed in Office; otherwise it
breaks lines at spaces only (and Thai Distributed justification then
stretches letters across the gap). Inserting ZERO WIDTH SPACE (U+200B) at
word boundaries gives every renderer (Word, LibreOffice, Google Docs) legal
break points, independent of the reader's Office language packs.

Boundaries come from Windows Uniscribe (usp10.dll ScriptBreak), which uses
the system Thai dictionary. On non-Windows systems, or if Uniscribe fails,
text is returned unchanged.
"""

from __future__ import annotations

import ctypes
import re
import sys

ZWSP = "​"
_THAI_RUN = re.compile(r"[฀-๿]{2,}")


class _ScriptAnalysis(ctypes.Structure):
    # WORD bitfields (eScript:10, fRTL:1, ...) + SCRIPT_STATE (WORD)
    _fields_ = [("bits", ctypes.c_uint16), ("state", ctypes.c_uint16)]


class _ScriptItem(ctypes.Structure):
    _fields_ = [("iCharPos", ctypes.c_int), ("a", _ScriptAnalysis)]


_usp10 = None
if sys.platform == "win32":
    try:
        _usp10 = ctypes.WinDLL("usp10")
    except OSError:  # pragma: no cover
        _usp10 = None


def _soft_breaks(text: str) -> list[int]:
    """Indexes i where a line may break before text[i] (Uniscribe fSoftBreak)."""
    n = len(text)
    buf = ctypes.create_unicode_buffer(text, n + 1)
    max_items = n + 2
    items = (_ScriptItem * (max_items + 1))()
    count = ctypes.c_int(0)
    hr = _usp10.ScriptItemize(buf, n, max_items, None, None, items, ctypes.byref(count))
    if hr != 0:
        return []
    breaks: list[int] = []
    for k in range(count.value):
        start = items[k].iCharPos
        end = items[k + 1].iCharPos if k + 1 <= count.value else n
        length = end - start
        if length <= 0:
            continue
        attrs = (ctypes.c_ubyte * length)()
        sub = ctypes.create_unicode_buffer(text[start:end], length + 1)
        if _usp10.ScriptBreak(sub, length, ctypes.byref(items[k].a), attrs) != 0:
            continue
        for j in range(1, length):
            if attrs[j] & 0x01:  # fSoftBreak
                breaks.append(start + j)
    return breaks


def _break_run(run: str) -> str:
    try:
        cuts = _soft_breaks(run)
    except Exception:
        return run
    if not cuts:
        return run
    out, prev = [], 0
    for c in cuts:
        out.append(run[prev:c])
        prev = c
    out.append(run[prev:])
    return ZWSP.join(out)


# Words that must never be split (proper names the dictionary does not know),
# e.g. set from thesis front matter "thai_no_break: [ออกัสวอเตอร์]".
NO_BREAK: set[str] = set()


def add_thai_word_breaks(text: str) -> str:
    """Insert U+200B between Thai words; unchanged if Uniscribe is unavailable."""
    if _usp10 is None or ZWSP in text:
        return text
    out = _THAI_RUN.sub(lambda m: _break_run(m.group(0)), text)
    for word in NO_BREAK:
        # remove any break hint that landed inside the protected word
        pattern = "​?".join(re.escape(ch) for ch in word)
        out = re.sub(pattern, word, out)
    return out


def available() -> bool:
    return _usp10 is not None
