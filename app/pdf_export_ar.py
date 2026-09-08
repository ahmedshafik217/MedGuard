"""Generates the Arabic-language printable PDF summary of a patient's
antibiotic safety record.

This is a deliberately separate pipeline from pdf_export.py (the English,
reportlab-based one): reportlab cannot correctly shape (join letters) or
right-to-left-reorder Arabic script without extra libraries
(arabic-reshaper, python-bidi) that could not be installed in this
environment (no package-index network access). Instead, this pipeline
renders an HTML template and converts it with wkhtmltopdf (via the
`pdfkit` wrapper) -- wkhtmltopdf embeds a WebKit engine, and WebKit's own
text-shaping handles Arabic correctly with zero extra Python dependencies.

Visual design (brand colors, section order, table layout) is kept in
lockstep with pdf_export.py by hand so the English and Arabic PDFs read as
the same document in two languages, per the hospital's request.

Requires the `wkhtmltopdf` **system binary** to be installed separately --
it is a compiled program, not a pip package. See README.md for install
instructions on other machines; this environment already has it at
/usr/bin/wkhtmltopdf.
"""
import base64
import shutil
from datetime import datetime
from pathlib import Path

import pdfkit
from flask import render_template

LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "hospital_logo.png"

GENDER_LABELS_AR = {"male": "ذكر", "female": "أنثى", "unspecified": "غير محدد"}
PREGNANCY_LABELS_AR = {
    "pregnant": "حامل حالياً",
    "not_pregnant": "غير حامل",
    "not_applicable": "لا ينطبق",
    "unknown": "غير معروف / غير مسجل",
}
SEVERITY_LABELS_AR = {
    "mild": "بسيطة",
    "moderate": "متوسطة",
    "severe": "شديدة",
    "unknown": "غير معروفة",
}
ALERT_LABELS_AR = {"danger": "خطر", "warning": "تنبيه", "info": "معلومة"}


class WkhtmltopdfNotFound(RuntimeError):
    """Raised when the wkhtmltopdf system binary isn't installed."""


def _wkhtmltopdf_path():
    # Prefer the well-known location this project was built/tested against,
    # but fall back to whatever is on PATH so this also works on a
    # deployment machine where it was installed differently.
    if Path("/usr/bin/wkhtmltopdf").exists():
        return "/usr/bin/wkhtmltopdf"
    found = shutil.which("wkhtmltopdf")
    if found:
        return found
    raise WkhtmltopdfNotFound(
        "The wkhtmltopdf program is not installed on this machine. It is a "
        "separate system package (not a pip package) -- see the README's "
        "'Arabic PDF export' section for install instructions."
    )


def _logo_data_uri():
    if not LOGO_PATH.exists():
        return None
    data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def generate_patient_history_pdf_arabic(patient, allergies, conditions, records):
    """Returns PDF bytes (Arabic) for the given patient's full safety record."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = render_template(
        "pdf/arabic_summary.html",
        patient=patient,
        allergies=allergies,
        conditions=conditions,
        records=records,
        generated_at=generated_at,
        logo_data_uri=_logo_data_uri(),
        gender_label=GENDER_LABELS_AR.get(patient.get("gender"), patient.get("gender") or "—"),
        pregnancy_label=PREGNANCY_LABELS_AR.get(patient.get("pregnancy_status"), "—"),
        severity_labels=SEVERITY_LABELS_AR,
        alert_labels=ALERT_LABELS_AR,
    )

    config = pdfkit.configuration(wkhtmltopdf=_wkhtmltopdf_path())
    footer_text = f"مستشفى الشفاء التخصصي — المريض {patient['public_id']} — أُنشئ في {generated_at}"
    options = {
        "page-size": "A4",
        "margin-top": "16mm",
        "margin-bottom": "18mm",
        "margin-left": "16mm",
        "margin-right": "16mm",
        "encoding": "UTF-8",
        "quiet": True,
        "enable-local-file-access": True,
        "footer-font-size": "7",
        "footer-right": footer_text,
        "footer-left": "صفحة [page] من [topage]",
        "footer-spacing": "6",
        "title": f"Antibiotic Safety Summary — {patient['public_id']} (Arabic)",
    }
    pdf_bytes = pdfkit.from_string(html, False, options=options, configuration=config)
    return pdf_bytes
