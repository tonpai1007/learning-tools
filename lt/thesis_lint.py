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
    # Resolve through the basedOn chain: Word drops properties that equal the
    # base style's when it saves (e.g. Heading 3 16pt == Normal 16pt).
    name = size = bold = cs = None
    s = style
    while s is not None:
        font = s.font
        name = name if name is not None else font.name
        if size is None and font.size:
            size = font.size.pt
        bold = bold if bold is not None else font.bold
        if cs is None:
            rpr = s.element.find(qn("w:rPr"))
            rfonts = rpr.find(qn("w:rFonts")) if rpr is not None else None
            if rfonts is not None:
                cs = rfonts.get(qn("w:cs"))
        s = s.base_style
    return {"name": name, "size": size, "bold": bold, "cs": cs}


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
    # 5. Page numbering across sections:
    #    some section must carry Roman numerals in its footer (front matter)
    #    and body sections must carry Arabic PAGE fields in their header.
    # ------------------------------------------------------------------
    roman_found = False
    arabic_found = False
    for i, s in enumerate(doc.sections):
        if s.footer.paragraphs and _has_page_field(s.footer.paragraphs[0]._p.xml, "ROMAN"):
            roman_found = True
        if i >= 1 and s.header.paragraphs and _has_page_field(s.header.paragraphs[0]._p.xml):
            arabic_found = True
    checks.append(_check("Front matter Roman numerals in footer", "pass" if roman_found else "fail",
                         "footer PAGE \\* ROMAN field" if roman_found else "no Roman footer field in any section"))
    checks.append(_check("Body Arabic numerals in header", "pass" if arabic_found else "fail",
                         "header PAGE field" if arabic_found else "no Arabic header field in any body section"))

    # ------------------------------------------------------------------
    # 6. Required front-matter pages
    # ------------------------------------------------------------------
    # Strip U+200B Thai word-break hints inserted by the converter.
    all_text = "\n".join(p.text for p in doc.paragraphs).replace("​", "")
    if "บทคัดย่อ" in all_text:
        checks.append(_check("Thai abstract page", "pass", "found (Thai heading present)"))
    else:
        checks.append(_check("Thai abstract page", "warn", "not found"))
    if "APPROVAL SHEET" in all_text or "ใบรับรองวิทยานิพนธ์" in all_text:
        checks.append(_check("Approval sheet page", "pass", "found"))
    else:
        checks.append(_check("Approval sheet page", "warn", "not found"))
    if (("LIST OF TABLES" in all_text and "LIST OF FIGURES" in all_text)
            or ("สารบัญตาราง" in all_text and "สารบัญรูป" in all_text)):
        checks.append(_check("List of Tables / List of Figures pages", "pass", "found"))
    else:
        checks.append(_check("List of Tables / List of Figures pages", "warn", "not found"))
    if "SEQ" in "\n".join(p._p.xml for p in doc.paragraphs if p.text.strip()):
        checks.append(_check("SEQ caption fields (auto-numbered lists)", "pass", "found"))
    else:
        checks.append(_check("SEQ caption fields (auto-numbered lists)", "warn",
                             "captions are plain text; List of Tables/Figures will stay empty"))

    # ------------------------------------------------------------------
    # 7. Chapter structure
    # ------------------------------------------------------------------
    # English "CHAPTER n" or Thai "บทที่ n"; each label must be followed by a
    # Heading 1 title. Unnumbered chapters (bibliography) have no label.
    label_re = re.compile(r"(?:CHAPTER|บทที่)\s+(\d+)")
    paras = doc.paragraphs
    texts = [p.text.replace("​", "").strip() for p in paras]
    label_idx = [i for i, t in enumerate(texts) if label_re.fullmatch(t)]
    if label_idx:
        numbers = [int(label_re.fullmatch(texts[i]).group(1)) for i in label_idx]
        sequential = numbers == list(range(1, len(numbers) + 1))
        paired = all(i + 1 < len(paras) and paras[i + 1].style.name == "Heading 1"
                     for i in label_idx)
        status = "pass" if sequential and paired else "warn"
        detail = f"{len(label_idx)} chapters; sequential={sequential}; paired_with_h1={paired}"
        checks.append(_check("Chapter labels (CHAPTER n)", status, detail))
    else:
        checks.append(_check("Chapter labels (CHAPTER n)", "warn", "no CHAPTER labels found"))

    # ------------------------------------------------------------------
    # 8. Body run fonts (warn on stray fonts, ignore math/code styles)
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
