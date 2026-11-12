"""
A coach uploads the client's own list of questions, so the finder must return them in
the coach's wording and order, and nothing else from the file.
"""

from __future__ import annotations

from backend.services.interview_packs import IMPORTED_TOPIC, imported_question_upserts
from backend.services.question_list import MAX_QUESTIONS, find_questions

BULLET = chr(0x2022)


class TestFindQuestions:
    def test_reads_a_numbered_list(self) -> None:
        text = "1. Explain lazy evaluation in Spark.\n2) How do you make a batch job idempotent?\n(3) What is a shuffle?"
        assert find_questions(text) == [
            "Explain lazy evaluation in Spark.",
            "How do you make a batch job idempotent?",
            "What is a shuffle?",
        ]

    def test_reads_q_numbers_dashes_and_word_bullets(self) -> None:
        text = f"Q1: Tell us about yourself.\n- Describe your Kafka experience\n{BULLET} How do you monitor pipelines?"
        assert find_questions(text) == [
            "Tell us about yourself.",
            "Describe your Kafka experience",
            "How do you monitor pipelines?",
        ]

    def test_reads_unnumbered_lines_that_end_with_a_question_mark(self) -> None:
        assert find_questions("What is a REST API?\nHow does Redis reduce latency?") == [
            "What is a REST API?",
            "How does Redis reduce latency?",
        ]

    def test_keeps_a_numbered_question_wrapped_over_two_lines_together(self) -> None:
        text = "1. When would you use a window function\n   instead of GROUP BY?\n2. What is an index?"
        assert find_questions(text)[0] == "When would you use a window function instead of GROUP BY?"

    def test_joins_a_sentence_that_wraps_onto_a_lower_case_line(self) -> None:
        assert find_questions("How does Redis caching\nreduce latency?") == ["How does Redis caching reduce latency?"]

    def test_does_not_glue_a_heading_onto_the_question_under_it(self) -> None:
        assert find_questions("Backend round\nWhat is a REST API?") == ["What is a REST API?"]

    def test_drops_headings_and_notes_that_are_not_questions(self) -> None:
        text = "Interview questions for Acme\nPlease prepare well.\n\n1. What is a shuffle?\nNotes: ask follow ups."
        assert find_questions(text) == ["What is a shuffle?"]

    def test_drops_fragments_too_short_to_be_a_question(self) -> None:
        assert find_questions("1. Spark\n2. What is a shuffle?") == ["What is a shuffle?"]

    def test_drops_exact_repeats(self) -> None:
        assert find_questions("What is a shuffle?\nWhat is a shuffle?") == ["What is a shuffle?"]

    def test_stops_at_the_limit(self) -> None:
        text = "\n".join(f"{index}. Question number {index} here?" for index in range(1, 40))
        assert len(find_questions(text)) == MAX_QUESTIONS

    def test_finds_nothing_in_a_file_with_no_questions(self) -> None:
        assert find_questions("Dear team,\nthe interview is on Monday.") == []


QUESTIONS = ["Explain lazy evaluation in Spark.", "What is a shuffle?"]
KEY_POINT = {"text": "Transformations wait for an action", "importance": "core", "source_quote": ""}


class TestImportedQuestionUpserts:
    def test_keeps_the_coach_s_wording_even_when_the_model_rephrases(self) -> None:
        output = {"answers": [{"number": 1, "topic": "Spark execution", "text": "Rephrased!", "key_points": [KEY_POINT]}]}
        upserts = imported_question_upserts(QUESTIONS, output)
        assert [upsert.text for upsert in upserts] == QUESTIONS

    def test_attaches_key_points_by_number_and_leaves_them_unapproved(self) -> None:
        output = {"answers": [{"number": 2, "topic": "Spark shuffle", "key_points": [KEY_POINT], "misconceptions": []}]}
        first, second = imported_question_upserts(QUESTIONS, output)
        assert first.key_points == []
        assert [key_point.approved for key_point in second.key_points] == [False]
        assert second.topic == "Spark shuffle"

    def test_creates_every_question_when_the_model_wrote_nothing(self) -> None:
        upserts = imported_question_upserts(QUESTIONS, {})
        assert [upsert.text for upsert in upserts] == QUESTIONS
        assert all(upsert.topic == IMPORTED_TOPIC and upsert.key_points == [] for upsert in upserts)

    def test_ignores_answers_for_numbers_that_are_not_in_the_list(self) -> None:
        output = {"answers": [{"number": 9, "topic": "Ghost", "key_points": [KEY_POINT]}]}
        assert all(upsert.key_points == [] for upsert in imported_question_upserts(QUESTIONS, output))
