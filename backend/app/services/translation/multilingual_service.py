"""Lightweight local translation/labelling for English/Hindi/Marathi.

Per the project brief, the MVP must NOT depend on a paid translation API.
This module provides a small phrasebook for the fixed UI/PDF strings we
generate (status labels, disclaimer, common precaution text) so the demo
works fully offline. It intentionally does NOT attempt full free-text
machine translation of arbitrary clinical text — that limitation is called
out explicitly wherever the module is used, so nothing is silently
mistranslated.
"""
from typing import Optional

PHRASEBOOK = {
    "disclaimer": {
        "en": (
            "ClinOps-AI is an academic prototype and clinical decision-support "
            "demonstration. AI-generated recommendations are not medical advice and "
            "must be independently reviewed and approved by a qualified doctor "
            "before use."
        ),
        "hi": (
            "ClinOps-AI ek academic prototype hai. AI dwara diye gaye sujhav "
            "medical salah nahi hain aur inhe upyog se pehle ek yogya doctor "
            "dwara swतंत्र roop se review aur approve karna anivarya hai."
        ),
        "mr": (
            "ClinOps-AI ha ek academic prototype ahe. AI ne dilele salle vaidyakiya "
            "salla nahit ani te vaparण्यापूर्वी eka patra doctor kadun swतंत्रपणे "
            "tapasun mान्य karणे avashyak ahe."
        ),
    },
    "approved": {"en": "Approved", "hi": "Manzoor", "mr": "Manjoor"},
    "rejected": {"en": "Rejected", "hi": "Asveekrit", "mr": "Nakaarala"},
    "pending_review": {"en": "Pending doctor review", "hi": "Doctor review baaki hai", "mr": "Doctor review baaki ahe"},
}

SUPPORTED_LANGUAGES = ("en", "hi", "mr")


def translate_label(key: str, language: str = "en") -> str:
    """Look up a known UI/PDF phrase in the requested language. Falls back to
    English (and finally to the raw key) if unavailable — never crashes, and
    never invents a translation.
    """
    entry = PHRASEBOOK.get(key)
    if not entry:
        return key
    return entry.get(language) or entry.get("en") or key


def language_label(language: str) -> str:
    return {"en": "English", "hi": "Hindi", "mr": "Marathi"}.get(language, language)


def is_supported(language: Optional[str]) -> bool:
    return language in SUPPORTED_LANGUAGES
