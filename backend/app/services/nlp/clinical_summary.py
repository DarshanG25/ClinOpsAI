"""Explainable clinical relevance scoring and extractive condensation.

This is a deterministic keyword/rule prototype, not a trained or validated
clinical summarization model. Summary content is quoted from source segments.
"""
from __future__ import annotations

import re
from typing import Any


METHOD = "keyword-extractive-v1"
VERSION = "1"

_CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "chief_complaint": (
        "problem today", "reason for visit", "main concern", "complaint",
        "taklif", "tras hoto",
    ),
    "symptoms": (
        "pain", "ache", "fever", "cough", "cold", "nausea", "vomit", "diarr",
        "rash", "itch", "dizzy", "weakness", "fatigue", "breathless", "swelling",
        "headache", "sore throat", "bukhar", "taap", "dard", "dukht", "khokla",
        "khokhala", "angadukhi", "sardi", "khansi", "ulti", "julaab", "khujli",
    ),
    "duration_onset": (
        "since", "started", "began", "onset", "days ago", "weeks ago",
        "se din", "din se", "divas", "pasun", "kab se", "when did",
    ),
    "severity_frequency": (
        "severe", "mild", "moderate", "worse", "better", "every day", "daily",
        "often", "sometimes", "frequency", "scale of", "out of 10",
    ),
    "associated_symptoms": (
        "associated with", "along with", "also have", "and also", "as well",
        "sath", "sobat",
    ),
    "medical_history": (
        "medical history", "history of", "previous diagnosis", "diagnosed with",
        "diabetes", "hypertension", "asthma", "surgery", "chronic", "past illness",
    ),
    "medications": (
        "medication", "medicine", "medicines", "tablet", "capsule", "syrup",
        "taking", "prescribe", "dose", "mg", "ml", "dawa", "goli", "औषध",
    ),
    "allergies": (
        "allergy", "allergic", "allergies", "drug reaction", "allerg",
    ),
    "previous_treatment": (
        "previous treatment", "already tried", "tried", "treated with",
        "treatment before", "not helping",
    ),
    "measurements": (
        "blood pressure", "bp ", "temperature", "pulse", "oxygen", "spo2",
        "weight", "sugar level", "temperature is", "°c", "bpm",
    ),
    "investigations": (
        "test result", "lab result", "investigation", "report shows", "blood test",
        "x-ray", "xray", "scan", "test was", "test is", "test shows", "lab",
    ),
    "assessment": (
        "diagnosis", "impression", "assessment", "looks like", "could be",
        "may be", "might be", "suspect", "likely", "lag raha", "hou shakte",
        "appears to", "viral fever", "sinusitis", "gastritis", "acid reflux",
        "migraine", "urinary tract infection", "food poisoning", "throat infection",
        "bacterial infection", "allergic rhinitis",
    ),
    "observations": (
        "on examination", "examination", "observed", "findings", "tenderness",
        "sounds clear", "looks well", "lungs clear", "clear to auscultation",
        "no tenderness", "examination normal",
    ),
    "treatment": (
        "take ", "start ", "stop ", "continue ", "increase ", "reduce ",
        "prescribe", "treatment", "medication plan", "apply ",
    ),
    "precautions_advice": (
        "avoid", "drink plenty", "rest", "precaution", "advice", "watch for",
        "seek care", "emergency", "fluids", "gargle", "taalaa", "ghya",
    ),
    "tests_recommended": (
        "order a", "recommend a test", "get a test", "test recommended",
        "blood work", "do the test", "investigation advised",
    ),
    "follow_up": (
        "follow up", "follow-up", "come back", "return in", "next visit",
        "review in", "see me in", "next appointment", "follow up",
    ),
    "patient_concerns": (
        "worried", "concern", "afraid", "question", "can i", "should i",
        "will this", "is it safe",
    ),
}

_CATEGORY_PRIORITY = (
    "chief_complaint", "symptoms", "duration_onset", "severity_frequency",
    "associated_symptoms", "medical_history", "allergies", "medications",
    "previous_treatment", "measurements", "investigations", "assessment",
    "observations", "treatment", "precautions_advice", "tests_recommended",
    "follow_up", "patient_concerns",
)
_PATIENT_CATEGORIES = {
    "chief_complaint", "symptoms", "duration_onset", "severity_frequency",
    "associated_symptoms", "medical_history", "medications", "allergies",
    "previous_treatment", "measurements", "patient_concerns",
}
_DOCTOR_CATEGORIES = {
    "assessment", "observations", "treatment", "precautions_advice",
    "tests_recommended", "follow_up", "investigations", "medications",
}
_ROLE_SYNONYMS = {
    "patient": "Patient",
    "doctor": "Doctor",
    "physician": "Doctor",
    "other/unknown": "Other/Unknown",
    "unknown": "Unknown",
    "other": "Other/Unknown",
    "patient's attendant/relative": "Patient's Attendant/Relative",
}
_REPEAT_TEXT = re.compile(r"\s+")


