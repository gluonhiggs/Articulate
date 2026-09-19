"""Unit tests for glossary-driven transcript correction."""

from __future__ import annotations

from backend.services.interview_glossary import (
    GlossaryEntry,
    apply_corrections,
    correct_transcript,
    phonetic_key,
    split_camel_case,
)

GLOSSARY = [
    GlossaryEntry("PySpark"),
    GlossaryEntry("Databricks"),
    GlossaryEntry("PostgreSQL", ("postgres", "post gres")),
    GlossaryEntry("Spark"),
    GlossaryEntry("Spark SQL"),
    GlossaryEntry("Delta Lake"),
    GlossaryEntry("Kubernetes", ("k8s",)),
    GlossaryEntry("Airflow"),
    GlossaryEntry("C++", ("c plus plus",)),
]


def test_split_camel_case_and_phonetic_key():
    assert split_camel_case("PySpark") == "py spark"
    assert split_camel_case("PostgreSQL") == "postgre sql"
    assert phonetic_key("pyspark") == "pispark"
    assert phonetic_key("quickkafka") == "kuikafka"


def test_corrects_misheard_terms_with_offsets_in_original():
    transcript = "I used pie spark on data bricks and stored results in post gres."
    corrected, corrections = correct_transcript(transcript, GLOSSARY)

    assert corrected == "I used PySpark on Databricks and stored results in PostgreSQL."
    assert [(c["original"], c["replacement"]) for c in corrections] == [
        ("pie spark", "PySpark"),
        ("data bricks", "Databricks"),
        ("post gres", "PostgreSQL"),
    ]
    for correction in corrections:
        assert transcript[correction["start"] : correction["end"]] == correction["original"]
    assert apply_corrections(transcript, corrections) == corrected


def test_alias_and_fuzzy_alias_match():
    corrected, _ = correct_transcript("we moved from postgress to k8s and air flow", GLOSSARY)
    assert corrected == "we moved from PostgreSQL to Kubernetes and Airflow"


def test_ordinary_sentence_is_unchanged():
    transcript = "I think the data pipeline was quite reliable, and the sparks of the team made it work."
    assert correct_transcript(transcript, GLOSSARY) == (transcript, [])


def test_case_only_differences_are_not_corrections():
    transcript = "we run pyspark and spark sql jobs on delta lake"
    assert correct_transcript(transcript, GLOSSARY) == (transcript, [])


def test_fuzzy_match_does_not_absorb_neighbouring_words():
    transcript = "we ran spark sql in production on delta lake today"
    assert correct_transcript(transcript, GLOSSARY) == (transcript, [])


def test_single_common_word_is_never_fuzzy_corrected():
    glossary = [GlossaryEntry("Kluster")]
    assert correct_transcript("the cluster is healthy", glossary) == ("the cluster is healthy", [])
    corrected, _ = correct_transcript("the klusterr is healthy", glossary)
    assert corrected == "the Kluster is healthy"


def test_symbol_term_via_spoken_alias():
    corrected, _ = correct_transcript("I wrote c plus plus for years", GLOSSARY)
    assert corrected == "I wrote C++ for years"


def test_no_glossary_or_empty_transcript():
    assert correct_transcript("pie spark", []) == ("pie spark", [])
    assert correct_transcript("", GLOSSARY) == ("", [])


def test_n_grams_do_not_cross_punctuation():
    transcript = "we store data, bricks are for walls"
    assert correct_transcript(transcript, GLOSSARY) == (transcript, [])
