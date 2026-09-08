"""Generates a printable PDF summary of one patient's antibiotic safety
record -- meant to be handed to (or emailed to) a doctor or pharmacist at a
visit, since not every clinic will have the app open.

Uses reportlab (add it to requirements.txt -- `pip install reportlab`).
The PDF's own labels are always in English regardless of the site's current
language, because reportlab cannot correctly shape/reorder Arabic script
without extra libraries (arabic-reshaper, python-bidi) that this project
deliberately avoids depending on. Any Arabic text a patient/owner typed into
a free-text field (an allergen name, a note, ...) is included as-is using a
bundled Unicode font (DejaVu Sans), but may not display with correct
letter-joining or right-to-left order -- see the README for the reasoning
and options if fully-shaped Arabic PDFs become a priority later.
"""
import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "hospital_logo.png"

_FONTS_REGISTERED = False


def _ensure_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONTS_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(FONTS_DIR / "DejaVuSans-Bold.ttf")))
    _FONTS_REGISTERED = True


# Palette sampled directly from the hospital logo, so the rest of the page
# reads as one consistent brand rather than a generic template with a logo
# pasted on top.
BRAND_TEAL = colors.HexColor("#1bbad8")        # the logo's bright cyan (banners/backgrounds)
BRAND_TEAL_DARK = colors.HexColor("#0f6677")   # a readable-on-white shade of that same teal (headings/text)
BRAND_NAVY = colors.HexColor("#092440")        # the logo wordmark's navy (title text)
BRAND_RED = colors.HexColor("#bd2031")         # the logo heart's red (danger alerts only)

ALERT_COLORS = {
    "danger": BRAND_RED,
    "warning": colors.HexColor("#92400e"),  # kept amber -- "warning" should still read as amber, not brand teal
    "info": BRAND_TEAL_DARK,
}
ALERT_LABELS = {"danger": "DANGER", "warning": "WARNING", "info": "INFO"}


