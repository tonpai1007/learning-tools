"""KMITL thesis template compliance linter.

Validates a generated thesis .docx against the School of Engineering
thesis guideline (Rev.1, 28 Sep 2023) formatting rules:

- A4 paper (210 x 297 mm)
- Margins: top/right/bottom 1 inch, left 1.5 inches
- Normal style: TH Sarabun New, 16 pt (with complex-script font for Thai)
- Heading 1: 24 pt bold (chapter titles), Heading 2: 18 pt bold (major),
  Heading 3: 16 pt bold (subheadings)
- Front matter: Roman numeral page fields in the footer
- Main body: Arabic page fields in the header
- Chapter structure: "CHAPTER n" labels paired with Heading 1 titles

Usage:
    from lt.thesis_lint import lint_thesis_docx
    report = lint_thesis_docx("thesis.docx")

    python -m lt lint-thesis thesis.docx
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn

THESIS_FONT = "TH Sarabun New"
MM_TOL = 1.5      # mm tolerance for page size
INCH_TOL = 0.05   # inch tolerance for margins
PT_TOL = 0.6      # pt tolerance for font sizes


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def _style_font_info(doc: Document, style_name: str) -> dict[str, Any]:
    try:
        style = doc.styles[style_name]
    except KeyError:
        return {"missing": True}
    font = style.font
    rpr = style.element.find(qn("w:rPr"))
    cs = None
    if rpr is not None:
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is not None:
            cs = rfonts.get(qn("w:cs"))
    size = font.size.pt if font.size else None
    return {"name": font.name, "size": size, "bold": font.bold, "cs": cs}


def _has_page_field(paragraph_xml: str, fmt: str | None = None) -> bool:
    if "PAGE" not in paragraph_xml:
        return False
    if fmt is None:
        return True
    return fmt in paragraph_xml


def lint_thesis_docx(docx_path: str | Path) -> dict[str, Any]:
    """Run all template checks against a .docx file and return a report.

    Returns a dict with:
        checks   - list of {check, status: pass|warn|fail, detail}
        summary  - {passed, warnings, failures, compliant}
    """
    path = Path(docx_path)
    if not path.exists():
        raise FileNotFoundError(f"Word document not found: {path}")

    doc = Document(str(path))
    checks: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # 1. Paper size (A4)
    # ------------------------------------------------------------------
    sec = doc.sections[0]
    width_mm = sec.page_width.mm if sec.page_width else 0
    height_mm = sec.page_height.mm if sec.page_height else 0
    if abs(width_mm - 210) <= MM_TOL and abs(height_mm - 297) <= MM_TOL:
        checks.append(_check("Paper size A4 (210x297 mm)", "pass",
                             f"{width_mm:.0f} x {height_mm:.0f} mm"))
    else:
        checks.append(_check("Paper size A4 (210x297 mm)", "fail",
                             f"found {width_mm:.0f} x {height_mm:.0f} mm"))

    # ------------------------------------------------------------------
    # 2. Margins
    # ------------------------------------------------------------------
    expected = {
        "top": (sec.top_margin, 1.0),
        "bottom": (sec.bottom_margin, 1.0),
        "right": (sec.right_margin, 1.0),
        "left": (sec.left_margin, 1.5),
    }
    for name, (value, want) in expected.items():
        actual = value.inches if value else 0
        if abs(actual - want) <= INCH_TOL:
            checks.append(_check(f"{name} margin {want}\"", "pass", f"{actual:.2f}\""))
        else:
            checks.append(_check(f"{name} margin {want}\"", "fail", f"found {actual:.2f}\""))

    # ------------------------------------------------------------------
    # 3. Normal style font (TH Sarabun New 16pt + Thai complex script)
    # ------------------------------------------------------------------
    normal = _style_font_info(doc, "Normal")
    if normal.get("missing"):
        checks.append(_check("Normal style exists", "fail", "style missing"))
    else:
        name_ok = (normal["name"] or "").startswith("TH Sarabun")
        size_ok = normal["size"] is not None and abs(normal["size"] - 16) <= PT_TOL
        cs_ok = (normal["cs"] or "").startswith("TH Sarabun")
        if name_ok and size_ok:
            checks.append(_check("Normal style: TH Sarabun New 16pt", "pass",
                                 f"{normal['name']} {normal['size']}pt"))
        else:
            checks.append(_check("Normal style: TH Sarabun New 16pt", "fail",
                                 f"{normal['name']} {normal['size']}pt"))
        checks.append(_check("Normal style Thai complex-script font", "pass" if cs_ok else "fail",
                             f"w:cs = {normal['cs']}"))

    # ------------------------------------------------------------------
    # 4. Heading styles
    # ------------------------------------------------------------------
    heading_spec = {
        "Heading 1": (24, True),   # chapter titles
        "Heading 2": (18, True),   # major headings
        "Heading 3": (16, True),   # subheadings
    }
    for style_name, (size, bold) in heading_spec.items():
        info = _style_font_info(doc, style_name)
        if info.get("missing"):
            checks.append(_check(f"{style_name}: {size}pt bold", "warn", "style not defined"))
            continue
        size_ok = info["size"] is not None and abs(info["size"] - size) <= PT_TOL
        bold_ok = info["bold"] in (True, None)  # None inherits; treat as ok
        status = "pass" if size_ok and bold_ok else "fail"
        checks.append(_check(f"{style_name}: {size}pt bold", status,
                             f"{info['name']} {info['size']}pt bold={info['bold']}"))

    # ------------------------------------------------------------------
    # 5. Page numbering: Roman footer (front matter), Arabic header (body)
    # ------------------------------------------------------------------
    if len(doc.sections) >= 2:
        front, body = doc.sections[0], doc.sections[1]
        ftr_xml = front.footer.paragraphs[0]._p.xml if front.footer.paragraphs else ""
        hdr_xml = body.header.paragraphs[0]._p.xml if body.header.paragraphs else ""
        checks.append(_check("Front matter Roman numerals in footer", "pass"
                             if _has_page_field(ftr_xml, "ROMAN") else "fail",
                             "footer PAGE \\* ROMAN field"))
        checks.append(_check("Body Arabic numerals in header", "pass"
                             if _has_page_field(hdr_xml) else "fail",
                             "header PAGE field"))
    else:
        checks.append(_check("Two sections (front matter / body)", "warn",
                             f"only {len(doc.sections)} section found"))

    # ------------------------------------------------------------------
    # 6. Chapter structure
    # ------------------------------------------------------------------
    chapter_labels = [p.text.strip() for p in doc.paragraphs
                      if re.fullmatch(r"CHAPTER \d+", p.text.strip())]
    h1_texts = [p.text.strip() for p in doc.paragraphs if p.style.name == "Heading 1"]
    if chapter_labels:
        numbers = [int(c.split()[1]) for c in chapter_labels]
        sequential = numbers == list(range(1, len(numbers) + 1))
        paired = len(chapter_labels) == len(h1_texts)
        status = "pass" if sequential and paired else "warn"
        detail = f"{len(chapter_labels)} chapters; sequential={sequential}; paired_with_h1={paired}"
        checks.append(_check("Chapter labels (CHAPTER n)", status, detail))
    else:
        checks.append(_check("Chapter labels (CHAPTER n)", "warn", "no CHAPTER labels found"))

    # ------------------------------------------------------------------
    # 7. Body run fonts (warn on stray fonts, ignore math/code styles)
    # ------------------------------------------------------------------
    allowed = {THESIS_FONT, "Cambria Math", "Consolas", None}
    stray: dict[str, int] = {}
    for p in doc.paragraphs:
        if p.style.name.startswith("Heading") or p.style.name in ("List Bullet", "List Number"):
            continue
        for run in p.runs:
            fname = run.font.name
            if fname and fname not in allowed and not fname.startswith("TH Sarabun"):
                stray[fname] = stray.get(fname, 0) + 1
    if stray:
        top = ", ".join(f"{k} x{v}" for k, v in sorted(stray.items(), key=lambda x: -x[1])[:3])
        checks.append(_check("Body runs use TH Sarabun New", "warn", f"stray fonts: {top}"))
    else:
        checks.append(_check("Body runs use TH Sarabun New", "pass", "no stray fonts"))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    failures = sum(1 for c in checks if c["status"] == "fail")
    warnings = sum(1 for c in checks if c["status"] == "warn")
    passed = sum(1 for c in checks if c["status"] == "pass")
    return {
        "path": str(path),
        "checks": checks,
        "summary": {
            "passed": passed,
            "warnings": warnings,
            "failures": failures,
            "compliant": failures == 0,
        },
    }


def format_report(report: dict[str, Any]) -> str:
    """Human-readable one-line-per-check report."""
    lines = [f"Thesis template compliance: {report['path']}"]
    icon = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL"}
    for c in report["checks"]:
        lines.append(f"  [{icon[c['status']]}] {c['check']} - {c['detail']}")
    s = report["summary"]
    verdict = "COMPLIANT" if s["compliant"] else "NOT COMPLIANT"
    lines.append(f"  {verdict}: {s['passed']} passed, {s['warnings']} warnings, {s['failures']} failures")
    return "\n".join(lines)


def lint_thesis_docx_json(docx_path: str | Path) -> str:
    """JSON string variant for API/MCP consumers."""
    return json.dumps(lint_thesis_docx(docx_path), ensure_ascii=False, indent=2)
