"""Unit tests for the pure interview grading rules."""

from __future__ import annotations

import time

import pytest

from backend.services.interview_scoring import (
    QUOTE_NOT_FOUND_REASON,
    QUOTE_REUSED_REASON,
    FollowUpOption,
    QuoteIndex,
    apply_quote_rules,
    choose_follow_up,
    content_score,
    merge_verdict,
    normalize_text,
    quote_in_text,
)

TRANSCRIPT = (
    "Well, an index is a separate data structure, usually a B-tree, that lets the database find rows "
    "without scanning the whole table. The trade-off is that every insert and update also has to "
    "maintain the index, so writes get slower and it uses extra disk space."
)


class TestQuoteCheck:
    def test_normalize_strips_punctuation_case_and_apostrophes(self):
        assert normalize_text("  It's a B-tree,   right? ") == "its a b tree right"

    def test_exact_quote_with_different_punctuation_and_case(self):
        assert quote_in_text("Every insert and update also has to maintain the index.", TRANSCRIPT)

    def test_fuzzy_quote_with_one_misheard_word(self):
        assert quote_in_text("lets the database find rows without scaning the whole table", TRANSCRIPT)

    def test_fuzzy_quote_below_threshold_is_rejected(self):
        assert not quote_in_text("lets the server locate records without reading every table", TRANSCRIPT)

    def test_quote_shorter_than_three_words_never_counts(self):
        assert not quote_in_text("B-tree", TRANSCRIPT)
        assert not quote_in_text("writes slower", TRANSCRIPT)

    def test_quote_not_present(self):
        assert not quote_in_text("a hash index gives constant time range scans", TRANSCRIPT)

    def test_empty_or_missing_quote(self):
        index = QuoteIndex(TRANSCRIPT)
        assert not index.contains("")
        assert not index.contains(None)

    def test_long_source_fuzzy_match_is_fast_enough(self):
        filler = " ".join(f"word{i} lorem ipsum dolor" for i in range(20_000))
        index = QuoteIndex(f"{filler} {TRANSCRIPT} {filler}")
        assert index.contains("so writes get slowr and it uses extra disk space")
        assert not index.contains("completely unrelated sentence about kubernetes pods")

    def test_repetitive_source_does_not_stall_the_search(self):
        index = QuoteIndex("a " * 100_000)
        started = time.perf_counter()
        assert not index.contains("a b " * 150)
        assert not index.contains("a b " * 30)
        assert time.perf_counter() - started < 2.0

    def test_find_returns_the_transcript_words_that_matched(self):
        match = QuoteIndex(TRANSCRIPT).find("lets the database find rows without scaning the whole table")
        assert match is not None
        assert match.text == "lets the database find rows without scanning the whole table"

    @pytest.mark.parametrize(
        ("text", "quote"),
        [
            ("In my experience a HashMap isn't thread safe at all.", "a HashMap is thread safe at all"),
            (
                "Transformations don't run immediately on the cluster.",
                "transformations do run immediately on the cluster",
            ),
            ("You should never store passwords in plain text.", "you should ever store passwords in plain text"),
            (TRANSCRIPT, "lets the database find rows with scanning the whole table"),
        ],
    )
    def test_fuzzy_quote_that_flips_a_negation_is_rejected(self, text, quote):
        assert QuoteIndex(text).find(quote) is None

    def test_fuzzy_quote_keeping_the_negation_still_matches(self):
        match = QuoteIndex("A HashMap is not thread safe at all.").find("a hashmap is not thred safe at all")
        assert match is not None
        assert match.text == "A HashMap is not thread safe at all"


