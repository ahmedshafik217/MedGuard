"""Resolves a short, possibly-imperfect spoken phrase -- captured by the
browser's own built-in speech recognition on the "Add antibiotic" form's
microphone button -- to one of this hospital's known antibiotic names.

Deliberately NOT an AI call: this uses plain fuzzy string matching
(Python's own difflib, standard library) against the antibiotics reference
table, so speaking a drug name costs nothing and needs no API key, unlike
the prescription-photo-scan feature (app/prescription_scan.py), which
genuinely needs a vision model to read handwriting. If nothing matches
closely enough -- an unfamiliar drug, a very garbled transcript -- the raw
heard text is returned unchanged, exactly as if it had been typed by hand:
never worse than typing, just not auto-corrected.
"""
import difflib

# difflib similarity ratio (0-1). Loose enough to catch a minor mis-hearing
# or a brand name typed/spoken slightly differently, tight enough that a
# genuinely different drug name won't get silently swapped in -- a
# patient-safety record should never auto-correct into the WRONG drug.
MATCH_CUTOFF = 0.6


def resolve_spoken_antibiotic_name(heard, known_antibiotics):
    """heard: raw transcript text from the browser's speech recognition.
    known_antibiotics: models.list_antibiotics() -- each item has
    generic_name and brand_names (comma-separated, may be None/empty).
    Returns {"heard": str, "resolved_name": str, "matched": bool}."""
    heard = (heard or "").strip()
    if not heard:
        return {"heard": heard, "resolved_name": "", "matched": False}

    candidates = {}  # lowercased candidate name -> real-cased generic name
    for a in known_antibiotics:
        generic = a.get("generic_name")
        if generic:
            candidates[generic.lower()] = generic
        for brand in (a.get("brand_names") or "").split(","):
            brand = brand.strip()
            if brand:
                candidates.setdefault(brand.lower(), generic)

    if not candidates:
        return {"heard": heard, "resolved_name": heard, "matched": False}

    best = difflib.get_close_matches(heard.lower(), candidates.keys(), n=1, cutoff=MATCH_CUTOFF)
    if best:
        return {"heard": heard, "resolved_name": candidates[best[0]], "matched": True}
    return {"heard": heard, "resolved_name": heard, "matched": False}