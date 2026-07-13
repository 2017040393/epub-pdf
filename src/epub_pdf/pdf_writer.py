from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .models import Book


def write_pdf(book: Book, output: Path, font_path: Path | None, font_size: float = 10.5) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    font_name = "Helvetica"
    if font_path:
        if not font_path.is_file():
            raise FileNotFoundError(f"Font file not found: {font_path}")
        font_name = "BookFont"
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

    document = SimpleDocTemplate(
        str(output), pagesize=A4,
        rightMargin=2.1 * cm, leftMargin=2.1 * cm,
        topMargin=2.0 * cm, bottomMargin=1.9 * cm,
        title=book.title, author=book.author or "",
    )
    styles = _styles(font_name, font_size)
    story = [Paragraph(escape(book.title), styles["book_title"])]
    if book.author:
        story += [Spacer(1, 0.25 * cm), Paragraph(escape(book.author), styles["author"])]
    story += [PageBreak()]
    for chapter_index, chapter in enumerate(book.chapters):
        if chapter_index:
            story.append(PageBreak())
        story.append(Paragraph(escape(chapter.title), styles["chapter"]))
        story.append(Spacer(1, 0.25 * cm))
        for block in chapter.blocks:
            style_name = {
                "heading": "heading",
                "list": "list",
                "quote": "quote",
                "code": "code",
            }.get(block.kind, "body")
            prefix = "- " if block.kind == "list" else ""
            story.append(Paragraph(escape(prefix + block.text).replace("\n", "<br/>"), styles[style_name]))
            story.append(Spacer(1, 0.10 * cm if block.kind == "heading" else 0.16 * cm))
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)


def _styles(font_name: str, font_size: float) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    leading = font_size * 1.7
    return {
        "book_title": ParagraphStyle("BookTitle", parent=base["Title"], fontName=font_name, fontSize=22, leading=30, alignment=TA_CENTER),
        "author": ParagraphStyle("Author", parent=base["Normal"], fontName=font_name, fontSize=12, leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "chapter": ParagraphStyle("Chapter", parent=base["Heading1"], fontName=font_name, fontSize=17, leading=24, spaceAfter=8),
        "heading": ParagraphStyle("Heading", parent=base["Heading2"], fontName=font_name, fontSize=font_size + 2.5, leading=font_size * 1.5, spaceBefore=8),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName=font_name, fontSize=font_size, leading=leading, alignment=TA_JUSTIFY, firstLineIndent=font_size * 2),
        "list": ParagraphStyle("List", parent=base["BodyText"], fontName=font_name, fontSize=font_size, leading=leading, leftIndent=font_size * 1.5),
        "quote": ParagraphStyle("Quote", parent=base["BodyText"], fontName=font_name, fontSize=font_size, leading=leading, leftIndent=font_size * 1.8, rightIndent=font_size, textColor=colors.HexColor("#444444")),
        "code": ParagraphStyle("Code", parent=base["Code"], fontName=font_name, fontSize=max(font_size - 1, 8), leading=font_size * 1.35, leftIndent=font_size),
    }


def _page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawCentredString(A4[0] / 2, 1.05 * cm, str(document.page))
    canvas.restoreState()