def _category_matches(text: str) -> list[str]:
    lowered = text.casefold()
    matches = [
        category
        for category, terms in _CATEGORY_TERMS.items()
        if any(term in lowered for term in terms)
    ]
    if (
        "duration_onset" not in matches
        and re.search(r"\bfor\s+(?:\d+|a|an|the|last|past|about|nearly)\b", lowered)
    ):
        matches.append("duration_onset")
    return matches


def _speaker(segment: dict[str, Any]) -> str:
    role = segment.get("speaker_role")
    if role:
        return _ROLE_SYNONYMS.get(str(role).casefold(), str(role))
    return "Unknown"


def _score_segment(segment: dict[str, Any]) -> tuple[float, list[str]]:
    text = str(segment.get("text") or "").strip()
    categories = _category_matches(text)
    if not text or not categories:
        return 0.0, categories

    score = min(0.58 + 0.11 * len(categories), 0.91)
    role = _speaker(segment)
    preferred_categories = (
        _PATIENT_CATEGORIES if role in {"Patient", "Patient's Attendant/Relative"}
        else _DOCTOR_CATEGORIES if role == "Doctor"
        else set()
    )
    score = min(score + (0.05 if preferred_categories.intersection(categories) else 0.01), 0.95)
    if len(text.split()) < 3:
        score = max(score, 0.55)
    return round(score, 2), categories


def _segment_identifier(segment: dict[str, Any], index: int) -> str:
    identifier = segment.get("segment_id") or segment.get("id")
    return str(identifier) if identifier is not None else f"segment-{index:04d}"


def _normalized_text(text: str) -> str:
    return _REPEAT_TEXT.sub(" ", text.casefold()).strip(" .,!?:;")


def analyze_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score each source segment while retaining original words and timestamps."""
    analyzed = []
    for index, segment in enumerate(segments):
        score, categories = _score_segment(segment)
        analyzed.append({
            "segment_id": _segment_identifier(segment, index),
            "speaker": _speaker(segment),
            "speaker_id": segment.get("speaker_id"),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": str(segment.get("text") or ""),
            "category": categories[0] if categories else "non_clinical",
            "categories": categories,
            "relevance_score": score,
            "is_clinically_relevant": score >= 0.55,
        })
    return analyzed


def condense_segments(analyzed_segments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Prioritize unique source excerpts within a three-minute speech budget."""
    candidates: list[dict[str, Any]] = []
    seen_text: set[tuple[str, str]] = set()
    for segment in analyzed_segments:
        if not segment["is_clinically_relevant"]:
            continue
        normalized = (segment["speaker"], _normalized_text(segment["text"]))
        if not normalized[1] or normalized in seen_text:
            continue
        seen_text.add(normalized)
        candidates.append(segment)

    def source_duration(segment: dict[str, Any]) -> float:
        start, end = segment["start"], segment["end"]
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            return float(end - start)
        return max(len(segment["text"].split()) / 2.5, 0.4)

    def priority(segment: dict[str, Any]) -> tuple[int, float, float]:
        category_rank = min(
            (_CATEGORY_PRIORITY.index(category) for category in segment["categories"]),
            default=len(_CATEGORY_PRIORITY),
        )
        start = segment["start"] if isinstance(segment["start"], (int, float)) else float("inf")
        return category_rank, -segment["relevance_score"], start

    candidates.sort(key=priority)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    used_seconds = 0.0
    budget_seconds = 180.0
    covered_categories: set[str] = set()

    # Retain at least the highest-priority excerpt for each category while
    # there is room, then use remaining time for the next best details.
    for candidate in candidates:
        new_categories = set(candidate["categories"]) - covered_categories
        if not new_categories:
            continue
        duration = source_duration(candidate)
        if used_seconds + duration <= budget_seconds or not selected:
            selected.append(candidate)
            selected_ids.add(candidate["segment_id"])
            covered_categories.update(candidate["categories"])
            used_seconds += duration

    for candidate in candidates:
        if candidate["segment_id"] in selected_ids:
            continue
        duration = source_duration(candidate)
        if used_seconds + duration <= budget_seconds:
            selected.append(candidate)
            selected_ids.add(candidate["segment_id"])
            used_seconds += duration
    selected.sort(key=lambda item: (
        item["start"] if isinstance(item["start"], (int, float)) else float("inf")
    ))

    if not selected:
        return "", []

    lines = ["Condensed clinical content (verbatim source excerpts):"]
    for category in _CATEGORY_PRIORITY:
        category_segments = [
            segment for segment in selected
            if segment["category"] == category
        ]
        if not category_segments:
            continue
        lines.append(f"\n{category.replace('_', ' ').title()}:")
        for segment in category_segments:
            start = segment["start"]
            end = segment["end"]
            timestamp = ""
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                timestamp = f"[{start:.2f}-{end:.2f}s] "
            lines.append(f"- {timestamp}{segment['speaker']}: {segment['text'].strip()}")
    return "\n".join(lines), selected


def generate_clinical_summary(segments: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = analyze_segments(segments)
    summary_text, selected = condense_segments(analyzed)
    return {
        "summary_text": summary_text,
        "segment_scores": analyzed,
        "relevant_segments": selected,
        "source_segment_ids": [segment["segment_id"] for segment in selected],
        "status": "generated" if selected else "no_relevant_content",
        "method": METHOD,
        "version": VERSION,
    }
