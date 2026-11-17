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


def _style_font(style: Any, size: float, bold: bool = False, name: str = THESIS_FONT) -> None:
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    _apply_cs_font(style.element, name)


def _run_font(run: Any, size: float | None = None, bold: bool | None = None,
              italic: bool | None = None, name: str = THESIS_FONT) -> None:
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
        r = p.add_run(text)
        _run_font(r, size, bold=bold)
    return p


INLINE_RE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`)")


def _add_inline(paragraph: Any, text: str, size: float = 16) -> None:
    """Add text honoring **bold**, *italic* and `code` markers."""
    for token in INLINE_RE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            r = paragraph.add_run(token[2:-2])
            _run_font(r, size, bold=True)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            r = paragraph.add_run(token[1:-1])
            _run_font(r, size, italic=True)
        elif token.startswith("`") and token.endswith("`"):
            r = paragraph.add_run(token[1:-1])
            _run_font(r, size - 2, name="Consolas")
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


def _setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    _style_font(normal, 16)
    pf = normal.paragraph_format
    pf.first_line_indent = Inches(0.5)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0

    _style_font(doc.styles["Heading 1"], 24, bold=True)   # chapter title
    h1 = doc.styles["Heading 1"].paragraph_format
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.first_line_indent = Inches(0)
    h1.space_before = Pt(0)
    h1.space_after = Pt(12)

    _style_font(doc.styles["Heading 2"], 18, bold=True)   # major heading
    h2 = doc.styles["Heading 2"].paragraph_format
    h2.first_line_indent = Inches(0)
    h2.space_before = Pt(12)
    h2.space_after = Pt(6)

    _style_font(doc.styles["Heading 3"], 16, bold=True)   # subheading
    h3 = doc.styles["Heading 3"].paragraph_format
    h3.first_line_indent = Inches(0.5)
    h3.space_before = Pt(6)
    h3.space_after = Pt(3)

    for list_style in ("List Bullet", "List Number"):
        try:
            _style_font(doc.styles[list_style], 16)
            doc.styles[list_style].paragraph_format.first_line_indent = Inches(0)
        except KeyError:  # pragma: no cover
            pass


def _configure_roman_footer(section: Any) -> None:
    """Unnumbered→Roman footer: PAGE \\* ROMAN bottom-center (abstract onward)."""
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.first_line_indent = Inches(0)
    _add_page_field(fp, fmt="ROMAN")


def _configure_body_section(section: Any) -> None:
    """Chapter sections: Arabic PAGE field top-right, none on chapter first page."""
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
    phrase = DEGREE_PHRASES.get(meta["plan"], DEGREE_PHRASES["1.2"])
    return [
        (meta["title"], 20, True, 12),
        (meta["author"], 20, True, 12),
        (phrase[0], 18, False, 0),
        (phrase[1], 18, False, 0),
        (f"{phrase[2]} {meta['program']}", 18, False, 12),
        ("SCHOOL OF ENGINEERING", 18, False, 0),
        ("KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG", 18, False, 12),
        (str(meta["year"]), 18, False, 0),
        (meta["code"], 18, False, 0),
    ]


def _render_cover(doc: Document, meta: dict[str, str]) -> None:
    for _ in range(3):
        _centered(doc, "", 18)
    for text, size, bold, after in _cover_lines(meta):
        _centered(doc, text, size, bold=bold, space_after=after)
    doc.add_page_break()


def _render_copyright(doc: Document, meta: dict[str, str]) -> None:
    for _ in range(22):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    lines = (f"COPYRIGHT {meta['year']}", "SCHOOL OF ENGINEERING",
             "KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG")
    for i, line in enumerate(lines):
        r = p.add_run(line + ("\n" if i < len(lines) - 1 else ""))
        _run_font(r, 16, bold=False)
    doc.add_page_break()


def _render_approval_sheet(doc: Document, meta: dict[str, str]) -> None:
    """Placeholder approval page (issued by the graduate school; signed by the
    Dean after the final defense)."""
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
    rows = [
        ("Thesis", meta["title"]),
        ("Student", meta["author"]),
        ("Student ID.", meta["student_id"]),
        ("Degree", meta["degree"]),
        ("Program", meta["program"]),
        ("Year", str(meta["year"])),
        ("Thesis Advisor", meta["advisor"]),
        ("Co-Thesis Advisor", meta["co_advisor"]),
    ]
    table = doc.add_table(rows=len(rows), cols=2)
    for i, (label, value) in enumerate(rows):
        cells = table.rows[i].cells
        r = cells[0].paragraphs[0].add_run(label)
        _run_font(r, 16, bold=True)
        r = cells[1].paragraphs[0].add_run(value)
        _run_font(r, 16)
    _centered(doc, "", 16, space_after=12)
    heading = "บทคัดย่อ" if thai else "ABSTRACT IN ENGLISH"
    _centered(doc, heading, 24, bold=True, space_after=12)
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
    _centered(doc, "ACKNOWLEDGEMENT", 24, bold=True, space_after=12)
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


def _render_toc(doc: Document) -> None:
    _centered(doc, "TABLE OF CONTENTS", 24, bold=True, space_after=12)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0)
    _add_toc_field(p, 'TOC \\o "1-3" \\h \\z \\u',
                   "Right-click and choose 'Update Field' to build the table of contents.")
    doc.add_page_break()


def _render_list_page(doc: Document, title: str, seq_name: str) -> None:
    """LIST OF TABLES / LIST OF FIGURES page driven by a TOC \\c field."""
    h = doc.add_paragraph(style="Heading 1")
    r = h.add_run(title)
    _run_font(r, 24, bold=True)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0)
    _add_toc_field(p, f'TOC \\c "{seq_name}" \\h \\z',
                   "Update fields (F9) to build this list from SEQ captions.")


# --------------------------------------------------------------------------
# Body rendering
# --------------------------------------------------------------------------

class _BodyRenderer:
    def __init__(self, doc: Document, base_dir: Path):
        self.doc = doc
        self.base_dir = base_dir
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
        p.paragraph_format.space_before = Pt(6)
        _add_seq_caption(p, "Table", "Table", self.chapter, self.table_no, caption)

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
        if img.exists():
            try:
                p.add_run().add_picture(str(img), width=Inches(5.0))
            except Exception:
                _add_inline(p, f"[missing image: {path}]")
        else:
            _add_inline(p, f"[missing image: {path}]")
        self.figure_no += 1
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.first_line_indent = Inches(0)
        _add_seq_caption(cap, "Figure", "Figure", self.chapter, self.figure_no, caption)

    def add_equation(self, expr: str) -> None:
        self.equation_no += 1
        p = self.doc.add_paragraph()
        p.paragraph_format.first_line_indent = Inches(0)
        # center tab + right tab for "(n.m)" on the right margin
        p.paragraph_format.tab_stops.add_tab_stop(Inches(2.6))
        p.paragraph_format.tab_stops.add_tab_stop(Inches(6.0), alignment=2)  # RIGHT
        _run_font(p.add_run("\t"), 16)
        r = p.add_run(expr.strip())
        _run_font(r, 11, name=MATH_FONT)
        _run_font(p.add_run(f"\t({self.chapter}.{self.equation_no})"), 16)

    def add_chapter(self, title: str) -> None:
        # Chapters 2+ start a new Word section so the first page of every
        # chapter can omit the page number (different-first-page is already
        # configured on the shared body sectPr).
        if self.chapter >= 1:
            self.doc.add_section(WD_SECTION_START.NEW_PAGE)
        self.chapter += 1
        self.table_no = self.figure_no = self.equation_no = 0
        label = self.doc.add_paragraph()
        label.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label.paragraph_format.first_line_indent = Inches(0)
        label.paragraph_format.space_before = Pt(0)
        r = label.add_run(f"CHAPTER {self.chapter}")
        _run_font(r, 20, bold=True)
        h = self.doc.add_paragraph(style="Heading 1")
        _add_inline(h, title.strip(), size=24)

    def add_heading(self, level: int, title: str) -> None:
        style = "Heading 2" if level == 2 else "Heading 3"
        h = self.doc.add_paragraph(style=style)
        _add_inline(h, title.strip(), size=18 if level == 2 else 16)

    def add_paragraph(self, text: str) -> None:
        p = self.doc.add_paragraph()
        _add_inline(p, text)

    def add_list_item(self, text: str, ordered: bool) -> None:
        style = "List Number" if ordered else "List Bullet"
        p = self.doc.add_paragraph(style=style)
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


def render_body(doc: Document, body_md: str, base_dir: Path) -> None:
    renderer = _BodyRenderer(doc, base_dir)
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
            renderer.add_list_item(m.group(2), ordered=True)
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

    doc = Document()
    _setup_styles(doc)
    _setup_page(doc.sections[0])          # section 0: unnumbered front pages

    _render_cover(doc, meta)              # 1. cover page
    _render_cover(doc, meta)              # 2. English title page (same content)
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
    _render_toc(doc)                         # 8. table of contents
    _render_list_page(doc, "LIST OF TABLES", "Table")    # 9. list of tables
    _render_list_page(doc, "LIST OF FIGURES", "Figure")  # 10. list of figures

    # Section 2: chapters, Arabic numbers top-right (suppressed per chapter start)
    body = doc.add_section(WD_SECTION_START.NEW_PAGE)
    _setup_page(body)
    _configure_body_section(body)

    render_body(doc, body_md, md_path.parent)

    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return output_docx
