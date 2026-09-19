"""Sample interview pack data shared by the interview test modules."""

from __future__ import annotations

import copy
import json

PACK_UID = "5b0c1d52-3f4e-4c47-9a53-1c0d6f7e8a90"

SOURCE_CONTENT = (
    "Spark evaluates transformations lazily. Nothing runs until an action such as count or collect is called. "
    "A shuffle moves data between executors over the network and is expensive."
)

_SAMPLE_PACK = {
    "format": "articulate-interview-pack",
    "format_version": 1,
    "pack": {
        "id": PACK_UID,
        "title": "Data Engineer: Spark basics",
        "role": "de",
        "level": "mid",
        "version": 2,
        "author": "Coach",
        "job_description": "Build batch pipelines with Spark.",
    },
    "glossary": [
        {"term": "PySpark", "aliases": []},
        {"term": "PostgreSQL", "aliases": ["post gres"]},
    ],
    "sources": [
        {"id": "src-spark", "title": "Spark notes", "url": "https://spark.apache.org", "content": SOURCE_CONTENT}
    ],
    "questions": [
        {
            "id": "q-lazy",
            "topic": "Spark",
            "text": "What is lazy evaluation in Spark?",
            "answer_seconds": 90,
            "key_points": [
                {
                    "id": "kp-lazy-core",
                    "text": "Transformations are not executed until an action is called",
                    "weight": 3,
                    "source_quote": "Nothing runs until an action such as count or collect is called.",
                },
                {"id": "kp-lazy-dag", "text": "Spark builds a plan (DAG) it can optimize before running", "weight": 2},
                {
                    "id": "kp-lazy-example",
                    "text": "Actions such as count, collect or write trigger execution",
                    "weight": 1,
                    "source_quote": "Spark runs every line immediately.",
                },
            ],
            "misconceptions": [
                {
                    "id": "mc-lazy",
                    "text": "Every transformation runs immediately on the cluster",
                    "correction": "Transformations run only when an action is triggered.",
                }
            ],
            "follow_ups": [
                {
                    "id": "fu-dag",
                    "text": "How does the plan help Spark optimize a job?",
                    "answer_seconds": 60,
                    "trigger_key_point_id": "kp-lazy-dag",
                    "key_points": [
                        {"id": "kp-fu-dag", "text": "Narrow transformations are pipelined into one stage", "weight": 3}
                    ],
                },
                {
                    "id": "fu-cache",
                    "text": "When would you cache a DataFrame?",
                    "answer_seconds": 60,
                    "key_points": [
                        {
                            "id": "kp-fu-cache",
                            "text": "When the same DataFrame is reused by several actions",
                            "weight": 3,
                        }
                    ],
                },
            ],
        },
        {
            "id": "q-shuffle",
            "topic": "Performance",
            "text": "What is a shuffle and why is it expensive?",
            "key_points": [{"id": "kp-shuffle", "text": "Data moves between executors over the network", "weight": 3}],
        },
    ],
}


def sample_pack() -> dict:
    return copy.deepcopy(_SAMPLE_PACK)


def pack_bytes(pack: dict) -> bytes:
    return json.dumps(pack).encode("utf-8")
