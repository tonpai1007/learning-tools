"""Markdown -> DOCX thesis converter (KMITL School of Engineering template).

Converts a Markdown thesis manuscript into a Word (.docx) file formatted
according to the KMITL thesis template/guideline (Rev.1, 28 Sep 2023):

- A4 paper, margins: top/right/bottom 1", left 1.5"
- TH Sarabun New font: 16pt body, 20pt English cover title, 24pt chapter titles,
  18pt major headings, 16pt subheadings, Cambria Math 11pt equations
- Page numbering per the guideline:
    * cover, title, copyright, approval sheet: no page numbers
    * Thai/English abstracts, acknowledgement, TOC, lists: Roman numerals
      (I, II, ...) bottom-center
    * chapters: Arabic numerals top-right, suppressed on the first page of
      every chapter (one Word section per chapter)
- Front matter pages generated from YAML metadata:
    cover, English title page, copyright, approval sheet, Thai abstract,
    English abstract, acknowledgement, Table of Contents,
    List of Tables, List of Figures
- Chapters rendered as "CHAPTER n" (20pt bold centered) + title (24pt bold centered)
- Table/figure captions use SEQ fields, so the List of Tables / List of
  Figures populate themselves when fields are updated (F9) in Word.

Usage:
    from lt.converters.thesis_docx import convert_thesis_md
    convert_thesis_md("thesis.md", "thesis.docx")

Markdown contract:
- YAML front matter between --- fences supplies metadata (title, author, year,
  degree, program, student_id, advisor, co_advisor, code, plan, abstract,
  abstract_thai, acknowledgement).
- "# Heading" starts a new chapter; "##" major heading; "###" subheading.
- Tables in GitHub pipe format (optional "Table: caption" line before);
  images ![caption](path); display math $$...$$.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is in requirements.txt
    yaml = None

THESIS_FONT = "TH Sarabun New"
MATH_FONT = "Cambria Math"

DEGREE_PHRASES = {
    "1.2": (
        "A THESIS SUBMITTED IN PARTIAL FULFILLMENT",
        "OF THE REQUIREMENT FOR THE DEGREE OF",
        "OF ENGINEERING IN",
    ),
    "1.1": (
        "A THESIS SUBMITTED IN FULFILLMENT",
        "OF THE REQUIREMENT FOR THE DEGREE OF",
        "OF ENGINEERING IN",
    ),
}

DEFAULT_META: dict[str, str] = {
    "title": "Thesis Title in English",
    "author": "Name Surname",
    "year": "20XX",
    "degree": "Doctor of Engineering",
    "program": "Civil Engineering",
    "student_id": "XXXXXXXX",
    "advisor": "Prof. Dr. Thesis Advisor",
    "co_advisor": "Assoc. Prof. Dr. Co-Thesis Advisor",
    "code": "KMITL-20XX-EN-X-XXX-XXX",
    "plan": "1.2",
}

# Thai-language thesis (front matter "lang: th"): Thai labels and Thai cover
# per the KMITL Thai thesis form (แบบฟอร์มการจัดรูปเล่มวิทยานิพนธ์ภาษาไทย).
LABELS: dict[str, dict[str, str]] = {
    "en": {
        "chapter": "CHAPTER {n}", "table": "Table", "figure": "Figure",
        "toc": "TABLE OF CONTENTS", "lot": "LIST OF TABLES", "lof": "LIST OF FIGURES",
        "ack": "ACKNOWLEDGEMENT", "abstract_th": "บทคัดย่อ", "abstract_en": "ABSTRACT IN ENGLISH",
    },
    "th": {
        "chapter": "บทที่ {n}", "table": "ตารางที่", "figure": "รูปที่",
        "toc": "สารบัญ", "lot": "สารบัญตาราง", "lof": "สารบัญรูป",
        "ack": "กิตติกรรมประกาศ", "abstract_th": "บทคัดย่อ", "abstract_en": "ABSTRACT",
    },
}

# Template profiles: institution names, label wording and typography that
# differ between KMITL thesis manuals. Select with front matter "template:".
PROFILES: dict[str, dict[str, Any]] = {
    # School of Engineering guideline (Rev.1, 28 Sep 2023) — default
    "kmitl-eng": {
        "font": "TH Sarabun New", "math_font": "Cambria Math", "math_pt": 11,
        "faculty_th": "คณะวิศวกรรมศาสตร์", "faculty_en": "SCHOOL OF ENGINEERING",
        "student_id_th": "รหัสประจำตัว", "advisor_th": "อาจารย์ที่ปรึกษาวิทยานิพนธ์",
        "co_advisor_th": "อาจารย์ที่ปรึกษาวิทยานิพนธ์ร่วม", "thesis_en": "Thesis",
        "title_th_pt": 20, "title_en_pt": 20, "toc_tc": False,
    },
    # College manual (คู่มือจัดทำวิทยานิพนธ์ วิทยาลัยนวัตกรรมการจัดการข้อมูล):
    # TH SarabunPSK; cover title 20pt Thai / 18pt English; equations Times New
    # Roman 11pt; TOC lists front matter and "บทที่ n ชื่อบท" with a "หน้า" header.
    "kmitl-cidm": {
        "font": "TH SarabunPSK", "math_font": "Times New Roman", "math_pt": 11,
        "faculty_th": "วิทยาลัยนวัตกรรมการจัดการข้อมูล",
        "faculty_en": "[COLLEGE NAME IN ENGLISH]",
        "student_id_th": "รหัสนักศึกษา", "advisor_th": "อาจารย์ผู้ควบคุมวิทยานิพนธ์",
        "co_advisor_th": "อาจารย์ผู้ควบคุมวิทยานิพนธ์ร่วม", "thesis_en": "Thesis Title",
        "title_th_pt": 20, "title_en_pt": 18, "toc_tc": True,
    },
}
_P: dict[str, Any] = dict(PROFILES["kmitl-eng"])   # active profile


def _set_profile(meta: dict[str, Any]) -> None:
    """Activate the template profile; front matter keys override it."""
    global THESIS_FONT, MATH_FONT, _P
    _P = dict(PROFILES.get(str(meta.get("template", "kmitl-eng")), PROFILES["kmitl-eng"]))
    for key in ("font", "faculty_th", "faculty_en"):
        if meta.get(key):
            _P[key] = str(meta[key])
    if meta.get("faculty"):
        _P["faculty_th"] = str(meta["faculty"])
    THESIS_FONT = _P["font"]
    MATH_FONT = _P["math_font"]


THAI_DEGREE_PHRASES = {
    "1.2": "วิทยานิพนธ์นี้เป็นส่วนหนึ่งของการศึกษาตามหลักสูตรปริญญา",
    "1.1": "วิทยานิพนธ์นี้สำหรับการศึกษาตามหลักสูตรปริญญา",
}

UNNUMBERED_RE = re.compile(r"\s*\{-\}\s*$")


def _labels(meta: dict[str, Any]) -> dict[str, str]:
    return LABELS.get(str(meta.get("lang", "en")).lower(), LABELS["en"])


def _en(meta: dict[str, Any], key: str) -> str:
    """English-side value: '<key>_en' when given (Thai thesis), else '<key>'."""
    return str(meta.get(f"{key}_en") or meta.get(key, ""))


THAI_ABSTRACT_PLACEHOLDER = (
    "เขียนบทคัดย่อภาษาไทยที่นี่ ความยาวประมาณ 200–250 คำ "
    "โดยเน้นประเด็นสำคัญของงานวิจัย วิธีการดำเนินงาน และผลการศึกษาที่สำคัญ"
)
ENGLISH_ABSTRACT_PLACEHOLDER = (
    "Replace this text with a 200-250 word abstract summarizing the research "
    "problem, methodology, and key findings."
)


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------

def _apply_cs_font(run_or_style_element: Any, name: str) -> None:
    """Also set complex-script and East-Asian font names (needed for Thai)."""
    rpr = run_or_style_element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:cs"), name)
    rfonts.set(qn("w:eastAsia"), name)


def _style_font(style: Any, size: float, bold: bool = False, name: str | None = None) -> None:
    from docx.shared import RGBColor
    name = name or THESIS_FONT   # resolved at call time (profile may change it)
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)   # built-in headings default to theme blue
    _apply_cs_font(style.element, name)
    # Mark complex-script text as Thai so Word applies Thai word breaking
    # (without it, Thai lines only break at spaces or mid-word).
    rpr = style.element.get_or_add_rPr()
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = rpr.makeelement(qn("w:lang"), {})
        rpr.append(lang)
    lang.set(qn("w:val"), "en-US")
    lang.set(qn("w:bidi"), "th-TH")


def _run_font(run: Any, size: float | None = None, bold: bool | None = None,
              italic: bool | None = None, name: str | None = None) -> None:
    name = name or THESIS_FONT
    run.font.name = name
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    _apply_cs_font(run._element, name)


def _field_run(run: Any, instr: str, cached_text: str = "") -> None:
    """Append a complex field (begin/instr/separate/[cached]/end) to a run."""
    base = run._element
    fld_begin = base.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "begin"})
    instr_el = base.makeelement(qn("w:instrText"), {})
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = f" {instr} "
    fld_sep = base.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "separate"})
    parts = [fld_begin, instr_el, fld_sep]
    if cached_text:
        cached = base.makeelement(qn("w:t"), {})
        cached.set(qn("xml:space"), "preserve")
        cached.text = cached_text
        parts.append(cached)
    parts.append(base.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "end"}))
    for el in parts:
        base.append(el)


def _add_page_field(paragraph: Any, fmt: str = "decimal") -> None:
    """Insert a PAGE field: fmt 'decimal' (1,2,3) or 'ROMAN' (I,II,III)."""
    run = paragraph.add_run()
    _run_font(run, 16)
    instr = f"PAGE \\* {fmt}" if fmt != "decimal" else "PAGE"
    _field_run(run, instr)


def _add_toc_field(paragraph: Any, instr: str, hint: str) -> None:
    """Insert a TOC-type field (e.g. standard TOC or \\c caption lists)."""
    run = paragraph.add_run()
    _run_font(run, 16)
    _field_run(run, instr, cached_text=hint)


def _add_tc(paragraph: Any, text: str, level: int = 1) -> None:
    """Hidden TC entry so the TOC lists this line (profiles with toc_tc)."""
    if not _P.get("toc_tc"):
        return
    run = paragraph.add_run()
    _run_font(run, 16)
    safe = _tw(text).replace('"', "'")
    _field_run(run, f'TC "{safe}" \\l {level}')


def _add_seq_caption(paragraph: Any, label: str, seq_name: str,
                     chapter: int, number: int, caption: str) -> None:
    """Caption line: 'Table 3.1 caption text' using a SEQ field for the number.

    The chapter number is literal (deterministic at render time) and the
    sequence number is a SEQ field restarting at Heading 1 (\\s 1), so the
    TOC \\c "<label>" list pages collect these captions on field update.
    """
    r = paragraph.add_run(f"{label} {chapter}.")
    _run_font(r, 16, bold=True)
    run = paragraph.add_run()
    _run_font(run, 16, bold=True)
    _field_run(run, f"SEQ {seq_name} \\* ARABIC \\s 1", cached_text=str(number))
    r = paragraph.add_run(" ")
    _run_font(r, 16, bold=True)
    _add_inline(paragraph, caption)


def _centered(doc: Document, text: str, size: float, bold: bool = False,
              space_after: float = 0, space_before: float = 0) -> Any:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    if text:
        r = p.add_run(_tw(text))
        _run_font(r, size, bold=bold)
    return p


# --------------------------------------------------------------------------
# Math: LaTeX -> MathML (latex2mathml) -> OMML (Office MML2OMML.XSL)
# --------------------------------------------------------------------------

_MML2OMML_CANDIDATES = (
    r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL",
    r"C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL",
)
_omml_xslt: Any = None
_omml_checked = False


def _get_omml_xslt() -> Any:
    """Load Office's MathML->OMML stylesheet once; None if unavailable."""
    global _omml_xslt, _omml_checked
    if _omml_checked:
        return _omml_xslt
    _omml_checked = True
    import os
    try:
        import latex2mathml.converter  # noqa: F401
        from lxml import etree
    except ImportError:
        return None
    paths = [os.environ.get("MML2OMML_XSL", "")] + list(_MML2OMML_CANDIDATES)
    for p in paths:
        if p and Path(p).exists():
            try:
                _omml_xslt = etree.XSLT(etree.parse(p))
            except Exception:
                _omml_xslt = None
            break
    return _omml_xslt