class TestApplyQuoteRules:
    def test_unverifiable_quote_downgrades_to_missing(self):
        claims = [{"verdict": "covered", "quote": "indexes make everything faster always", "reason": "ok"}]
        [result] = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert result["verdict"] == "missing"
        assert result["quote"] is None
        assert result["reason"] == QUOTE_NOT_FOUND_REASON

    def test_credited_quote_is_replaced_by_the_transcript_words(self):
        claims = [
            {"verdict": "covered", "quote": "every insert and update also has to maintain the indx", "reason": "r"}
        ]
        [result] = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert result["verdict"] == "covered"
        assert result["quote"] == "every insert and update also has to maintain the index"

    def test_quote_that_drops_a_negation_is_not_credited(self):
        claims = [
            {"verdict": "covered", "quote": "lets the database find rows with scanning the whole table", "reason": "r"}
        ]
        [result] = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert result["verdict"] == "missing"
        assert result["reason"] == QUOTE_NOT_FOUND_REASON

    def test_incorrect_verdict_also_needs_its_quote(self):
        claims = [{"verdict": "incorrect", "quote": "indexes never slow down writes", "reason": "wrong"}]
        assert apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))[0]["verdict"] == "missing"

    def test_same_quote_supports_at_most_two_key_points(self):
        quote = "writes get slower and it uses extra disk space"
        claims = [{"verdict": verdict, "quote": quote, "reason": "r"} for verdict in ("covered", "partial", "covered")]
        results = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert [r["verdict"] for r in results] == ["covered", "partial", "missing"]
        assert results[2]["reason"] == QUOTE_REUSED_REASON

    def test_overlapping_pieces_of_one_sentence_share_the_reuse_limit(self):
        quotes = [
            "every insert and update also has",
            "insert and update also has to",
            "and update also has to maintain",
            "update also has to maintain the index",
        ]
        claims = [{"verdict": "covered", "quote": quote, "reason": "r"} for quote in quotes]
        results = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert [r["verdict"] for r in results] == ["covered", "covered", "missing", "missing"]
        assert results[3]["reason"] == QUOTE_REUSED_REASON

    def test_quotes_from_different_sentences_are_separate_evidence(self):
        quotes = ["an index is a separate data structure", "every insert and update also has to maintain the index"]
        claims = [{"verdict": "covered", "quote": quote, "reason": "r"} for quote in quotes * 2]
        results = apply_quote_rules(claims, QuoteIndex(TRANSCRIPT))
        assert [r["verdict"] for r in results] == ["covered", "covered", "covered", "covered"]

    def test_missing_claim_is_kept_without_quote(self):
        [result] = apply_quote_rules([{"verdict": "missing", "quote": "", "reason": "absent"}], QuoteIndex(TRANSCRIPT))
        assert result == {"verdict": "missing", "quote": None, "reason": "absent"}


class TestMergeVerdict:
    @pytest.mark.parametrize(
        ("proposer", "verifier", "expected"),
        [
            ("covered", "supported", "covered"),
            ("covered", "partial", "partial"),
            ("covered", "not_supported", "missing"),
            ("partial", "supported", "partial"),
            ("covered", "contradicted", "incorrect"),
            ("partial", "contradicted", "incorrect"),
            ("incorrect", "supported", "incorrect"),
            ("covered", None, "covered"),
        ],
    )
    def test_lower_verdict_wins(self, proposer, verifier, expected):
        assert merge_verdict(proposer, verifier) == expected


