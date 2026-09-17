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

Matching runs in three passes, each one tried only if the previous one
found nothing:

  1. Fragment rules -- clinicians very often say (and the browser's speech
     recognizer very often mangles) a scientific/generic name down to a
     short fragment: "triaxone" for ceftriaxone, "vanco" for vancomycin,
     and so on. This runs first and specifically, because a short fragment
     like that can otherwise score a deceptively high similarity against
     an unrelated *short brand name* in the next pass (e.g. "moxi" against
     the brand "Amoxil") purely for being a similar length -- which would
     silently produce the wrong drug. Checking these specific, hand-picked
     fragments first avoids that trap entirely.
  2. Whole-phrase fuzzy match -- handles brand names (Augmentin, Cipro,
     Zithromax...) and a full generic name spoken clearly, typos and all.
  3. Word-by-word fuzzy fallback -- catches everything else, like a filler
     word the recognizer tacked on ("give me augmentin please") or a minor
     mis-hearing of a short brand name.
"""
import difflib
import re

# difflib similarity ratio (0-1). Loose enough to catch a minor mis-hearing
# or a brand name typed/spoken slightly differently, tight enough that a
# genuinely different drug name won't get silently swapped in -- a
# patient-safety record should never auto-correct into the WRONG drug.
MATCH_CUTOFF = 0.6

# Per-word fallback cutoff (pass 3, see below). Kept much stricter than
# MATCH_CUTOFF: many antibiotic names share a drug-class suffix (the
# "-cillin" in ampicillin/amoxicillin/piperacillin, the "-mycin" in
# vancomycin/azithromycin/clindamycin...), so two *different* real drugs
# can score a deceptively high ratio against each other from the shared
# ending alone -- e.g. "piperacillin" vs "ampicillin" scores 0.73, and
# "bactam" (the tail of tazobactam) vs the brand "Bactrim" scores 0.77.
# 0.85 comfortably clears a genuine minor mis-hearing/typo of one word
# (a single swapped/dropped letter in an 8+ letter word) while staying
# above both of those real cross-drug collisions.
WORD_MATCH_CUTOFF = 0.85

_PUNCT_RE = re.compile(r"[^\w\s\-]")
_SPACE_RE = re.compile(r"\s+")


def _normalize(text):
    """Strips stray punctuation the browser's speech recognizer sometimes
    appends (periods, commas) and collapses whitespace, without touching
    the letters themselves."""
    text = _PUNCT_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def _prefix_agrees(a, b, n=3):
    """True if `a` and `b` start the same way (first `n` characters, or
    the full shorter string if it's under `n` characters).

    Used to gate BOTH fuzzy-match passes below, on top of their ratio
    cutoff. Many antibiotic names only differ at the start and share a
    drug-class ending -- "-cillin" (ampicillin/amoxicillin/piperacillin),
    "-mycin" (vancomycin/azithromycin/clindamycin), "-floxacin"... so a
    shared ending alone can pull two genuinely DIFFERENT real drugs to a
    deceptively high difflib ratio (e.g. "piperacillin" vs "ampicillin"
    scores 0.73 -- comfortably over MATCH_CUTOFF on its own). A real
    mis-hearing or typo of a word almost always still gets the opening
    sound right, so requiring the start to agree keeps that case working
    while refusing to gamble on which same-suffix drug was meant -- in
    line with this module's whole approach of leaving a case unmatched
    (the clinician just types it) rather than silently guessing wrong."""
    cut = min(n, len(a), len(b))
    return a[:cut] == b[:cut]


def _find_by_keywords(candidates, include, exclude=()):
    """Looks through this hospital's actual antibiotics list (already
    flattened into the lowercased generic-name/brand-name -> real generic
    name map built in resolve_spoken_antibiotic_name) for an entry whose
    name contains every keyword in `include` and none of `exclude`.

    Resolving through the live list -- rather than a hardcoded spelling --
    means a fragment rule only ever fires if the drug it's meant for is
    actually in this hospital's reference table, and always returns that
    drug's real spelling/capitalization from the table."""
    for key, generic in candidates.items():
        if all(kw in key for kw in include) and not any(kw in key for kw in exclude):
            return generic
    return None