def _latex_to_omml(latex: str) -> Any:
    """Return an <m:oMath> lxml element for a LaTeX expression, or None."""
    xslt = _get_omml_xslt()
    if xslt is None:
        return None
    try:
        import latex2mathml.converter
        from docx.oxml import parse_xml
        from lxml import etree
        mathml = latex2mathml.converter.convert(latex.strip())
        omml = xslt(etree.fromstring(mathml.encode("utf-8")))
        return parse_xml(etree.tostring(omml.getroot()))
    except Exception:
        return None


def _set_omath_font(omath: Any, size: float) -> None:
    """Cambria Math at the given size on every math run."""
    half_points = str(int(size * 2))
    for r in omath.iter(qn("m:r")):
        rpr = r.find(qn("w:rPr"))
        if rpr is None:
            rpr = r.makeelement(qn("w:rPr"), {})
            mrpr = r.find(qn("m:rPr"))
            r.insert(1 if mrpr is not None else 0, rpr)
        for tag in ("w:rFonts", "w:sz", "w:szCs"):
            old = rpr.find(qn(tag))
            if old is not None:
                rpr.remove(old)
        rpr.append(rpr.makeelement(qn("w:rFonts"), {
            qn("w:ascii"): MATH_FONT, qn("w:hAnsi"): MATH_FONT, qn("w:cs"): MATH_FONT}))
        rpr.append(rpr.makeelement(qn("w:sz"), {qn("w:val"): half_points}))
        rpr.append(rpr.makeelement(qn("w:szCs"), {qn("w:val"): half_points}))


