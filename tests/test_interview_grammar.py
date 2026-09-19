"""Unit tests for check_grammar filtering, with a fake LanguageTool."""

from __future__ import annotations

from types import SimpleNamespace

from backend.services import grammar


def _match(text: str, fragment: str, rule_id: str, category: str = "GRAMMAR"):
    offset = text.index(fragment)
    return SimpleNamespace(
        rule_id=rule_id,
        category=category,
        offset=offset,
        error_length=len(fragment),
        message=f"{rule_id} message",
        replacements=["a", "b", "c", "d"],
    )


class _FakeTool:
    def __init__(self, matches):
        self._matches = matches

    def check(self, text):
        return self._matches


def test_returns_none_when_languagetool_unavailable(monkeypatch):
    monkeypatch.setattr(grammar, "get_lt_tool", lambda: None)
    assert grammar.check_grammar("he go to work", ["Kafka"]) is None


def test_returns_none_when_check_raises(monkeypatch):
    class _Broken:
        def check(self, text):
            raise RuntimeError("server gone")

    monkeypatch.setattr(grammar, "get_lt_tool", lambda: _Broken())
    assert grammar.check_grammar("he go to work", []) is None


def test_filters_artifacts_spelling_and_glossary_terms(monkeypatch):
    text = "yesterday he go to work and deploy kafka topics with pyspark on Databricks"
    matches = [
        _match(text, "he go", "HE_VERB_AGR"),
        _match(text, "yesterday", "UPPERCASE_SENTENCE_START", "CASING"),
        _match(text, "kafka", "MORFOLOGIK_RULE_EN_US", "TYPOS"),
        _match(text, "pyspark", "SOME_TYPO", "TYPOS"),
        _match(text, "deploy kafka", "VERB_NOUN_CONFUSION"),
        _match(text, "Databricks", "EN_A_VS_AN", "MISC"),
        _match(text, "work and", "BORED_OF", "STYLE"),
    ]
    monkeypatch.setattr(grammar, "get_lt_tool", lambda: _FakeTool(matches))

    issues = grammar.check_grammar(text, ["Kafka", "databricks", ""])

    assert [issue["rule_id"] for issue in issues] == ["HE_VERB_AGR", "BORED_OF"]
    assert issues[0]["text"] == "he go"
    assert issues[0]["replacements"] == ["a", "b", "c"]


def test_ignore_terms_respect_word_boundaries(monkeypatch):
    text = "the sparkle of sparks"
    matches = [_match(text, "sparkle", "SOME_RULE")]
    monkeypatch.setattr(grammar, "get_lt_tool", lambda: _FakeTool(matches))
    assert len(grammar.check_grammar(text, ["spark"])) == 1