# Fragment rules for the generic/scientific names clinicians here commonly
# shorten when speaking, and the browser's speech recognizer commonly
# mangles further. Checked in order, first match wins -- order barely
# matters since the fragments themselves don't overlap, but the amoxicillin
# pair is kept together since telling them apart is the one case that does.
#
# Each entry: (test(cleaned_phrase, words) -> bool, include keywords,
# exclude keywords) -- see _find_by_keywords above.
_FRAGMENT_RULES = [
    # any part of the word contains "triaxone" -> ceftriaxone
    (lambda t, w: "triaxone" in t, ["ceftriaxone"], []),
    # "cipro" -> ciprofloxacin
    (lambda t, w: "cipro" in t, ["ciprofloxacin"], []),
    # "amox" in one word + "clavu"/"clavo" in another word -> the combo drug
    (lambda t, w: any("amox" in x for x in w) and any(("clavu" in x or "clavo" in x) for x in w),
     ["amoxicillin", "clav"], []),
    # a single word containing "amox" and ending in "n" -> amoxicillin alone
    # (never the combo -- excluded explicitly so the two can never be mixed up)
    (lambda t, w: len(w) == 1 and "amox" in w[0] and w[0].endswith("n"),
     ["amoxicillin"], ["clav"]),
    # "azithro" -> azithromycin
    (lambda t, w: "azithro" in t, ["azithromycin"], []),
    # "clari" or "clarithro" -> clarithromycin
    (lambda t, w: "clari" in t, ["clarithromycin"], []),
    # "levo" -> levofloxacin
    (lambda t, w: "levo" in t, ["levofloxacin"], []),
    # "line" or "zolid" -> linezolid
    (lambda t, w: "line" in t or "zolid" in t, ["linezolid"], []),
    # starts with "mero" -> meropenem
    (lambda t, w: any(x.startswith("mero") for x in w), ["meropenem"], []),
    # starts with "cefuro" or ends with "xime" -> cefuroxime
    (lambda t, w: any(x.startswith("cefuro") for x in w) or any(x.endswith("xime") for x in w),
     ["cefuroxime"], []),
    # ends with "dime" (covers "...azidime" too) -> ceftazidime
    (lambda t, w: any(x.endswith("dime") for x in w), ["ceftazidime"], []),
    # ends with "kacin" -> amikacin
    (lambda t, w: any(x.endswith("kacin") for x in w), ["amikacin"], []),
    # starts with "genta" -> gentamicin
    (lambda t, w: any(x.startswith("genta") for x in w), ["gentamicin"], []),
    # starts with "moxi" -> moxifloxacin
    (lambda t, w: any(x.startswith("moxi") for x in w), ["moxifloxacin"], []),
    # starts with "clinda" -> clindamycin
    (lambda t, w: any(x.startswith("clinda") for x in w), ["clindamycin"], []),
    # starts with "vanco" -> vancomycin
    (lambda t, w: any(x.startswith("vanco") for x in w), ["vancomycin"], []),
    # starts with "metro" -> metronidazole
    (lambda t, w: any(x.startswith("metro") for x in w), ["metronidazole"], []),
    # starts with "pipera", or "tazo" appears mid-phrase -> piperacillin-tazobactam
    (lambda t, w: any(x.startswith("pipera") for x in w) or "tazo" in t,
     ["piperacillin", "tazo"], []),
]


def _resolve_by_fragment_rules(cleaned, words, candidates):
    for test, include, exclude in _FRAGMENT_RULES:
        if test(cleaned, words):
            found = _find_by_keywords(candidates, include, exclude)
            if found:
                return found
    return None


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

    cleaned = _normalize(heard.lower())

    # Pass 1: fragment rules for shortened/mangled generic (scientific)
    # names -- see _FRAGMENT_RULES above. Deliberately runs before the
    # whole-phrase fuzzy match below: a short fragment like "moxi" or
    # "amox" can otherwise score a deceptively high similarity against an
    # unrelated short BRAND name (e.g. "Amoxil") just for being a similar
    # length, which would silently resolve to the wrong drug.
    words = cleaned.split()
    fragment_match = _resolve_by_fragment_rules(cleaned, words, candidates)
    if fragment_match:
        return {"heard": heard, "resolved_name": fragment_match, "matched": True}

    # Pass 2: whole-phrase fuzzy match (brand names, cleanly-heard full
    # generic names). Also requires prefix agreement (see _prefix_agrees)
    # so a shared drug-class ending can't alone pull in a different real
    # drug -- get a few candidates back and take the first that agrees,
    # rather than trusting get_close_matches' single best-ratio pick.
    for key in difflib.get_close_matches(cleaned, candidates.keys(), n=3, cutoff=MATCH_CUTOFF):
        if _prefix_agrees(cleaned, key):
            return {"heard": heard, "resolved_name": candidates[key], "matched": True}

    # Pass 3: word-by-word fuzzy fallback -- catches cases like "give me
    # augmentin please" or a filler word the recognizer tacked on, where the
    # drug name itself is clear but the full phrase doesn't match well.
    # Same prefix-agreement guard as pass 2, for the same reason.
    for word in words:
        if len(word) < 3:
            continue
        for key in difflib.get_close_matches(word, candidates.keys(), n=3, cutoff=WORD_MATCH_CUTOFF):
            if _prefix_agrees(word, key):
                return {"heard": heard, "resolved_name": candidates[key], "matched": True}

    return {"heard": heard, "resolved_name": heard, "matched": False}
