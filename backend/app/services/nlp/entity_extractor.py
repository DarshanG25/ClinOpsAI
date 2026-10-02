"""Hybrid clinical entity extraction.

Approach (transparent, MVP-appropriate — not a medical NER model):
 1. Normalize text (lowercase, collapse whitespace, transliteration-friendly
    Hindi/Marathi number & unit words -> digits/English units).
 2. Regex + dictionary lookup for medication mentions (matches medicines.json
    generic names / aliases), with dosage/frequency/duration/route captured
    from the surrounding text via regex patterns (English + common
    Hindi/Marathi phrasing).
 3. Keyword/dictionary matching for symptoms, diagnoses and precautions
    against curated term lists.

This intentionally avoids hard-coding a fixed output: everything returned is
derived from what actually appears in the given transcript. If nothing
matches, the corresponding list is empty (not fabricated).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from app.config.settings import settings

DATA_DIR = Path(settings.data_dir)
MEDICINES_PATH = DATA_DIR / "medicines.json"


def _load_medicines() -> List[dict]:
    if not MEDICINES_PATH.exists():
        return []
    with open(MEDICINES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


MEDICINES = _load_medicines()

# alias/generic -> medicine record, longest names matched first
_MED_LOOKUP: Dict[str, dict] = {}
for med in MEDICINES:
    _MED_LOOKUP[med["generic_name"].lower()] = med
    for alias in med.get("aliases", []):
        _MED_LOOKUP[alias.lower()] = med
_MED_TERMS_SORTED = sorted(_MED_LOOKUP.keys(), key=len, reverse=True)

SYMPTOM_TERMS = [
    "fever", "headache", "head ache", "cough", "dry cough", "wet cough", "cold",
    "runny nose", "sneezing", "sore throat", "body ache", "body pain", "joint pain",
    "back pain", "stomach pain", "abdominal pain", "vomiting", "nausea", "diarrhea",
    "loose motion", "loose motions", "dehydration", "breathlessness", "wheezing",
    "chest pain", "fatigue", "weakness", "dizziness", "rash", "itching", "swelling",
    "burning urination", "acidity", "heartburn", "poor appetite", "chills",
]

DIAGNOSIS_TERMS = [
    "viral fever", "throat infection", "bacterial infection", "sinusitis",
    "gastritis", "acid reflux", "urinary tract infection", "uti", "dysentery",
    "allergy", "allergic rhinitis", "asthma", "hypertension", "high blood pressure",
    "diabetes", "anemia", "ear infection", "food poisoning", "migraine",
]

PRECAUTION_TERMS = [
    ("rest", "Take adequate rest"),
    ("plenty of fluids", "Drink plenty of fluids"),
    ("drink fluids", "Drink plenty of fluids"),
    ("avoid spicy", "Avoid spicy/oily food"),
    ("tikhat khane taalaa", "Avoid spicy food"),
    ("avoid oily", "Avoid oily food"),
    ("avoid outside food", "Avoid outside/street food"),
    ("bahar ka khana avoid", "Avoid outside/street food"),
    ("gargle", "Warm water gargles"),
    ("garam paani se gargle", "Warm water gargles"),
    ("follow up", "Follow up if symptoms persist or worsen"),
    ("no known drug allergies", "No known drug allergies reported"),
]

# --- Hindi/Marathi -> canonical English normalization for dosage phrasing ---
_HI_MR_NUMBERS = {
    "ek": "1", "do": "2", "don": "2", "teen": "3", "tin": "3", "char": "4",
    "paanch": "5", "panch": "5", "saat": "7", "aath": "8", "das": "10",
}
_FREQ_PHRASES = [
    (r"\b(din mein|roj|roz)\s+(ek|do|don|teen|tin)\s+baar\b", None),  # handled generically below
]

DAY_WORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(_HI_MR_NUMBERS.keys()) + r")\b", re.IGNORECASE
)


def _normalize_numbers(text: str) -> str:
    def repl(match):
        return _HI_MR_NUMBERS.get(match.group(0).lower(), match.group(0))
    return DAY_WORD_PATTERN.sub(repl, text)


# Dosage: "500 mg", "40 mg", "1 sachet", "10 ml"
DOSAGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|ml|mcg|iu|sachet[s]?|puff[s]?)\b", re.IGNORECASE)

# Frequency: English "twice daily", "three times a day", "once daily",
# plus normalized Hindi/Marathi "2 baar", "1 baar subah shaam" etc.
FREQ_PATTERNS = [
    (re.compile(r"\bonce\s+(a\s+)?day\b|\bonce\s+daily\b", re.I), "once daily"),
    (re.compile(r"\btwice\s+(a\s+)?day\b|\btwice\s+daily\b", re.I), "twice daily"),
    (re.compile(r"\bthrice\s+(a\s+)?day\b|\bthree\s+times\s+(a\s+)?day\b", re.I), "three times daily"),
    (re.compile(r"\bfour\s+times\s+(a\s+)?day\b", re.I), "four times daily"),
    (re.compile(r"\b1\s*baar\b", re.I), "once daily"),
    (re.compile(r"\b2\s*baar\b", re.I), "twice daily"),
    (re.compile(r"\b3\s*baar\b", re.I), "three times daily"),
    (re.compile(r"\bsubah\s+shaam\b", re.I), "twice daily (morning and evening)"),
    (re.compile(r"\bsakali\s+ekda\b", re.I), "once daily (morning)"),
    (re.compile(r"\b1\s*vela\b", re.I), "once daily"),
    (re.compile(r"\b2\s*vela\b", re.I), "twice daily"),
    (re.compile(r"\b3\s*vela\b", re.I), "three times daily"),
    (re.compile(r"\bhar\s+din\b|\broj\b|\broz\b", re.I), "once daily"),
]

# Duration: "3 days", "5 din", "1 week"
DURATION_RE_EN = re.compile(r"(\d+)\s*(day|days|week|weeks)\b", re.IGNORECASE)
DURATION_RE_HI = re.compile(r"(\d+)\s*(din|divas|hafta|haftey)\b", re.IGNORECASE)

ROUTE_HINTS = [
    ("inhaler", "inhalation"), ("puff", "inhalation"), ("gel", "topical"),
    ("syrup", "oral"), ("tablet", "oral"), ("capsule", "oral"), ("sachet", "oral"),
]


@dataclass
class ExtractedMedication:
    text: str
    normalized: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    confidence: float = 0.75


def _find_window(text: str, start: int, end: int, radius: int = 45) -> str:
    """Grab context around a match, snapped to whitespace boundaries so we
    never truncate mid-token (e.g. cutting "500 mg" into "00 mg")."""
    lo = max(0, start - radius)
    if lo > 0:
        space = text.find(" ", lo)
        lo = space + 1 if 0 <= space < start else lo
    hi = min(len(text), end + radius)
    if hi < len(text):
        space = text.rfind(" ", end, hi)
        hi = space if space > end else hi
    return text[lo:hi]


def extract_medications(normalized_text: str) -> List[ExtractedMedication]:
    found: List[ExtractedMedication] = []
    seen_spans = set()
    lower = normalized_text.lower()
    for term in _MED_TERMS_SORTED:
        for match in re.finditer(re.escape(term), lower):
            span = (match.start(), match.end())
            if any(s[0] <= span[0] < s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            med = _MED_LOOKUP[term]
            window = _find_window(normalized_text, span[0], span[1])
            # Prefer text *after* the medicine name (standard phrasing is
            # "Medicine 500mg twice daily for 3 days"); fall back to the
            # full window (including preceding context) if nothing is found.
            window_after = normalized_text[span[1]: min(len(normalized_text), span[1] + 60)]

            dosage_match = DOSAGE_RE.search(window_after) or DOSAGE_RE.search(window)
            dosage = f"{dosage_match.group(1)} {dosage_match.group(2)}" if dosage_match else None

            frequency = None
            for pattern, label in FREQ_PATTERNS:
                if pattern.search(window_after):
                    frequency = label
                    break
            if frequency is None:
                for pattern, label in FREQ_PATTERNS:
                    if pattern.search(window):
                        frequency = label
                        break

            duration = None
            dur_match = (DURATION_RE_EN.search(window_after) or DURATION_RE_HI.search(window_after)
                         or DURATION_RE_EN.search(window) or DURATION_RE_HI.search(window))
            if dur_match:
                num, unit = dur_match.group(1), dur_match.group(2).lower()
                unit_norm = "day(s)" if unit in ("day", "days", "din", "divas") else "week(s)"
                duration = f"{num} {unit_norm}"

            route = med.get("default_route", "oral")
            for hint, route_val in ROUTE_HINTS:
                if hint in window.lower():
                    route = route_val
                    break

            found.append(ExtractedMedication(
                text=normalized_text[span[0]:span[1]],
                normalized=med["generic_name"],
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                route=route,
                confidence=0.85 if dosage and frequency else 0.65,
            ))
    return found


def extract_terms(normalized_text: str, terms: List[str]) -> List[str]:
    lower = normalized_text.lower()
    hits = []
    for term in terms:
        if re.search(r"\b" + re.escape(term) + r"\b", lower):
            hits.append(term)
    return hits


def extract_precautions(normalized_text: str) -> List[str]:
    lower = normalized_text.lower()
    hits = []
    for trigger, label in PRECAUTION_TERMS:
        if trigger in lower and label not in hits:
            hits.append(label)
    return hits


def extract_clinical_data(transcript: str) -> List[dict]:
    """Main entry point. Returns a flat list of entity dicts ready for the
    ClinicalEntity repository (entity_type in symptom/diagnosis/medication/precaution).
    """
    if not transcript or not transcript.strip():
        return []

    normalized = _normalize_numbers(transcript)

    rows: List[dict] = []

    for symptom in extract_terms(normalized, SYMPTOM_TERMS):
        rows.append({
            "entity_type": "symptom", "text": symptom, "normalized": symptom,
            "confidence": 0.7,
        })

    for diagnosis in extract_terms(normalized, DIAGNOSIS_TERMS):
        rows.append({
            "entity_type": "diagnosis", "text": diagnosis, "normalized": diagnosis,
            "confidence": 0.7,
        })

    for med in extract_medications(normalized):
        rows.append({
            "entity_type": "medication",
            "text": med.text,
            "normalized": med.normalized,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "duration": med.duration,
            "route": med.route,
            "confidence": med.confidence,
        })

    for precaution in extract_precautions(normalized):
        rows.append({
            "entity_type": "precaution", "text": precaution, "normalized": precaution,
            "confidence": 0.6,
        })

    return rows