def _styles():
    _ensure_fonts()
    ss = getSampleStyleSheet()
    base = ParagraphStyle("Base", parent=ss["Normal"], fontName="DejaVuSans", fontSize=9, leading=12)
    return {
        "title": ParagraphStyle("Title", parent=base, fontName="DejaVuSans-Bold", fontSize=16,
                                 textColor=BRAND_NAVY, spaceAfter=2, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("Subtitle", parent=base, fontSize=11, textColor=BRAND_TEAL_DARK,
                                    fontName="DejaVuSans-Bold", spaceAfter=10, alignment=TA_CENTER),
        "h2": ParagraphStyle("H2", parent=base, fontName="DejaVuSans-Bold", fontSize=12,
                              textColor=BRAND_TEAL_DARK, spaceBefore=14, spaceAfter=6),
        "body": base,
        "small": ParagraphStyle("Small", parent=base, fontSize=8, textColor=colors.HexColor("#555555")),
        "cell": ParagraphStyle("Cell", parent=base, fontSize=8.5, leading=11),
        "cell_bold": ParagraphStyle("CellBold", parent=base, fontName="DejaVuSans-Bold", fontSize=8.5, leading=11),
        "disclaimer": ParagraphStyle("Disclaimer", parent=base, fontSize=8, leading=11,
                                      textColor=colors.HexColor("#7a5b00"),
                                      backColor=colors.HexColor("#fff8e6"),
                                      borderPadding=6),
    }


def _alert_paragraph(alert, styles):
    color = ALERT_COLORS.get(alert.get("level"), colors.black)
    label = ALERT_LABELS.get(alert.get("level"), alert.get("level", "").upper())
    text = (
        f'<font color="{color.hexval()}"><b>[{label}]</b></font> '
        f'<b>{_escape(alert.get("title", ""))}</b><br/>{_escape(alert.get("message", ""))}'
    )
    return Paragraph(text, styles["cell"])


def _escape(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _table(data, col_widths, styles, header_bg=BRAND_TEAL):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4faf9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


GENDER_LABELS = {"male": "Male", "female": "Female", "unspecified": "Unspecified"}
PREGNANCY_LABELS = {
    "pregnant": "Currently pregnant",
    "not_pregnant": "Not pregnant",
    "not_applicable": "Not applicable",
    "unknown": "Unknown / not recorded",
}


def generate_patient_history_pdf(patient, allergies, conditions, records):
    """Returns PDF bytes for the given patient's full safety record."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Antibiotic Safety Summary — {patient['public_id']}",
    )

    story = []
    if LOGO_PATH.exists():
        from reportlab.lib.utils import ImageReader
        logo_reader = ImageReader(str(LOGO_PATH))
        logo_w_px, logo_h_px = logo_reader.getSize()
        target_w = 90 * mm
        target_h = target_w * (logo_h_px / logo_w_px)
        logo_img = Image(str(LOGO_PATH), width=target_w, height=target_h)
        logo_img.hAlign = "CENTER"
        story.append(logo_img)
        story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("Al Shefa Specialized Hospital", styles["title"]))
    story.append(Paragraph("Patient Antibiotic Safety AI Analysis", styles["subtitle"]))

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    info_rows = [
        ["Patient ID", patient["public_id"]],
        ["Name", patient.get("full_name") or "—"],
        ["Gender", GENDER_LABELS.get(patient.get("gender"), patient.get("gender", "—"))],
        ["Date of birth", (patient.get("date_of_birth") or "—") +
         (f" ({patient['age_years']} years old)" if patient.get("age_years") is not None else "")],
        ["Pregnancy status", PREGNANCY_LABELS.get(patient.get("pregnancy_status"), "—")],
        ["Generated", generated_at],
    ]
    info_table = Table(
        [[Paragraph(f"<b>{_escape(k)}</b>", styles["cell"]), Paragraph(_escape(v), styles["cell"])]
         for k, v in info_rows],
        colWidths=[45 * mm, 120 * mm],
    )
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)

    story.append(Paragraph("Known Allergies", styles["h2"]))
    if allergies:
        rows = [["Allergen", "Drug class", "Severity", "Reaction", "Recorded"]]
        for a in allergies:
            rows.append([
                Paragraph(_escape(a.get("allergen")), styles["cell"]),
                Paragraph(_escape(a.get("drug_class") or "—"), styles["cell"]),
                Paragraph(_escape((a.get("severity") or "—").capitalize()), styles["cell"]),
                Paragraph(_escape(a.get("reaction") or "—"), styles["cell"]),
                Paragraph(_escape((a.get("recorded_at") or "")[:10]), styles["cell"]),
            ])
        story.append(_table(rows, [38 * mm, 32 * mm, 22 * mm, 48 * mm, 25 * mm], styles))
    else:
        story.append(Paragraph("No allergies recorded.", styles["body"]))

    story.append(Paragraph("Medical Conditions", styles["h2"]))
    if conditions:
        rows = [["Condition", "Notes", "Recorded"]]
        for c in conditions:
            rows.append([
                Paragraph(_escape(c.get("condition_name")), styles["cell"]),
                Paragraph(_escape(c.get("notes") or "—"), styles["cell"]),
                Paragraph(_escape((c.get("recorded_at") or "")[:10]), styles["cell"]),
            ])
        story.append(_table(rows, [55 * mm, 80 * mm, 30 * mm], styles))
    else:
        story.append(Paragraph("No medical conditions recorded.", styles["body"]))

    story.append(Paragraph("Antibiotic History", styles["h2"]))
    if records:
        rows = [["Date", "Antibiotic", "Dose", "Duration", "By", "Alerts at the time"]]
        for r in records:
            alerts = r.get("alerts") or []
            if alerts and alerts[0].get("code") not in ("no_issues_found",):
                alert_flow = [_alert_paragraph(a, styles) for a in alerts]
            elif alerts:
                alert_flow = [Paragraph("No known issues found.", styles["cell"])]
            else:
                alert_flow = [Paragraph("—", styles["cell"])]
            rows.append([
                Paragraph(_escape(r.get("prescribed_date")), styles["cell"]),
                Paragraph(_escape(r.get("display_name")), styles["cell_bold"]),
                Paragraph(_escape(r.get("dose") or "—"), styles["cell"]),
                Paragraph(_escape(r.get("duration") or "—"), styles["cell"]),
                Paragraph(_escape(r.get("prescribed_by") or r.get("added_by") or "—"), styles["cell"]),
                alert_flow,
            ])
        story.append(_table(rows, [24 * mm, 26 * mm, 16 * mm, 18 * mm, 20 * mm, 66 * mm], styles))
    else:
        story.append(Paragraph("No antibiotics recorded yet.", styles["body"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "This document reflects patient-reported data recorded in Al Shefa's antibiotic safety "
        "app as of the generation date above. It is a clinical decision-SUPPORT summary and does "
        "not replace the independent judgment of a licensed physician or pharmacist. Please verify "
        "all entries with the patient directly.",
        styles["disclaimer"],
    ))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("DejaVuSans", 7.5)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(16 * mm, 10 * mm,
                           f"Al Shefa Specialized Hospital — Patient {patient['public_id']} — generated {generated_at}")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