def _add_math(paragraph: Any, latex: str, size: float) -> None:
    """Append a native Word equation; fall back to plain Cambria Math text."""
    omath = _latex_to_omml(latex)
    if omath is not None:
        _set_omath_font(omath, size)
        paragraph._p.append(omath)
    else:
        r = paragraph.add_run(latex.strip())
        _run_font(r, size, name=MATH_FONT)


INLINE_RE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`|\$[^$\n]+?\$)")


# Thai thesis: insert zero-width word-break hints (see thai_wordbreak.py).
_THAI_WORD_BREAKS = False


def _tw(text: str) -> str:
    if not _THAI_WORD_BREAKS:
        return text
    from lt.converters.thai_wordbreak import add_thai_word_breaks
    return add_thai_word_breaks(text)


def _add_inline(paragraph: Any, text: str, size: float = 16) -> None:
    """Add text honoring **bold**, *italic*, `code` and $math$ markers."""
    text = _tw(text)
    for token in INLINE_RE.split(text):
        if not token:
            continue
        if token.startswith("$") and token.endswith("$") and len(token) > 2:
            _add_math(paragraph, token[1:-1], 12)
        elif token.startswith("**") and token.endswith("**"):
            r = paragraph.add_run(token[2:-2])
            _run_font(r, size, bold=True)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            r = paragraph.add_run(token[1:-1])
            _run_font(r, size, italic=True)
        elif token.startswith("`") and token.endswith("`"):
            r = paragraph.add_run(token[1:-1])
            # Consolas looks ~40% larger than TH Sarabun New at the same pt size.
            _run_font(r, round(size * 0.7), name="Consolas")
        else:
            r = paragraph.add_run(token)
            _run_font(r, size)


# --------------------------------------------------------------------------
# Page setup, styles, section configuration
# --------------------------------------------------------------------------

def _setup_page(section: Any) -> None:
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.5)
    section.right_margin = Inches(1.0)


def _setup_styles(doc: Document, thai: bool = False) -> None:
    normal = doc.styles["Normal"]
    _style_font(normal, 16)
    pf = normal.paragraph_format
    pf.first_line_indent = Inches(0.5)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    if thai:
        # KMITL Thai form uses Thai Distributed justification for body text.
        pf.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY

    _style_font(doc.styles["Heading 1"], 24, bold=True)   # chapter title
    h1 = doc.styles["Heading 1"].paragraph_format
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.first_line_indent = Inches(0)
    h1.space_before = Pt(0)
    h1.space_after = Pt(18)        # one blank line before the body text

    _style_font(doc.styles["Heading 2"], 18, bold=True)   # major heading
    h2 = doc.styles["Heading 2"].paragraph_format
    h2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h2.first_line_indent = Inches(0)
    h2.space_before = Pt(18)       # one line above
    h2.space_after = Pt(6)

    _style_font(doc.styles["Heading 3"], 16, bold=True)   # subheading
    h3 = doc.styles["Heading 3"].paragraph_format
    h3.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h3.first_line_indent = Inches(0.5)   # 7 character spaces
    h3.space_before = Pt(9)        # half a line above
    h3.space_after = Pt(3)

    # List of tables / figures entries ("ตารางที่ 2.1 ..."): flush left with a
    # hanging indent so wrapped captions align with the caption text.
    from docx.enum.style import WD_STYLE_TYPE
    try:
        tof = doc.styles["table of figures"]
    except KeyError:
        tof = doc.styles.add_style("table of figures", WD_STYLE_TYPE.PARAGRAPH)
        tof.base_style = normal
        # Declare it as Word's built-in style, not a custom one; otherwise
        # Word swaps in its default definition when it updates the field.
        if tof.element.get(qn("w:customStyle")) is not None:
            del tof.element.attrib[qn("w:customStyle")]
        tof.element.set(qn("w:styleId"), "TableofFigures")
    tof_pf = tof.paragraph_format
    tof_pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tof_pf.left_indent = Inches(0.85)
    tof_pf.first_line_indent = Inches(-0.85)

    for list_style in ("List Bullet", "List Number"):
        try:
            _style_font(doc.styles[list_style], 16)
            doc.styles[list_style].paragraph_format.first_line_indent = Inches(0)
        except KeyError:  # pragma: no cover
            pass


def _restart_page_numbers(section: Any, fmt: str = "decimal") -> None:
    """Start this section's page numbering at 1 (I for the Roman section):
    the abstract is page I and Chapter 1 is page 1, not a continuation of
    the unnumbered cover pages. The number format must be set on the
    section too, or TOC entries show Arabic numbers for Roman pages."""
    sect_pr = section._sectPr
    pg = sect_pr.find(qn("w:pgNumType"))
    if pg is None:
        pg = sect_pr.makeelement(qn("w:pgNumType"), {})
        sect_pr.append(pg)
    pg.set(qn("w:start"), "1")
    pg.set(qn("w:fmt"), fmt)


def _configure_roman_footer(section: Any) -> None:
    """Unnumbered→Roman footer: PAGE \\* ROMAN bottom-center (abstract onward)."""
    _restart_page_numbers(section, fmt="upperRoman")
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.first_line_indent = Inches(0)
    _add_page_field(fp, fmt="ROMAN")


def _configure_body_section(section: Any) -> None:
    """Chapter sections: Arabic PAGE field top-right, none on chapter first page."""
    _restart_page_numbers(section)
    section.header_distance = Inches(0.5)   # page number 0.5" from the top edge
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    section.different_first_page_header_footer = True
    hp = section.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.paragraph_format.first_line_indent = Inches(0)
    _add_page_field(hp, fmt="decimal")


# --------------------------------------------------------------------------
# Front matter pages
# --------------------------------------------------------------------------

def _cover_lines(meta: dict[str, str]) -> list[tuple[str, float, bool, float]]:
    phrase = DEGREE_PHRASES.get(str(meta["plan"]), DEGREE_PHRASES["1.2"])
    return [
        (_en(meta, "title"), _P["title_en_pt"], True, 12),
        (_en(meta, "author"), _P["title_en_pt"], True, 12),
        (phrase[0], 18, False, 0),
        (phrase[1], 18, False, 0),
        (f"{_en(meta, 'degree').upper()} IN {_en(meta, 'program').upper()}", 18, False, 12),
        (_P["faculty_en"], 18, False, 0),
        ("KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG", 18, False, 12),
        (_en(meta, "year"), 18, False, 0),
        (meta["code"], 18, False, 0),
    ]


def _thai_cover_lines(meta: dict[str, str]) -> list[tuple[str, float, bool, float]]:
    """Thai cover / Thai title page: Thai+English title and names (no
    honorifics), Thai degree phrase, faculty, institute, B.E. year, code."""
    phrase = THAI_DEGREE_PHRASES.get(str(meta["plan"]), THAI_DEGREE_PHRASES["1.2"])
    return [
        (meta["title"], _P["title_th_pt"], True, 6),
        (_en(meta, "title"), _P["title_en_pt"], True, 24),
        (meta["author"], _P["title_th_pt"], True, 0),
        (_en(meta, "author"), _P["title_en_pt"], True, 36),
        (f"{phrase}{meta['degree']}", 18, False, 0),
        (f"สาขาวิชา{meta['program']}", 18, False, 0),
        (_P["faculty_th"], 18, False, 0),
        ("สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง", 18, False, 12),
        (f"พ.ศ. {meta['year']}", 18, False, 0),
        (meta["code"], 18, False, 0),
    ]


def _render_cover(doc: Document, meta: dict[str, str], thai: bool = False) -> None:
    for _ in range(3):
        _centered(doc, "", 18)
    lines = _thai_cover_lines(meta) if thai else _cover_lines(meta)
    for text, size, bold, after in lines:
        _centered(doc, text, size, bold=bold, space_after=after)
    doc.add_page_break()


def _render_copyright(doc: Document, meta: dict[str, str]) -> None:
    for _ in range(22):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    lines = (f"COPYRIGHT {_en(meta, 'year')}", _P["faculty_en"],
             "KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG")
    for i, line in enumerate(lines):
        r = p.add_run(line + ("\n" if i < len(lines) - 1 else ""))
        _run_font(r, 16, bold=False)
    doc.add_page_break()


def _render_approval_sheet(doc: Document, meta: dict[str, str]) -> None:
    """Placeholder approval page (issued by the graduate school; signed by the
    Dean after the final defense)."""
    if _labels(meta) is LABELS["th"]:
        faculty = _P["faculty_th"]
        _centered(doc, faculty, 18, bold=True, space_after=0)
        _centered(doc, "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง", 18, bold=True)
        _centered(doc, "ใบรับรองวิทยานิพนธ์", 24, bold=True, space_after=18)
        _centered(doc, meta["title"], 18, bold=True, space_after=6)
        _centered(doc, meta["author"], 16, space_after=4)
        _centered(doc, f"{meta['degree']} สาขาวิชา{meta['program']}", 16, space_after=4)
        _centered(doc, f"หมายเลขวิทยานิพนธ์ {meta['code']}", 16, space_after=24)
        _centered(doc, "คณะกรรมการสอบวิทยานิพนธ์", 16, space_after=18)
        # the faculty already starts with "คณะ" / "วิทยาลัย"; the dean signs for it
        signers = [
            ("ประธานกรรมการ", ""),
            (_P["advisor_th"], meta["advisor"]),
            ("กรรมการ", ""),
            ("กรรมการ", ""),
            (f"คณบดี{faculty}", ""),
        ]
    else:
        _centered(doc, "APPROVAL SHEET", 24, bold=True, space_after=18)
        _centered(doc, meta["title"], 18, bold=True, space_after=6)
        _centered(doc, f"by {meta['author']}", 16, space_after=4)
        _centered(doc, f"{meta['degree']} in {meta['program']}", 16, space_after=24)
        _centered(doc, "Approved by the Thesis Examination Committee:", 16, space_after=18)
        signers = [
            ("Thesis Advisor", meta["advisor"]),
            ("Committee Chairperson", ""),
            ("Committee Member", ""),
            ("Committee Member", ""),
            ("Dean of the School of Engineering", ""),
        ]
    for role, name in signers:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.space_after = Pt(24)
        r = p.add_run(f"{role} ............................................")
        _run_font(r, 16)
        if name:
            r2 = p.add_run(f"  ({name})")
            _run_font(r2, 16)


def _render_abstract(doc: Document, meta: dict[str, str], thai: bool = False) -> None:
    labels = _labels(meta)
    if thai and labels is LABELS["th"]:
        rows = [
            ("หัวข้อวิทยานิพนธ์", meta["title"]),
            ("นักศึกษา", meta["author"]),
            (_P["student_id_th"], meta["student_id"]),
            ("ปริญญา", meta["degree"]),
            ("สาขาวิชา", meta["program"]),
            ("พ.ศ.", str(meta["year"])),
            (_P["advisor_th"], meta["advisor"]),
            (_P["co_advisor_th"], meta["co_advisor"]),
        ]
    else:
        rows = [
            (_P["thesis_en"], _en(meta, "title")),
            ("Student", _en(meta, "author")),
            ("Student ID.", meta["student_id"]),
            ("Degree", _en(meta, "degree")),
            ("Program", _en(meta, "program")),
            ("Year", _en(meta, "year")),
            ("Thesis Advisor", _en(meta, "advisor")),
            ("Co-Thesis Advisor", _en(meta, "co_advisor")),
        ]
    table = doc.add_table(rows=len(rows), cols=2)
    table.autofit = False
    widths = (Inches(2.3), Inches(3.45))   # label column fits Thai labels
    for i, (label, value) in enumerate(rows):
        cells = table.rows[i].cells
        for c, w in zip(cells, widths):
            c.width = w
            c.paragraphs[0].paragraph_format.first_line_indent = Inches(0)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = cells[0].paragraphs[0].add_run(label)
        _run_font(r, 16, bold=True)
        r = cells[1].paragraphs[0].add_run(_tw(str(value)))
        _run_font(r, 16)
    _centered(doc, "", 16, space_after=12)
    heading = labels["abstract_th"] if thai else labels["abstract_en"]
    hp = _centered(doc, heading, 24, bold=True, space_after=12)
    _add_tc(hp, "บทคัดย่อภาษาไทย" if thai else "บทคัดย่อภาษาอังกฤษ")
    if thai:
        abstract = meta.get("abstract_thai") or THAI_ABSTRACT_PLACEHOLDER
    else:
        abstract = meta.get("abstract") or ENGLISH_ABSTRACT_PLACEHOLDER
    for chunk in str(abstract).split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        p = doc.add_paragraph()
        _add_inline(p, chunk)
    doc.add_page_break()


def _render_acknowledgement(doc: Document, meta: dict[str, str]) -> None:
    hp = _centered(doc, _labels(meta)["ack"], 24, bold=True, space_after=12)
    _add_tc(hp, _labels(meta)["ack"])
    ack = meta.get("acknowledgement") or (
        "The author would like to express sincere gratitude to the thesis advisor "
        "and everyone who contributed to the successful completion of this thesis."
    )
    for chunk in str(ack).split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        p = doc.add_paragraph()
        _add_inline(p, chunk)
    _centered(doc, "", 16, space_after=12)
    _centered(doc, meta["author"], 16, space_after=0)
    doc.add_page_break()


def _page_header_line(doc: Document, left: str = "") -> None:
    """'หน้า' flush right (optionally 'ตารางที่' / 'รูปที่' flush left)."""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.tab_stops.add_tab_stop(Inches(5.77), alignment=2)  # RIGHT
    _run_font(p.add_run(f"{left}\tหน้า"), 16, bold=True)


def _render_toc(doc: Document, title: str = "TABLE OF CONTENTS") -> None:
    hp = _centered(doc, title, 24, bold=True, space_after=12)
    if _P.get("toc_tc"):
        # Front matter and chapter lines come from TC entries ("บทที่ n ชื่อบท"),
        # section headings from outline levels 2-3; "หน้า" header on the right.
        _add_tc(hp, title)
        _page_header_line(doc)
        instr = 'TOC \\o "2-3" \\f \\l "1-1" \\h \\z \\u'
    else:
        instr = 'TOC \\o "1-3" \\h \\z \\u'
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0)
    _add_toc_field(p, instr,
                   "Right-click and choose 'Update Field' to build the table of contents.")
    # No trailing page-break paragraph: when the updated TOC fills its last
    # page, that paragraph spills over and leaves a blank page. The next list
    # heading starts a new page instead (page_break_before). The field's final
    # (empty) paragraph keeps this paragraph's format, so make it 1pt high.
    from docx.enum.text import WD_LINE_SPACING
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(1)
    p.paragraph_format.space_after = Pt(0)


def _render_list_page(doc: Document, title: str, seq_name: str,
                      new_page: bool = False) -> None:
    """LIST OF TABLES / LIST OF FIGURES page driven by a TOC \\c field."""
    h = doc.add_paragraph(style="Heading 1")
    h.paragraph_format.page_break_before = new_page
    r = h.add_run(title)
    _run_font(r, 24, bold=True)
    _add_tc(h, title)
    if _P.get("toc_tc"):
        _page_header_line(doc, "ตารางที่" if seq_name == "Table" else "รูปที่")
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0)
    _add_toc_field(p, f'TOC \\c "{seq_name}" \\h \\z',
                   "Update fields (F9) to build this list from SEQ captions.")


# --------------------------------------------------------------------------
# Body rendering
# --------------------------------------------------------------------------

class _BodyRenderer:
    def __init__(self, doc: Document, base_dir: Path,
                 labels: dict[str, str] | None = None):
        self.doc = doc
        self.base_dir = base_dir
        self.labels = labels or LABELS["en"]
        self.sections_started = 0
        self.in_bibliography = False
        self.chapter = 0
        self.table_no = 0
        self.figure_no = 0
        self.equation_no = 0
        self.pending_table: list[list[str]] = []

    # -- blocks -------------------------------------------------------------
    def flush_table(self) -> None:
        """Materialize buffered markdown table rows as a Word table."""
        if not self.pending_table:
            return
        rows = [r for r in self.pending_table
                if not all(re.fullmatch(r":?-{2,}:?", c or "---") for c in r)]
        self.pending_table = []
        if not rows:
            return
        col_count = max(len(r) for r in rows)
        table = self.doc.add_table(rows=len(rows), cols=col_count)
        table.style = "Table Grid"
        for r_i, row in enumerate(rows):
            for c_i in range(col_count):
                cell = table.cell(r_i, c_i)
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.first_line_indent = Inches(0)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                _add_inline(p, row[c_i] if c_i < len(row) else "", size=16)
                if r_i == 0:
                    for run in p.runs:
                        run.font.bold = True
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(6)
        spacer.paragraph_format.first_line_indent = Inches(0)

    def add_table_caption(self, caption: str) -> None:
        """'Table x.y Caption' line above the table (SEQ field for the number)."""
        self.table_no += 1
        p = self.doc.add_paragraph()
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.space_before = Pt(18)    # one blank line before the caption
        p.paragraph_format.keep_with_next = True
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _add_seq_caption(p, self.labels["table"], "Table", self.chapter, self.table_no, caption)

    def add_image(self, caption: str, path: str) -> None:
        img = Path(path)
        if not img.is_absolute():
            img = self.base_dir / img
        if not img.exists():
            fallback = self.base_dir / Path(path).name
            if fallback.exists():
                img = fallback
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.space_before = Pt(18)    # one blank line before the figure
        p.paragraph_format.keep_with_next = True
        if img.exists():
            try:
                pic = p.add_run().add_picture(str(img), width=Inches(5.0))
                # Keep tall figures (plus caption) within the 9.69" text block.
                max_h = Inches(7.0)
                if pic.height > max_h:
                    ratio = max_h / pic.height
                    pic.width = int(pic.width * ratio)
                    pic.height = max_h
            except Exception:
                _add_inline(p, f"[missing image: {path}]")
        else:
            _add_inline(p, f"[missing image: {path}]")
        self.figure_no += 1
        cap = self.doc.add_paragraph()
        # Caption centred when it fits on one line, else flush left (manual 3.9);
        # ~80 characters of TH Sarabun 16pt fit the 5.77" text width.
        one_line = len(caption) + len(self.labels["figure"]) + 6 <= 80
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER if one_line else WD_ALIGN_PARAGRAPH.LEFT
        cap.paragraph_format.first_line_indent = Inches(0)
        cap.paragraph_format.space_after = Pt(18)   # one blank line after
        _add_seq_caption(cap, self.labels["figure"], "Figure", self.chapter, self.figure_no, caption)

    def add_equation(self, expr: str) -> None:
        self.equation_no += 1
        p = self.doc.add_paragraph()
        p.paragraph_format.first_line_indent = Inches(0)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(16)    # one line above and below
        p.paragraph_format.space_after = Pt(16)
        # center tab + right tab for "(n.m)" on the right margin
        p.paragraph_format.tab_stops.add_tab_stop(Inches(2.6))
        p.paragraph_format.tab_stops.add_tab_stop(Inches(5.77), alignment=2)  # RIGHT
        _run_font(p.add_run("\t"), 16)
        _add_math(p, expr, _P["math_pt"])
        _run_font(p.add_run(f"\t({self.chapter}.{self.equation_no})"), 16)

    def add_chapter(self, title: str) -> None:
        # Every chapter after the first starts a new Word section so the first
        # page of every chapter can omit the page number (different-first-page
        # is already configured on the shared body sectPr).
        # "# Title {-}" is an unnumbered chapter (e.g. bibliography): no
        # "CHAPTER n" label and no chapter number increment.
        unnumbered = bool(UNNUMBERED_RE.search(title))
        title = UNNUMBERED_RE.sub("", title)
        if self.sections_started >= 1:
            sec = self.doc.add_section(WD_SECTION_START.NEW_PAGE)
            # add_section copies the previous sectPr, including the
            # restart-at-1 of the first chapter; later chapters continue.
            pg = sec._sectPr.find(qn("w:pgNumType"))
            if pg is not None and pg.get(qn("w:start")) is not None:
                del pg.attrib[qn("w:start")]
        self.sections_started += 1
        self.in_bibliography = unnumbered and bool(
            re.search(r"บรรณานุกรม|เอกสารอ้างอิง|bibliography|references", title, re.IGNORECASE))
        clean = re.sub(r"[*`]", "", title.strip())
        if not unnumbered:
            self.chapter += 1
            self.table_no = self.figure_no = self.equation_no = 0
            label = self.doc.add_paragraph()
            label.alignment = WD_ALIGN_PARAGRAPH.CENTER
            label.paragraph_format.first_line_indent = Inches(0)
            label.paragraph_format.space_before = Pt(0)
            label.paragraph_format.keep_with_next = True
            chapter_label = self.labels["chapter"].format(n=self.chapter)
            r = label.add_run(chapter_label)
            _run_font(r, 20, bold=True)
            _add_tc(label, f"{chapter_label} {clean}")
        h = self.doc.add_paragraph(style="Heading 1")
        _add_inline(h, title.strip(), size=24)
        if unnumbered:
            _add_tc(h, clean)

    def add_heading(self, level: int, title: str) -> None:
        style = "Heading 2" if level == 2 else "Heading 3"
        h = self.doc.add_paragraph(style=style)
        h.paragraph_format.keep_with_next = True
        _add_inline(h, title.strip(), size=18 if level == 2 else 16)

    def add_paragraph(self, text: str) -> None:
        p = self.doc.add_paragraph()
        if getattr(self, "in_bibliography", False):
            # Bibliography entry: flush left, continuation lines indented
            # 7 character spaces (hanging indent), no blank line between.
            pf = p.paragraph_format
            pf.left_indent = Inches(0.5)
            pf.first_line_indent = Inches(-0.5)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _add_inline(p, text)

    def add_list_item(self, text: str, ordered: bool, number: str = "") -> None:
        if ordered:
            # Literal "n." with a hanging indent: Word's single List Number
            # sequence would otherwise keep counting across separate lists.
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Inches(0.75)
            pf.first_line_indent = Inches(-0.25)
            pf.tab_stops.add_tab_stop(Inches(0.75))
            _run_font(p.add_run(f"{number}.\t"), 16)
        else:
            p = self.doc.add_paragraph(style="List Bullet")
        _add_inline(p, text)

    def add_code_block(self, code: str) -> None:
        for line in code.split("\n"):
            p = self.doc.add_paragraph()
            p.paragraph_format.first_line_indent = Inches(0)
            r = p.add_run(line)
            _run_font(r, 14, name="Consolas")


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")
MATH_RE = re.compile(r"^\$\$(.+?)\$\$\s*$")


