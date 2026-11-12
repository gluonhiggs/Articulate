"""
The matcher decides which questions a candidate is shown, so a false match costs them
practice time on something nobody asked about, and a miss hides a question they need.
"""

from __future__ import annotations

import pytest

from backend.services.interview_skills import SkillRow, build_rows, sort_key
from backend.services.skills import find_skills, known_skills, label_of


class TestFindSkills:
    def test_reads_the_technologies_out_of_a_question(self) -> None:
        found = find_skills("In Spark, what triggers a computation, and how does PostgreSQL differ?")
        assert found == ["spark", "postgresql"]

    def test_keeps_the_order_they_first_appear(self) -> None:
        assert find_skills("Airflow then Kafka then Airflow again") == ["airflow", "kafka"]

    def test_matches_a_written_form_as_well_as_the_name(self) -> None:
        assert find_skills("we use PySpark daily") == ["spark"]
        assert find_skills("the k8s cluster") == ["kubernetes"]
        assert find_skills("a postgres database") == ["postgresql"]

    def test_matches_a_name_that_ends_in_punctuation(self) -> None:
        assert find_skills("C# and .NET on the backend") == ["csharp"]
        assert find_skills("written in C++") == ["cpp"]
        assert find_skills("our CI/CD runs on Jenkins") == ["ci-cd"]

    def test_prefers_the_longer_name_at_the_same_place(self) -> None:
        assert find_skills("we run SQL Server") == ["sqlserver"]

    @pytest.mark.parametrize(
        "sentence",
        [
            "please go to the rest of the room",
            "spring is the best season",
            "he joined the team and we had a rest",
        ],
    )
    def test_ignores_ordinary_english_that_looks_like_a_technology(self, sentence: str) -> None:
        assert find_skills(sentence) == []

    def test_does_not_match_inside_a_longer_word(self) -> None:
        assert find_skills("javascripting is not a word") == []
        assert find_skills("sparkle") == []

    def test_stops_at_the_limit(self) -> None:
        text = "python java scala rust kafka airflow docker redis mysql"
        assert len(find_skills(text, limit=3)) == 3

    def test_has_a_readable_label_for_every_skill_it_can_return(self) -> None:
        for skill in find_skills("spark postgresql ci/cd c# node.js"):
            assert label_of(skill) != skill.replace("-", " ") or skill == "rust"


class TestKnownSkills:
    def test_keeps_only_names_in_the_vocabulary(self) -> None:
        assert known_skills(["spark", "nonsense", "SQL"]) == ["spark", "sql"]

    def test_drops_repeats(self) -> None:
        assert known_skills(["spark", "spark"]) == ["spark"]


def row(**overrides) -> SkillRow:
    base = dict(
        skill="spark", label="Apache Spark", question_count=3, in_job=True, in_cv=True, best_score=80, answered=2
    )
    base.update(overrides)
    return SkillRow(**base)


class TestRanking:
    def test_a_gap_the_job_asks_for_comes_first(self) -> None:
        rows = sorted([row(), row(skill="airflow", question_count=0, answered=0, best_score=None)], key=sort_key)
        assert rows[0].skill == "airflow"
        assert rows[0].state == "no_questions"

    def test_a_weak_skill_beats_an_unpractised_one(self) -> None:
        weak = row(skill="sql", best_score=40, answered=1)
        fresh = row(skill="kafka", best_score=None, answered=0)
        assert sorted([fresh, weak], key=sort_key)[0].skill == "sql"

    def test_a_skill_the_job_wants_outranks_one_it_does_not(self) -> None:
        wanted = row(skill="sql", in_job=True, best_score=90, answered=4)
        unwanted = row(skill="kafka", in_job=False, question_count=0, answered=0, best_score=None)
        assert sorted([unwanted, wanted], key=sort_key)[0].skill == "sql"

    def test_the_worse_score_comes_first_among_weak_skills(self) -> None:
        rows = sorted([row(skill="a", best_score=65), row(skill="b", best_score=20)], key=sort_key)
        assert [item.skill for item in rows] == ["b", "a"]


class TestBuildRows:
    def test_counts_the_questions_carrying_each_skill(self) -> None:
        rows = build_rows({1: ["spark"], 2: ["spark", "sql"]}, {}, [], [])
        counts = {item.skill: item.question_count for item in rows}
        assert counts == {"spark": 2, "sql": 1}

    def test_lists_a_job_skill_with_no_questions_at_all(self) -> None:
        rows = build_rows({}, {}, ["airflow"], [])
        assert [(item.skill, item.question_count, item.state) for item in rows] == [("airflow", 0, "no_questions")]

    def test_keeps_the_best_score_across_the_questions_of_a_skill(self) -> None:
        rows = build_rows({1: ["spark"], 2: ["spark"]}, {1: [30, 55], 2: [70]}, [], [])
        assert rows[0].best_score == 70
        assert rows[0].answered == 2
