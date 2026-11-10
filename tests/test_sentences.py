"""Which spoken sentences get offered a rewrite is a stated rule, so it is tested like one.

The LLM only ever sees sentences this module picked, so a rule that picks everything
wastes free-tier quota and a rule that picks nothing hides the feature.
"""

from __future__ import annotations

import pytest

from backend.services.sentences import MIN_WORDS, find_span, sentence_spans, weak_sentences

RUN_ON = (
    "Spark chose this design because in data engineering usually the transformations are very "
    "complicated and with some attempts developers may try to optimize their code but they cannot "
    "fully do everything so some data transformations can be broken down into smaller units."
)
CLEAN = "Transformations are recorded into a plan instead of running immediately."


class TestSentenceSpans:
    def test_splits_on_terminal_punctuation(self) -> None:
        spans = sentence_spans("One thing. Two things! Three?")
        assert [("One thing.", 0), ("Two things!", 11), ("Three?", 23)] == [
            (text, start) for (start, end) in spans for text in [("One thing. Two things! Three?")[start:end]]
        ]

    def test_unpunctuated_tail_is_its_own_sentence(self) -> None:
        text = "First one. then a tail with no full stop"
        spans = sentence_spans(text)
        assert len(spans) == 2
        assert text[spans[1][0] : spans[1][1]] == "then a tail with no full stop"

    def test_text_without_punctuation_is_one_sentence(self) -> None:
        assert sentence_spans("no punctuation at all") == [(0, 21)]

    def test_empty_text_still_yields_one_span(self) -> None:
        assert sentence_spans("") == [(0, 0)]


class TestWeakSentences:
    def test_a_clean_sentence_is_left_alone(self) -> None:
        assert weak_sentences(CLEAN) == []

    def test_a_run_on_is_flagged_for_length_and_chaining(self) -> None:
        (found,) = weak_sentences(RUN_ON)
        assert found["reasons"] == ["run_on", "chained"]
        assert found["text"] == RUN_ON

    def test_a_grammar_offset_inside_a_sentence_flags_it(self) -> None:
        text = f"{CLEAN} The plan is called a lineage graph and it records every step taken."
        offset = text.index("is called")
        assert [found["reasons"] for found in weak_sentences(text, [offset])] == [["grammar"]]

    def test_a_grammar_offset_outside_every_sentence_flags_nothing(self) -> None:
        assert weak_sentences(CLEAN, [10_000]) == []

    def test_short_sentences_are_never_flagged(self) -> None:
        short = "It is lazy."
        assert len(short.split()) < MIN_WORDS
        assert weak_sentences(short, [0]) == []

    def test_a_leading_connective_does_not_count_as_a_chained_clause(self) -> None:
        # "And ..." is how people start a spoken sentence; only chaining mid-sentence counts.
        text = "And Spark treats the user code as an instruction which it keeps for later use."
        assert weak_sentences(text) == []

    def test_results_come_back_in_spoken_order(self) -> None:
        text = f"{CLEAN} {RUN_ON} {CLEAN} {RUN_ON}"
        found = weak_sentences(text)
        assert len(found) == 2
        assert [item["index"] for item in found] == sorted(item["index"] for item in found)

    def test_the_cap_keeps_the_worst_offenders(self) -> None:
        # One sentence with two reasons must survive a cap of one over a single-reason sentence.
        grammar_only = "The plan is called a lineage graph and it records every step that was taken."
        text = f"{grammar_only} {RUN_ON}"
        found = weak_sentences(text, [text.index("is called")], limit=1)
        assert [item["reasons"] for item in found] == [["run_on", "chained"]]

    def test_spans_point_at_the_sentence_in_the_original_text(self) -> None:
        text = f"{CLEAN} {RUN_ON}"
        (found,) = weak_sentences(text)
        assert text[found["start"] : found["end"]].strip() == RUN_ON


class TestFindSpan:
    def test_locates_a_phrase(self) -> None:
        assert find_span("the plan is called lazy", "is called") == (9, 18)

    def test_prefers_the_occurrence_nearest_the_expected_offset(self) -> None:
        text = "is called here and is called there"
        assert find_span(text, "is called", 19) == (19, 28)
        assert find_span(text, "is called", 0) == (0, 9)

    def test_returns_the_first_occurrence_without_an_expected_offset(self) -> None:
        assert find_span("a b a b", "a b") == (0, 3)

    @pytest.mark.parametrize("needle", ["", "absent"])
    def test_missing_phrases_have_no_span(self, needle: str) -> None:
        assert find_span("the plan is lazy", needle) is None