def render_body(doc: Document, body_md: str, base_dir: Path,
                labels: dict[str, str] | None = None) -> None:
    renderer = _BodyRenderer(doc, base_dir, labels)
    lines = body_md.split("\n")
    in_code = False
    code_lines: list[str] = []
    prev_nonempty = ""

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                renderer.flush_table()
                renderer.add_code_block("\n".join(code_lines))
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not renderer.pending_table:
                # First row of a table: an optional preceding "Table: caption"
                # line becomes the numbered caption above the table.
                cap = re.match(r"^table\s*:\s*(.+)$", prev_nonempty, re.IGNORECASE)
                if cap:
                    renderer.add_table_caption(cap.group(1))
            renderer.pending_table.append(cells)
            continue

        renderer.flush_table()

        if not stripped:
            continue
        prev_nonempty = stripped

        m = HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            if level == 1:
                renderer.add_chapter(title)
            else:
                renderer.add_heading(level, title)
            continue

        m = IMAGE_RE.match(stripped)
        if m:
            renderer.add_image(m.group(1), m.group(2))
            continue

        m = MATH_RE.match(stripped)
        if m:
            renderer.add_equation(m.group(1))
            continue

        if re.match(r"^[-*]\s+", stripped):
            renderer.add_list_item(re.sub(r"^[-*]\s+", "", stripped), ordered=False)
            continue

        m = re.match(r"^(\d+)[.)]\s+(.*)", stripped)
        if m:
            renderer.add_list_item(m.group(2), ordered=True, number=m.group(1))
            continue

        # "Table: caption" is consumed by the following table's first row.
        if re.match(r"^table\s*:", stripped, re.IGNORECASE):
            continue

        if stripped.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.5)
            _add_inline(p, stripped[2:], size=16)
            for run in p.runs:
                run.font.italic = True
            continue

        renderer.add_paragraph(stripped)

    renderer.flush_table()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def parse_front_matter(md_text: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from the markdown body."""
    meta: dict[str, Any] = {}
    body = md_text
    if md_text.lstrip().startswith("---"):
        parts = md_text.lstrip().split("---", 2)
        if len(parts) == 3 and yaml is not None:
            try:
                loaded = yaml.safe_load(parts[1]) or {}
                if isinstance(loaded, dict):
                    meta = loaded
                body = parts[2]
            except yaml.YAMLError:
                body = md_text
    return meta, body


def convert_thesis_md(
    md_path: str | Path,
    output_docx: str | Path | None = None,
    meta_overrides: dict[str, Any] | None = None,
    skip_approval_sheet: bool = False,
) -> Path:
    """Convert a Markdown thesis manuscript into a KMITL-formatted .docx file.

    Page-number architecture (per the guideline):
      section 0: cover / title / copyright / approval sheet  -> no numbers
      section 1: abstracts / acknowledgement / TOC / lists   -> Roman, bottom-center
      section 2+: one section per chapter                    -> Arabic, top-right,
                 suppressed on each chapter's first page

    Args:
        md_path: source .md file (may include YAML front matter).
        output_docx: destination path; defaults to the .md path with .docx suffix.
        meta_overrides: values that take precedence over front matter fields.
        skip_approval_sheet: omit the approval-sheet placeholder page.

    Returns:
        Path to the generated .docx file.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    md_text = md_path.read_text(encoding="utf-8-sig")
    front, body_md = parse_front_matter(md_text)

    meta: dict[str, str] = dict(DEFAULT_META)
    for key, value in front.items():
        meta[str(key)] = value
    if meta_overrides:
        for key, value in meta_overrides.items():
            if value:
                meta[str(key)] = value

    if output_docx is None:
        output_docx = md_path.with_suffix(".docx")
    output_docx = Path(output_docx)

    _set_profile(meta)                    # fonts, faculty names, label wording
    labels = _labels(meta)
    thai = labels is LABELS["th"]
    global _THAI_WORD_BREAKS
    _THAI_WORD_BREAKS = thai and str(meta.get("thai_word_breaks", "true")).lower() != "false"
    if _THAI_WORD_BREAKS:
        from lt.converters import thai_wordbreak
        thai_wordbreak.NO_BREAK = {str(w) for w in (meta.get("thai_no_break") or [])}

    doc = Document()
    _setup_styles(doc, thai=thai)
    _setup_page(doc.sections[0])          # section 0: unnumbered front pages

    _render_cover(doc, meta, thai=thai)   # 1. cover page
    if thai:
        _render_cover(doc, meta, thai=True)  # 1b. Thai title page (same as cover)
    _render_cover(doc, meta)              # 2. English title page
    _render_copyright(doc, meta)          # 3. copyright page
    if not skip_approval_sheet:
        _render_approval_sheet(doc, meta)  # 4. approval sheet placeholder

    # Section 1: Roman-numbered front matter (abstract starts at page I)
    roman = doc.add_section(WD_SECTION_START.NEW_PAGE)
    _setup_page(roman)
    _configure_roman_footer(roman)

    _render_abstract(doc, meta, thai=True)   # 5. Thai abstract
    _render_abstract(doc, meta, thai=False)  # 6. English abstract
    _render_acknowledgement(doc, meta)       # 7. acknowledgement
    _render_toc(doc, labels["toc"])          # 8. table of contents
    _render_list_page(doc, labels["lot"], "Table", new_page=True)  # 9. list of tables
    _render_list_page(doc, labels["lof"], "Figure")   # 10. list of figures

    # Section 2: chapters, Arabic numbers top-right (suppressed per chapter start)
    body = doc.add_section(WD_SECTION_START.NEW_PAGE)
    _setup_page(body)
    _configure_body_section(body)

    render_body(doc, body_md, md_path.parent, labels)

    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return output_docx
