"""Deterministic tests for the explainable, extractive clinical summary."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.nlp.clinical_summary import generate_clinical_summary  # noqa: E402


def _segment(text: str, start: float = 0, end: float = 5, role: str | None = None) -> dict:
    return {
        "start": start,
        "end": end,
        "text": text,
        "speaker_role": role,
        "speaker_id": "speaker-1" if role else None,
    }


def test_short_consultation_condenses_symptoms_and_plan_without_invention():
    segments = [
        _segment("Hello, how are you?", 0, 2),
        _segment("I have had a mild fever since yesterday.", 4, 8, "Patient"),
        _segment("Take Paracetamol 500 mg twice daily for 3 days.", 10, 15, "Doctor"),
        _segment("Goodbye.", 16, 17),
    ]

    result = generate_clinical_summary(segments)

    assert result["status"] == "generated"
    assert len(result["segment_scores"]) == len(segments)
    assert len(result["relevant_segments"]) == 2
    assert "fever since yesterday" in result["summary_text"]
    assert "Paracetamol 500 mg twice daily for 3 days" in result["summary_text"]
    assert "diagnosis" not in result["summary_text"].lower()
    assert [segment["start"] for segment in result["relevant_segments"]] == [4, 10]


def test_long_consultation_prioritizes_relevant_content_within_three_minutes():
    segments = [
        _segment(f"Patient reports fever episode number {index}.", index, index + 1, "Patient")
        for index in range(240)
    ]

    result = generate_clinical_summary(segments)

    assert result["status"] == "generated"
    assert 0 < len(result["relevant_segments"]) <= 180
    assert len(result["source_segment_ids"]) == len(result["relevant_segments"])


def test_irrelevant_conversation_is_excluded_but_informal_clinical_statement_is_kept():
    segments = [
        _segment("Good morning, how was traffic?", 0, 3),
        _segment("Please fill out the registration form.", 3, 6),
        _segment("I thought it was nothing, but my chest pain has been getting worse.", 8, 13),
        _segment("Your appointment is at the front desk.", 14, 17),
    ]

    result = generate_clinical_summary(segments)

    assert len(result["relevant_segments"]) == 1
    assert "chest pain" in result["summary_text"]
    assert "traffic" not in result["summary_text"]
    assert "registration" not in result["summary_text"]


def test_duplicate_statement_is_selected_once_and_keeps_first_timestamp():
    statement = "I have had a headache since Monday."
    result = generate_clinical_summary([
        _segment(statement, 12.4, 15.2, "Patient"),
        _segment(statement, 31.0, 33.0, "Patient"),
    ])

    assert len(result["relevant_segments"]) == 1
    assert result["relevant_segments"][0]["start"] == 12.4
    assert result["relevant_segments"][0]["end"] == 15.2
    assert result["source_segment_ids"] == ["segment-0000"]


def test_hindi_marathi_transliteration_and_unknown_speaker_are_retained():
    result = generate_clinical_summary([
        _segment("Mujhe bukhar hai aur mala angadukhi aahe.", 2.5, 6.75),
    ])

    assert result["relevant_segments"][0]["speaker"] == "Unknown"
    assert result["relevant_segments"][0]["start"] == 2.5
    assert result["relevant_segments"][0]["end"] == 6.75
    assert result["relevant_segments"][0]["is_clinically_relevant"] is True


def test_no_relevant_content_returns_empty_summary_and_segments():
    result = generate_clinical_summary([
        _segment("Hello, thank you for coming in.", 0, 3),
        _segment("The weather is nice today.", 4, 7),
    ])

    assert result["status"] == "no_relevant_content"
    assert result["summary_text"] == ""
    assert result["relevant_segments"] == []
    assert result["source_segment_ids"] == []


def test_missing_clinical_information_is_not_filled_in():
    result = generate_clinical_summary([
        _segment("I have a cough.", 1, 2, "Patient"),
    ])

    assert result["summary_text"]
    assert "diagnosis" not in result["summary_text"].lower()
    assert "medication" not in result["summary_text"].lower()
    assert "allerg" not in result["summary_text"].lower()
    assert result["relevant_segments"][0]["text"] == "I have a cough."