class TestContentScore:
    def test_all_core_covered_is_strong(self):
        assert content_score([(3, "covered"), (3, "covered"), (2, "partial"), (1, "missing")], 0) == (78, "strong")

    def test_a_stated_misconception_costs_a_fixed_penalty(self):
        assert content_score([(3, "covered"), (2, "covered"), (1, "covered")], misconception_count=1) == (90, "strong")
        assert content_score([(3, "covered"), (2, "covered"), (1, "covered")], misconception_count=2) == (80, "strong")

    def test_the_penalty_never_takes_a_score_below_zero(self):
        assert content_score([(3, "missing"), (1, "partial")], misconception_count=3) == (0, "weak")

    def test_a_wrong_core_point_scores_exactly_like_a_missing_one(self):
        # Trying and being slightly wrong must never score below staying silent.
        wrong = content_score([(3, "incorrect"), (3, "covered"), (3, "covered"), (2, "covered"), (1, "covered")], 0)
        silent = content_score([(3, "missing"), (3, "covered"), (3, "covered"), (2, "covered"), (1, "covered")], 0)
        assert wrong == silent == (69, "developing")

    def test_a_wrong_core_point_still_keeps_the_answer_out_of_strong(self):
        score, band = content_score([(3, "incorrect"), (2, "covered"), (2, "covered"), (1, "covered")], 0)
        assert band != "strong"
        assert score <= 69

    def test_core_key_point_missing_caps_at_69(self):
        score, band = content_score([(3, "missing"), (2, "covered"), (2, "covered"), (2, "covered"), (2, "covered")], 0)
        assert score == 69
        assert band == "developing"

    def test_core_partial_cannot_be_strong(self):
        score, band = content_score([(3, "partial"), (1, "covered")], 0)
        assert band != "strong"
        assert score <= 69

    def test_weak_band_below_40(self):
        assert content_score([(3, "partial"), (2, "missing"), (2, "missing")], 0) == (21, "weak")

    def test_rounds_half_up(self):
        assert content_score([(2, "covered"), (2, "missing"), (2, "missing"), (2, "partial")], 0) == (38, "weak")
        assert content_score([(1, "partial"), (1, "missing"), (1, "missing"), (1, "missing")], 0) == (13, "weak")

    def test_requires_key_points(self):
        with pytest.raises(ValueError):
            content_score([], 0)


class TestChooseFollowUp:
    OPTIONS = [
        FollowUpOption(question_id=10, position=0, trigger_key_point_uid=None),
        FollowUpOption(question_id=11, position=1, trigger_key_point_uid="kp-a"),
        FollowUpOption(question_id=12, position=2, trigger_key_point_uid="kp-b"),
        FollowUpOption(question_id=13, position=3, trigger_key_point_uid="kp-c"),
    ]
    WEIGHTS = {"kp-a": 1, "kp-b": 3, "kp-c": 2}

    def test_incorrect_beats_missing_and_partial(self):
        verdicts = {"kp-a": "partial", "kp-b": "missing", "kp-c": "incorrect"}
        assert choose_follow_up(self.OPTIONS, verdicts, self.WEIGHTS, "weak") == 13

    def test_missing_beats_partial(self):
        verdicts = {"kp-a": "missing", "kp-b": "partial", "kp-c": "covered"}
        assert choose_follow_up(self.OPTIONS, verdicts, self.WEIGHTS, "developing") == 11

    def test_ties_break_by_weight_then_position(self):
        verdicts = {"kp-a": "missing", "kp-b": "missing", "kp-c": "missing"}
        assert choose_follow_up(self.OPTIONS, verdicts, self.WEIGHTS, "weak") == 12
        same_weight = {"kp-a": 2, "kp-b": 2, "kp-c": 2}
        assert choose_follow_up(self.OPTIONS, verdicts, same_weight, "weak") == 11

    def test_strong_answer_without_triggers_gets_untriggered_follow_up(self):
        verdicts = {"kp-a": "covered", "kp-b": "covered", "kp-c": "covered"}
        assert choose_follow_up(self.OPTIONS, verdicts, self.WEIGHTS, "strong") == 10

    def test_no_follow_up_when_nothing_triggered_and_not_strong(self):
        verdicts = {"kp-a": "covered", "kp-b": "covered", "kp-c": "covered"}
        assert choose_follow_up(self.OPTIONS, verdicts, self.WEIGHTS, "developing") is None

    def test_strong_answer_without_untriggered_options(self):
        options = [o for o in self.OPTIONS if o.trigger_key_point_uid]
        verdicts = {"kp-a": "covered", "kp-b": "covered", "kp-c": "covered"}
        assert choose_follow_up(options, verdicts, self.WEIGHTS, "strong") is None
