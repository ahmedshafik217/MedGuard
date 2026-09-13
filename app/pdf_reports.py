"""Hospital-wide (not per-patient) PDF reports:

- generate_quality_report_pdf(): for the Quality Control Manager -- every
  antibiotic entry across every patient whose safety check produced a
  danger or warning alert (repeated/recent exposure, allergy conflicts,
  pregnancy contraindications, condition contraindications, drug-drug
  interactions), grouped by alert type with counts.
- generate_pharmacy_report_pdf(): for the Pharmacy Manager -- how many
  times each antibiotic was prescribed within one calendar month,
  hospital-wide.

Reuses the same reportlab styling helpers as app/pdf_export.py (colors,
fonts, table look) so every PDF this app produces reads as one consistent
document, rather than two different visual styles."""
import io
from collections import Counter
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.pdf_export import ALERT_COLORS, ALERT_COLORS_BY_CODE, ALERT_LABELS, LOGO_PATH, _escape, _styles, _table

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Human-readable label for each alert "code" the safety-check engine
# produces (see app/engine/safety_check.py) -- used to group/count the
# Quality Control report's findings by issue TYPE, not just list them flat.
ALERT_CODE_LABELS = {
    "allergy_direct": "Allergy conflict (direct match)",
    "allergy_cross_reactivity": "Allergy conflict (cross-reactivity)",
    "pregnancy_contraindicated": "Pregnancy contraindication",
    "recent_exposure": "Repeated / recent exposure (same antibiotic)",
    "recent_exposure_class": "Repeated / recent exposure (same drug class)",
    "condition_contraindicated": "Medical condition contraindication",
    "drug_drug_interaction": "Drug-drug interaction",
}


def _logo_or_title(story, styles):
    if LOGO_PATH.exists():
        from reportlab.lib.utils import ImageReader

        from reportlab.platypus import Image
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


def _footer_maker(label, generated_at):
    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("DejaVuSans", 7.5)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(16 * mm, 10 * mm, f"Al Shefa Specialized Hospital — {label} — generated {generated_at}")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    return _footer


def generate_quality_report_pdf(flagged_records):
    """flagged_records: list of antibiotic_records dicts (as returned by
    models.list_flagged_records_all()) whose 'alerts' list already contains
    at least one danger/warning alert."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
        title="Quality Control — Antibiotic Safety Analysis",
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    story = []
    _logo_or_title(story, styles)
    story.append(Paragraph("Quality Control — Antibiotic Safety Analysis", styles["subtitle"]))
    story.append(Paragraph(f"Generated {generated_at} — hospital-wide, all patients", styles["small"]))
    story.append(Spacer(1, 10))

    # Count each flagged ALERT (not each record -- one record can carry
    # more than one alert) by its code, so "repeated antibiotics" and
    # "allergies" etc. are each their own line, per Ahmed's spec.
    code_counter = Counter()
    flat_rows = []  # (record, alert) pairs, most recent record first
    for record in flagged_records:
        for alert in record.get("alerts", []):
            if alert.get("level") not in ("danger", "warning"):
                continue
            code_counter[alert.get("code", "other")] += 1
            flat_rows.append((record, alert))

    story.append(Paragraph("Summary by issue type", styles["h2"]))
    if code_counter:
        rows = [["Issue type", "Occurrences"]]
        for code, count in code_counter.most_common():
            rows.append([ALERT_CODE_LABELS.get(code, code.replace("_", " ").title()), str(count)])
        story.append(_table(rows, [140 * mm, 35 * mm], styles))
    else:
        story.append(Paragraph("No flagged safety issues found in the antibiotic history.", styles["body"]))

    story.append(Paragraph("Flagged entries (most recent first)", styles["h2"]))
    if flat_rows:
        rows = [["Date", "Patient ID", "Antibiotic", "Issue", "Details"]]
        for record, alert in flat_rows:
            color = ALERT_COLORS_BY_CODE.get(alert.get("code")) or ALERT_COLORS.get(alert.get("level"), colors.black)
            label = ALERT_LABELS.get(alert.get("level"), (alert.get("level") or "").upper())
            issue_html = (
                f'<font color="{color.hexval()}"><b>[{label}]</b></font><br/>'
                f'{_escape(ALERT_CODE_LABELS.get(alert.get("code"), alert.get("code", "")))}'
            )
            rows.append([
                Paragraph(_escape(record.get("prescribed_date")), styles["cell"]),
                Paragraph(_escape(record.get("patient_public_id")), styles["cell_bold"]),
                Paragraph(_escape(record.get("display_name")), styles["cell"]),
                Paragraph(issue_html, styles["cell"]),
                Paragraph(_escape(alert.get("message", "")), styles["cell"]),
            ])
        story.append(_table(rows, [20 * mm, 24 * mm, 26 * mm, 40 * mm, 65 * mm], styles))
    else:
        story.append(Paragraph("Nothing to list.", styles["body"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "This report lists every antibiotic entry hospital-wide whose automatic safety check raised a "
        "danger or warning alert. It is a clinical decision-SUPPORT summary for quality/infection-control "
        "review and does not replace independent clinical judgment.",
        styles["disclaimer"],
    ))

    doc.build(story, onFirstPage=_footer_maker("Quality Control Report", generated_at),
               onLaterPages=_footer_maker("Quality Control Report", generated_at))
    return buf.getvalue()


def generate_pharmacy_report_pdf(year, month, counts):
    """counts: list of (antibiotic_name, count) tuples, most-prescribed
    first (see models.monthly_antibiotic_counts)."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Pharmacy Monthly Antibiotic Usage — {year}-{month:02d}",
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    month_label = f"{MONTH_NAMES[month]} {year}"

    story = []
    _logo_or_title(story, styles)
    story.append(Paragraph("Pharmacy — Monthly Antibiotic Usage Report", styles["subtitle"]))
    story.append(Paragraph(f"{month_label} — hospital-wide, all patients — generated {generated_at}", styles["small"]))
    story.append(Spacer(1, 10))

    total = sum(c for _, c in counts)
    story.append(Paragraph(f"Total antibiotics prescribed this month: {total}", styles["h2"]))
    if counts:
        rows = [["Antibiotic", "Times prescribed"]]
        for name, count in counts:
            rows.append([Paragraph(_escape(name), styles["cell"]), str(count)])
        story.append(_table(rows, [140 * mm, 35 * mm], styles))
    else:
        story.append(Paragraph("No antibiotics were recorded as prescribed this month.", styles["body"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Counts are based on each antibiotic entry's prescribed date, hospital-wide across all patients. "
        "An antibiotic typed as free text (not found in the reference database) is counted under whatever "
        "name was entered.",
        styles["disclaimer"],
    ))

    doc.build(story, onFirstPage=_footer_maker(f"Pharmacy Report {year}-{month:02d}", generated_at),
               onLaterPages=_footer_maker(f"Pharmacy Report {year}-{month:02d}", generated_at))
    return buf.getvalue()
