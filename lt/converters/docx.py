"""
MDIE HTML to Microsoft Word (.docx) Report Converter
Converts computational engineering HTML calculation sheets and academic project dossiers
into beautifully formatted, printable Microsoft Word (.docx) documents.
Supports optional AI-assisted Executive Summaries and Engineering Peer Reviews.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from bs4 import BeautifulSoup, NavigableString, Tag
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

try:
    from .ai import complete as lt_complete
except ImportError:
    try:
        from lt.ai import complete as lt_complete
    except ImportError:
        lt_complete = None

try:
    from mdie.ai.llm_router import LLMRouter
except ImportError:
    LLMRouter = None


class HTMLToDocxConverter:
    """
    Parses MDIE HTML reports and generates structured, professionally styled Word documents (.docx).
    """

    COLOR_PRIMARY = RGBColor(15, 23, 42)      # Slate-900 #0F172A
    COLOR_ACCENT = RGBColor(29, 78, 216)      # Blue-700 #1D4ED8
    COLOR_MUTED = RGBColor(71, 85, 105)       # Slate-600 #475569
    COLOR_PASS = RGBColor(4, 120, 87)         # Emerald-700 #047857
    COLOR_FAIL = RGBColor(185, 28, 28)        # Red-700 #B91C1C
    COLOR_CODE = RGBColor(51, 65, 85)         # Slate-700

    @classmethod
    def convert(
        cls,
        html_path: Union[str, Path],
        output_docx_path: Optional[Union[str, Path]] = None,
        enable_ai: bool = False,
        custom_ai_instructions: Optional[str] = None
    ) -> Path:
        """
        Converts an HTML report to a styled DOCX file.
        If enable_ai is True, invokes LLMRouter (Gemini/Groq/OpenRouter) to generate
        an AI Peer-Review & Executive Summary embedded in the document.
        """
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        if output_docx_path is None:
            output_docx_path = html_path.with_suffix(".docx")
        else:
            output_docx_path = Path(output_docx_path)

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")
        doc = docx.Document()

        # 1. Setup Document Geometry & Styles
        cls._setup_document_page(doc)
        cls._setup_styles(doc)

        # 2. Extract Document Metadata
        base_dir = html_path.parent
        doc_title = cls._extract_title(soup)

        # 3. Check for Cover Sheet (Academic Dossier)
        cover_sheet = soup.find("div", class_=re.compile(r"cover-sheet", re.I))
        if cover_sheet:
            cls._render_cover_page(doc, cover_sheet, doc_title)
            doc.add_page_break()
        else:
            cls._render_simple_header(doc, doc_title)

        # 4. Optional AI Engineering Peer-Review Section
        if enable_ai:
            cls._render_ai_review_section(doc, soup, html_path, custom_ai_instructions)

        # 5. Render Main Document Body
        main_wrapper = soup.find("div", class_="document-wrapper") or soup.find("body") or soup
        cls._render_content(doc, main_wrapper, base_dir, skip_cover=bool(cover_sheet))

        # 6. Save Document
        output_docx_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_docx_path))
        return output_docx_path

    @classmethod
    def _setup_document_page(cls, doc: docx.Document):
        """Configures 1-inch margins and standard A4/Letter size."""
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            section.page_width = Inches(8.5)
            section.page_height = Inches(11.0)

    @classmethod
    def _setup_styles(cls, doc: docx.Document):
        """Sets standard clean typography."""
        styles = doc.styles

        # Normal
        normal = styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        normal.font.color.rgb = cls.COLOR_PRIMARY
        normal.paragraph_format.line_spacing = 1.15
        normal.paragraph_format.space_after = Pt(4)

        # Heading 1
        h1 = styles["Heading 1"]
        h1.font.name = "Calibri"
        h1.font.size = Pt(16)
        h1.font.bold = True
        h1.font.color.rgb = cls.COLOR_PRIMARY
        h1.paragraph_format.space_before = Pt(14)
        h1.paragraph_format.space_after = Pt(4)
        h1.paragraph_format.keep_with_next = True

        # Heading 2
        h2 = styles["Heading 2"]
        h2.font.name = "Calibri"
        h2.font.size = Pt(13)
        h2.font.bold = True
        h2.font.color.rgb = cls.COLOR_ACCENT
        h2.paragraph_format.space_before = Pt(10)
        h2.paragraph_format.space_after = Pt(3)
        h2.paragraph_format.keep_with_next = True

        # Heading 3
        h3 = styles["Heading 3"]
        h3.font.name = "Calibri"
        h3.font.size = Pt(11)
        h3.font.bold = True
        h3.font.color.rgb = cls.COLOR_MUTED
        h3.paragraph_format.space_before = Pt(6)
        h3.paragraph_format.space_after = Pt(2)
        h3.paragraph_format.keep_with_next = True

    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> str:
        """Extracts primary document title."""
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()
        h1 = soup.find("h1")
        if h1 and h1.text.strip():
            return h1.text.strip()
        return "MDIE Engineering Calculation Dossier"

    @classmethod
    def _render_simple_header(cls, doc: docx.Document, title: str):
        """Header for standard engineering calculation sheets."""
        p = doc.add_paragraph()
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(20)
        run.font.color.rgb = cls.COLOR_PRIMARY
        p.paragraph_format.space_after = Pt(12)

    @classmethod
    def _render_cover_page(cls, doc: docx.Document, cover_elem: Tag, title: str):
        """Renders an academic or professional cover page."""
        # Top Header (University / Faculty)
        univ_elem = cover_elem.find("div", class_="cover-header")
        if univ_elem:
            p_univ = doc.add_paragraph()
            p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p_univ.add_run(univ_elem.get_text(separator="\n").strip())
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = cls.COLOR_MUTED
            p_univ.paragraph_format.space_after = Pt(16)

        # Course Information
        course_elem = cover_elem.find("div", class_="cover-course")
        if course_elem:
            p_course = doc.add_paragraph()
            p_course.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p_course.add_run(course_elem.get_text().strip())
            run.bold = True
            run.font.size = Pt(13)
            run.font.color.rgb = cls.COLOR_ACCENT
            p_course.paragraph_format.space_after = Pt(30)

        # Spacing
        for _ in range(2):
            doc.add_paragraph()

        # Document Title Group
        p_type = doc.add_paragraph()
        p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
        type_elem = cover_elem.find("div", class_="cover-report-type")
        r_type = p_type.add_run(type_elem.get_text().strip() if type_elem else "PROJECT CALCULATION REPORT")
        r_type.font.size = Pt(11)
        r_type.font.color.rgb = cls.COLOR_MUTED
        r_type.bold = True

        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_elem = cover_elem.find("div", class_="cover-title")
        r_title = p_title.add_run(title_elem.get_text().strip() if title_elem else title)
        r_title.bold = True
        r_title.font.size = Pt(22)
        r_title.font.color.rgb = cls.COLOR_PRIMARY
        p_title.paragraph_format.space_after = Pt(8)

        sub_elem = cover_elem.find("div", class_="cover-subtitle")
        if sub_elem:
            p_sub = doc.add_paragraph()
            p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_sub = p_sub.add_run(sub_elem.get_text().strip())
            r_sub.font.size = Pt(11)
            r_sub.font.color.rgb = cls.COLOR_MUTED
            p_sub.paragraph_format.space_after = Pt(40)

        for _ in range(2):
            doc.add_paragraph()

        # Metadata Table / Block
        meta_table = cover_elem.find("table", class_="cover-meta-table")
        if meta_table:
            rows = meta_table.find_all("tr")
            t = doc.add_table(rows=len(rows), cols=2)
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r_idx, row in enumerate(rows):
                cols = row.find_all(["th", "td"])
                if len(cols) >= 2:
                    t.rows[r_idx].cells[0].text = cols[0].get_text().strip()
                    t.rows[r_idx].cells[1].text = cols[1].get_text().strip()
                    # Bold labels
                    t.rows[r_idx].cells[0].paragraphs[0].runs[0].bold = True
                    cls._set_cell_padding(t.rows[r_idx].cells[0], top=40, bottom=40, left=80, right=80)
                    cls._set_cell_padding(t.rows[r_idx].cells[1], top=40, bottom=40, left=80, right=80)
            cls._set_table_borders(t, color_hex="CBD5E1")

    @classmethod
    def _render_ai_review_section(
        cls,
        doc: docx.Document,
        soup: BeautifulSoup,
        html_path: Path,
        custom_instructions: Optional[str] = None
    ):
        """
        Executes cascading LLMRouter call to generate an AI Executive Summary & Engineering Review
        and formats it as a highlighted callout box in Word.
        """
        report_text = soup.get_text(separator="\n", strip=True)[:10000]

        sys_prompt = (
            "You are a Senior Mechanical Engineering Professor and Lead Design Auditor. "
            "Analyze the following engineering calculation report and write a high-level "
            "Executive Engineering Peer-Review Dossier for a professional submission. "
            "Structure your output in clear markdown with these 3 sections:\n"
            "### 1. Executive Engineering Summary\n"
            "(Synthesize key machine parameters, applied forces, and primary structural concept)\n"
            "### 2. Critical Stress & Safety Factor (FoS) Audit\n"
            "(Identify governing components, lowest safety factors, buckling risk, and code compliance)\n"
            "### 3. Design & Manufacturing Recommendations\n"
            "(Practical feedback on tolerances, material choice, weld inspections, and weight optimization)"
        )
        if custom_instructions:
            sys_prompt += f"\nSpecial User Instructions: {custom_instructions}"

        user_prompt = f"Engineering Report for Analysis:\n\n{report_text}"

        ai_review_text = ""
        provider_used = "Offline Engineering Agent"
        try:
            if lt_complete is not None:
                ai_review_text = lt_complete(prompt=user_prompt, system=sys_prompt, temperature=0.2)
                provider_used = "Learning Tools AI"
            elif LLMRouter is not None:
                res = LLMRouter.route(sys_prompt, user_prompt, max_tokens=1500, temperature=0.2)
                ai_review_text = res.get("text", "")
                provider_used = res.get("provider", "MDIE AI")
            else:
                ai_review_text = "AI engine not configured in environment."
        except Exception as e:
            ai_review_text = f"Automated AI Review could not be fetched: {e}"

        if not ai_review_text:
            return

        # Render AI Box
        t = doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = t.rows[0].cells[0]
        cls._set_cell_shading(cell, "EFF6FF") # Light blue-50
        cls._set_cell_padding(cell, top=140, bottom=140, left=180, right=180)
        cls._set_single_left_border(cell, color_hex="1D4ED8", sz=24) # Thick blue bar

        p = cell.paragraphs[0]
        r_header = p.add_run(f"🤖 AI Engineering Executive Summary & Peer-Review ({provider_used.upper()})")
        r_header.bold = True
        r_header.font.size = Pt(12)
        r_header.font.color.rgb = cls.COLOR_ACCENT
        p.paragraph_format.space_after = Pt(8)

        # Parse markdown lines into callout box
        for line in ai_review_text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            p_line = cell.add_paragraph()
            if line_s.startswith("### "):
                r = p_line.add_run(line_s.replace("### ", ""))
                r.bold = True
                r.font.size = Pt(11)
                r.font.color.rgb = cls.COLOR_PRIMARY
                p_line.paragraph_format.space_before = Pt(6)
                p_line.paragraph_format.space_after = Pt(2)
            elif line_s.startswith("- ") or line_s.startswith("* "):
                p_line.style = "List Bullet"
                r = p_line.add_run(line_s[2:])
                r.font.size = Pt(10)
                p_line.paragraph_format.space_after = Pt(2)
            else:
                r = p_line.add_run(line_s)
                r.font.size = Pt(10)
                p_line.paragraph_format.space_after = Pt(4)

        # Spacing after callout box
        doc.add_paragraph().paragraph_format.space_after = Pt(12)

    @classmethod
    def _render_content(cls, doc: docx.Document, container: Tag, base_dir: Path, skip_cover: bool = False):
        """Recursively parses and renders HTML DOM elements into Word."""
        for child in container.children:
            if isinstance(child, NavigableString):
                continue

            if not isinstance(child, Tag):
                continue

            # Skip cover sheet if already rendered
            if skip_cover and "cover-sheet" in child.get("class", []):
                continue

            # Skip print bar / utility buttons
            if "no-print-bar" in child.get("class", []):
                continue

            tag = child.name.lower()

            if tag in ["h1", "h2", "h3", "h4"]:
                cls._render_heading(doc, child)

            elif tag == "p":
                cls._render_paragraph(doc, child)

            elif tag in ["ul", "ol"]:
                cls._render_list(doc, child, is_ordered=(tag == "ol"))

            elif tag == "table":
                cls._render_table(doc, child)

            elif tag == "img":
                cls._render_image(doc, child, base_dir)

            elif tag in ["div", "section", "article"]:
                # Check for special container types
                classes = child.get("class", [])
                if any(c in classes for c in ["callout-box", "audit-panel", "alert", "fbd-frame"]):
                    cls._render_callout_box(doc, child, base_dir)
                else:
                    cls._render_content(doc, child, base_dir, skip_cover=skip_cover)

            elif tag == "hr":
                p = doc.add_paragraph()
                cls._set_paragraph_bottom_border(p, color_hex="CBD5E1")

    @classmethod
    def _render_heading(cls, doc: docx.Document, tag: Tag):
        """Formats headings with hierarchy and bold styling."""
        text = tag.get_text().strip()
        if not text:
            return
        level_map = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
        lvl = level_map.get(tag.name.lower(), 2)
        h = doc.add_heading(text, level=lvl)
        h.paragraph_format.keep_with_next = True

    @classmethod
    def _render_paragraph(cls, doc: docx.Document, tag: Tag):
        """Renders paragraph preserving inline bold, italic, and code."""
        text = tag.get_text().strip()
        if not text:
            return
        p = doc.add_paragraph()
        cls._append_inline_formatted_text(p, tag)

    @classmethod
    def _render_list(cls, doc: docx.Document, tag: Tag, is_ordered: bool = False):
        """Renders unordered or ordered lists."""
        for li in tag.find_all("li", recursive=False):
            style = "List Number" if is_ordered else "List Bullet"
            p = doc.add_paragraph(style=style)
            cls._append_inline_formatted_text(p, li)
            p.paragraph_format.space_after = Pt(2)

    @classmethod
    def _render_table(cls, doc: docx.Document, tag: Tag):
        """Renders data tables with styled headers, alternating rows, and pass/fail highlights."""
        rows = tag.find_all("tr")
        if not rows:
            return

        # Determine column count
        col_count = max(len(r.find_all(["th", "td"])) for r in rows)
        if col_count == 0:
            return

        t = doc.add_table(rows=len(rows), cols=col_count)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cls._set_table_borders(t, color_hex="CBD5E1")

        for r_idx, r in enumerate(rows):
            cells = r.find_all(["th", "td"])
            is_header = bool(r.find("th")) or (r_idx == 0)

            for c_idx in range(col_count):
                cell = t.rows[r_idx].cells[c_idx]
                if c_idx < len(cells):
                    html_cell = cells[c_idx]
                    cell_text = html_cell.get_text().strip()
                    cell.text = cell_text
                    p = cell.paragraphs[0]

                    # Styling
                    if is_header:
                        cls._set_cell_shading(cell, "0F172A") # Dark Navy Slate
                        for run in p.runs:
                            run.font.color.rgb = RGBColor(255, 255, 255)
                            run.font.bold = True
                            run.font.size = Pt(9.5)
                    else:
                        for run in p.runs:
                            run.font.size = Pt(9.5)
                        # Alternating row shading
                        if r_idx % 2 == 1:
                            cls._set_cell_shading(cell, "F8FAFC")

                        # Pass/Fail highlight
                        upper_text = cell_text.upper()
                        if "PASS" in upper_text:
                            for run in p.runs:
                                run.font.bold = True
                                run.font.color.rgb = cls.COLOR_PASS
                        elif "FAIL" in upper_text:
                            for run in p.runs:
                                run.font.bold = True
                                run.font.color.rgb = cls.COLOR_FAIL

                    cls._set_cell_padding(cell, top=60, bottom=60, left=80, right=80)

        # Spacing after table
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    @classmethod
    def _render_image(cls, doc: docx.Document, tag: Tag, base_dir: Path):
        """Resolves local image references and embeds into Word document."""
        src = tag.get("src", "")
        if not src:
            return

        img_path = base_dir / src
        if not img_path.exists():
            # Try plain filename in base_dir
            img_path = base_dir / Path(src).name

        if img_path.exists() and img_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp"]:
            try:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(img_path), width=Inches(5.5))
                caption = tag.get("alt", "")
                if caption:
                    p_cap = doc.add_paragraph()
                    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = p_cap.add_run(caption)
                    r.font.italic = True
                    r.font.size = Pt(9)
                    r.font.color.rgb = cls.COLOR_MUTED
            except Exception:
                pass

    @classmethod
    def _render_callout_box(cls, doc: docx.Document, tag: Tag, base_dir: Path):
        """Renders shaded highlight panel with left vertical accent bar."""
        t = doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = t.rows[0].cells[0]
        cls._set_cell_shading(cell, "F8FAFC")
        cls._set_cell_padding(cell, top=100, bottom=100, left=140, right=140)
        cls._set_single_left_border(cell, color_hex="0F172A", sz=18)

        # Recursively render children inside callout cell
        cell_p = cell.paragraphs[0]
        first = True
        for elem in tag.find_all(["p", "div", "h3", "h4", "img"], recursive=False):
            if elem.name.lower() == "img":
                cls._render_image(doc, elem, base_dir)
            else:
                text = elem.get_text().strip()
                if not text:
                    continue
                p = cell_p if first else cell.add_paragraph()
                first = False
                cls._append_inline_formatted_text(p, elem)
                p.paragraph_format.space_after = Pt(3)

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    @classmethod
    def _append_inline_formatted_text(cls, paragraph: Any, tag: Tag):
        """Iterates child nodes preserving <b>, <strong>, <i>, <em>, <code>."""
        for item in tag.children:
            if isinstance(item, NavigableString):
                text = str(item)
                if text:
                    paragraph.add_run(text)
            elif isinstance(item, Tag):
                sub_text = item.get_text()
                run = paragraph.add_run(sub_text)
                sub_name = item.name.lower()
                if sub_name in ["b", "strong"]:
                    run.bold = True
                if sub_name in ["i", "em"]:
                    run.italic = True
                if sub_name in ["code", "kbd"]:
                    run.font.name = "Consolas"
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = cls.COLOR_CODE

    # --- Low-Level OpenXML Helpers for Cell Shading, Borders & Padding ---

    @staticmethod
    def _set_cell_shading(cell: Any, color_hex: str):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
        tcPr.append(shd)

    @staticmethod
    def _set_cell_padding(cell: Any, top: int = 80, bottom: int = 80, left: int = 100, right: int = 100):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>'
            f'<w:top w:w="{top}" w:type="dxa"/>'
            f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
            f'<w:left w:w="{left}" w:type="dxa"/>'
            f'<w:right w:w="{right}" w:type="dxa"/>'
            f'</w:tcMar>'
        )
        tcPr.append(tcMar)

    @staticmethod
    def _set_table_borders(table: Any, color_hex: str = "CBD5E1"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="6" w:space="0" w:color="{color_hex}"/>'
            f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="{color_hex}"/>'
            f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>'
            f'<w:insideV w:val="none"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    @staticmethod
    def _set_single_left_border(cell: Any, color_hex: str = "1D4ED8", sz: int = 24):
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="none"/>'
            f'<w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color_hex}"/>'
            f'<w:bottom w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

    @staticmethod
    def _set_paragraph_bottom_border(paragraph: Any, color_hex: str = "CBD5E1"):
        pPr = paragraph._p.get_or_add_pPr()
        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'<w:bottom w:val="single" w:sz="6" w:space="1" w:color="{color_hex}"/>'
            f'</w:pBdr>'
        )
        pPr.append(pBdr)
