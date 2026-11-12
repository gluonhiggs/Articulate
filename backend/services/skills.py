"""
Find the technologies named in a piece of text.

The same matcher tags a question, a CV and a job description, so a question matches a
job only when both name the same technology. It is a fixed vocabulary and plain text
matching rather than a model call: the result is free, instant, and identical every
time, which is what lets the skill list show why each row matched.

The list is written for precision. A form that is also an ordinary English word, such
as "go", "rest" or "spring", is left out, because one false match puts a question in
front of a candidate who never asked for it.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

SKILL_FORMS: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript", "java script"),
    "typescript": ("typescript", "type script"),
    "golang": ("golang", "go lang"),
    "csharp": ("c#", "c sharp", ".net", "dotnet"),
    "cpp": ("c++",),
    "rust": ("rust",),
    "scala": ("scala",),
    "sql": ("sql", "window function", "group by"),
    "postgresql": ("postgresql", "postgres", "psql"),
    "mysql": ("mysql",),
    "sqlserver": ("sql server", "mssql", "t-sql"),
    "oracle": ("oracle",),
    "mongodb": ("mongodb", "mongo db"),
    "redis": ("redis",),
    "elasticsearch": ("elasticsearch", "elastic search"),
    "spark": ("spark", "pyspark"),
    "hadoop": ("hadoop", "hdfs", "mapreduce", "map reduce"),
    "kafka": ("kafka",),
    "airflow": ("airflow",),
    "dbt": ("dbt",),
    "snowflake": ("snowflake",),
    "databricks": ("databricks",),
    "bigquery": ("bigquery", "big query"),
    "redshift": ("redshift",),
    "flink": ("flink",),
    "etl": ("etl", "elt", "data pipeline", "data pipelines", "ingestion"),
    "data-modelling": ("data modelling", "data modeling", "star schema", "dimensional model"),
    "data-warehouse": ("data warehouse", "lakehouse", "data lake"),
    "aws": ("aws", "amazon web services", "s3", "ec2", "emr"),
    "azure": ("azure",),
    "gcp": ("gcp", "google cloud"),
    "docker": ("docker", "containerisation", "containerization"),
    "kubernetes": ("kubernetes", "k8s"),
    "terraform": ("terraform",),
    "ci-cd": ("ci/cd", "cicd", "jenkins", "github actions", "gitlab ci"),
    "linux": ("linux", "bash"),
    "git": ("git", "github", "gitlab"),
    "rest-api": ("rest api", "restful", "api design"),
    "graphql": ("graphql",),
    "grpc": ("grpc",),
    "microservices": ("microservice", "microservices"),
    "system-design": ("system design", "high availability", "scalability", "load balancing"),
    "testing": ("unit test", "unit tests", "unit testing", "integration test", "pytest", "junit", "tdd"),
    "react": ("react.js", "reactjs", "react"),
    "angular": ("angular",),
    "vue": ("vue.js", "vuejs", "vue"),
    "nodejs": ("node.js", "nodejs", "node js"),
    "django": ("django",),
    "flask": ("flask",),
    "fastapi": ("fastapi", "fast api"),
    "spring-boot": ("spring boot", "spring framework"),
    "security": ("oauth", "jwt", "authentication", "authorisation", "authorization"),
    "performance": ("performance tuning", "query tuning", "optimisation", "optimization", "latency", "throughput"),
    "concurrency": ("concurrency", "multithreading", "race condition", "deadlock"),
}

SKILL_LABELS: dict[str, str] = {
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "golang": "Go",
    "csharp": "C# and .NET",
    "cpp": "C++",
    "rust": "Rust",
    "scala": "Scala",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlserver": "SQL Server",
    "oracle": "Oracle",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "spark": "Apache Spark",
    "hadoop": "Hadoop",
    "kafka": "Kafka",
    "airflow": "Airflow",
    "dbt": "dbt",
    "snowflake": "Snowflake",
    "databricks": "Databricks",
    "bigquery": "BigQuery",
    "redshift": "Redshift",
    "flink": "Flink",
    "etl": "Data pipelines",
    "data-modelling": "Data modelling",
    "data-warehouse": "Data warehouse",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "ci-cd": "CI/CD",
    "linux": "Linux",
    "git": "Git",
    "rest-api": "REST APIs",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "system-design": "System design",
    "testing": "Testing",
    "react": "React",
    "angular": "Angular",
    "vue": "Vue",
    "nodejs": "Node.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring-boot": "Spring Boot",
    "security": "Security",
    "performance": "Performance",
    "concurrency": "Concurrency",
}

MAX_SKILLS = 8

# A form may end or start with punctuation (c#, c++, .net, ci/cd), so the usual \b does
# not work: the neighbours are checked directly instead.
_BEFORE = r"(?<![A-Za-z0-9_+#.])"
_AFTER = r"(?![A-Za-z0-9_+#])"


def label_of(skill: str) -> str:
    return SKILL_LABELS.get(skill, skill.replace("-", " "))


def _pattern_for(form: str) -> str:
    return _BEFORE + re.escape(form).replace(r"\ ", r"\s+") + _AFTER


@lru_cache(maxsize=1)
def _matcher() -> re.Pattern[str]:
    # Longest form first, so "sql server" wins over "sql" at the same position.
    forms = sorted(
        ((form, skill) for skill, group in SKILL_FORMS.items() for form in group),
        key=lambda item: -len(item[0]),
    )
    return re.compile("|".join(f"(?P<g{index}>{_pattern_for(form)})" for index, (form, _) in enumerate(forms)))


@lru_cache(maxsize=1)
def _skill_by_group() -> dict[str, str]:
    forms = sorted(
        ((form, skill) for skill, group in SKILL_FORMS.items() for form in group),
        key=lambda item: -len(item[0]),
    )
    return {f"g{index}": skill for index, (_, skill) in enumerate(forms)}


def find_skills(text: str, limit: int = MAX_SKILLS) -> list[str]:
    """The technologies named in *text*, in the order they first appear, without repeats."""
    if not text:
        return []
    by_group = _skill_by_group()
    found: list[str] = []
    for match in _matcher().finditer(text.lower()):
        skill = by_group[match.lastgroup]
        if skill not in found:
            found.append(skill)
            if len(found) >= limit:
                break
    return found


def known_skills(values: Iterable[str]) -> list[str]:
    """The values that name a skill in the vocabulary, deduplicated and in order."""
    kept: list[str] = []
    for value in values:
        skill = str(value).strip().lower()
        if skill in SKILL_FORMS and skill not in kept:
            kept.append(skill)
    return kept
