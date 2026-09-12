"""Turns a record's structured dose/duration codes into a human-readable
phrase in a REQUESTED language, using the same STRINGS dictionary as the
rest of the UI (app/translations.py).

Why this exists: dose and duration used to be plain free-text fields, so a
dose typed while the app was in Arabic (e.g. "1 جم كل 8 ساعات") stayed
exactly that Arabic text forever -- including when the SAME record later
appeared on an English PDF. There is no safe way to auto-translate that
after the fact: running a patient's free-text dose through a machine
translator risks silently mistranslating a number or unit on a patient-
safety record, which is a real risk for the exact thing this app exists to
prevent.

The fix is to stop storing free text for the amount/unit/frequency and
store a small, closed set of CODES instead (dose_unit, frequency,
duration_unit) -- see app/db.py's antibiotic_records columns. Translating a
closed vocabulary we fully control is just a dictionary lookup, so it's
safe in a way that translating open-ended text is not. format_dose() and
format_duration() below do that lookup for whatever language is requested,
independent of the language the record was originally entered in.

Old records created before this existed have no structured fields --
format_dose()/format_duration() fall back to the legacy dose/duration free
text for those (unchanged behavior, no data loss), which is the one case
that still won't translate -- there is no data to translate it from.
"""
from app.translations import t

# Keep these lists and the DOSE_UNIT_*/FREQUENCY_*/DURATION_UNIT_* keys in
# translations.py in sync -- each entry here is rendered as a <option> in
# the add-antibiotic forms and must have a matching "dose_unit_<code>" /
# "freq_<code>" / "duration_unit_<code>" translation key.
DOSE_UNITS = ["mg", "g", "ml", "iu", "tablet", "capsule"]
FREQUENCIES = [
    "once_daily", "twice_daily", "three_times_daily", "four_times_daily",
    "every_6h", "every_8h", "every_12h", "every_24h", "as_needed", "single_dose",
]
DURATION_UNITS = ["day", "week", "dose"]


def format_dose(record, lang):
    """record: a dict with dose_amount/dose_unit/dose_unit_other/frequency/
    frequency_other (structured, new records) and/or dose (legacy free
    text, old records). Returns a display string, or None if nothing was
    entered at all."""
    amount = (record.get("dose_amount") or "").strip()
    unit = record.get("dose_unit")
    freq = record.get("frequency")

    if not amount and not unit and not freq:
        # No structured data on this record -- either nothing was entered,
        # or it's a record from before structured dose/duration existed.
        # Fall back to whatever free text (if any) was originally stored.
        return record.get("dose") or None

    parts = []
    if amount:
        parts.append(amount)
    if unit == "other":
        if record.get("dose_unit_other"):
            parts.append(record["dose_unit_other"])
    elif unit:
        parts.append(t(f"dose_unit_{unit}", lang))
    phrase = " ".join(p for p in parts if p)

    freq_text = None
    if freq == "other":
        freq_text = record.get("frequency_other") or None
    elif freq:
        freq_text = t(f"freq_{freq}", lang)

    if freq_text:
        phrase = f"{phrase} — {freq_text}" if phrase else freq_text

    return phrase or None


def format_duration(record, lang):
    """Same idea as format_dose() but for duration_amount/duration_unit/
    duration_unit_other (structured) with a fallback to the legacy
    duration free text for old records."""
    amount = (record.get("duration_amount") or "").strip()
    unit = record.get("duration_unit")

    if not amount and not unit:
        return record.get("duration") or None

    unit_text = None
    if unit == "other":
        unit_text = record.get("duration_unit_other") or None
    elif unit:
        unit_text = t(f"duration_unit_{unit}", lang)

    if amount and unit_text:
        return f"{amount} {unit_text}"
    return amount or unit_text or None
