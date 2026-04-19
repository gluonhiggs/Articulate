"""
Oxford 5000 vocabulary data - loaded once at module level.
Source: backend/data/oxford_5000.csv (scraped from Oxford Learner's Dictionaries)

Three dicts built at import time:
  WORD_TO_CEFR    - word -> CEFR level str ("A1"…"C1")
  WORD_TO_DATA    - word -> {type, phon_n_am, definition, example}
  CEFR_TO_WORDS   - level -> [words]  (for future word-suggestion features)

US spelling aliases are applied at load time so American spellings
(color, favorite, organize…) resolve to the same entry as their
British headword.

Do NOT import this per-request - it is loaded once at module import time.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_CSV = Path(__file__).parent / "oxford_5000.csv"

# Common US->UK spelling aliases so American-spelled words hit the dict.
# Only entries whose UK form is actually in the Oxford 5000 take effect.
_US_TO_UK: Dict[str, str] = {
    # -our / -or
    "color": "colour",
    "honor": "honour",
    "favor": "favor",
    "behavior": "behaviour",
    "neighbour": "neighbor",
    "harbor": "harbour",
    "humor": "humour",
    "labor": "labour",
    "rumor": "rumour",
    "flavor": "flavour",
    "tumor": "tumour",
    "vapor": "vapour",
    "armor": "armour",
    "odor": "odour",
    # -ize / -ise
    "organize": "organise",
    "recognize": "recognise",
    "realize": "realise",
    "analyze": "analyse",
    "apologize": "apologise",
    "emphasize": "emphasise",
    "criticize": "criticise",
    "authorize": "authorise",
    "characterize": "characterise",
    "specialize": "specialise",
    "summarize": "summarise",
    "utilize": "utilise",
    "mobilize": "mobilise",
    "legalize": "legalise",
    "normalize": "normalise",
    "modernize": "modernise",
    "stabilize": "stabilise",
    "visualize": "visualise",
    "minimize": "minimise",
    "maximize": "maximise",
    "finalize": "finalise",
    "prioritize": "prioritise",
    "customize": "customise",
    "digitize": "digitise",
    "memorize": "memorise",
    # -er / -re
    "center": "centre",
    "theater": "theatre",
    "meter": "metre",
    "fiber": "fibre",
    "liter": "litre",
    "specter": "spectre",
    "somber": "sombre",
    "caliber": "calibre",
    # -se / -ce
    "defense": "defence",
    "offense": "offence",
    "license": "licence",
    "pretense": "pretence",
    # misc
    "program": "programme",
    "catalog": "catalogue",
    "dialog": "dialogue",
    "analog": "analogue",
    "check": "cheque",
    "tire": "tyre",
    "curb": "kerb",
    "gray": "grey",
    "jewelry": "jewellery",
    "mustache": "moustache",
    "plow": "plough",
    "draft": "draught",
    "favorite": "favourite",
    "aging": "ageing",
}

WORD_TO_CEFR: Dict[str, str] = {}
WORD_TO_DATA: Dict[str, dict] = {}
CEFR_TO_WORDS: Dict[str, List[str]] = {
    "A1": [],
    "A2": [],
    "B1": [],
    "B2": [],
    "C1": [],
}

_VALID_LEVELS = frozenset(CEFR_TO_WORDS)
_LEVEL_RANK = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4}

try:
    with open(_CSV, newline="", encoding="utf-8") as _f:
        for _row in csv.DictReader(_f):
            _word = _row["word"].strip().lower()
            _level = _row["cefr"].strip().upper()  # normalise to "A1"…"C1"
            if not _word or _level not in _VALID_LEVELS:
                continue
            # When the same word appears multiple times (different POS),
            # keep the lower CEFR level - most accessible usage wins for scoring.
            if _word in WORD_TO_CEFR:
                if _LEVEL_RANK[_level] >= _LEVEL_RANK[WORD_TO_CEFR[_word]]:
                    continue
                # Remove old entry from CEFR_TO_WORDS before overwriting
                _old_level = WORD_TO_CEFR[_word]
                try:
                    CEFR_TO_WORDS[_old_level].remove(_word)
                except ValueError:
                    pass
            WORD_TO_CEFR[_word] = _level
            WORD_TO_DATA[_word] = {
                "type": _row.get("type", "").strip(),
                "phon_n_am": _row.get("phon_n_am", "").strip(),
                "definition": _row.get("definition", "").strip(),
                "example": _row.get("example", "").strip(),
            }
            CEFR_TO_WORDS[_level].append(_word)

    # Apply US spelling aliases
    for _us, _uk in _US_TO_UK.items():
        if _uk in WORD_TO_CEFR and _us not in WORD_TO_CEFR:
            WORD_TO_CEFR[_us] = WORD_TO_CEFR[_uk]
            WORD_TO_DATA[_us] = WORD_TO_DATA[_uk]

    logger.debug("Oxford 5000 loaded: %d entries", len(WORD_TO_CEFR))

except FileNotFoundError:
    logger.error("oxford_5000.csv not found at %s - vocab scoring will be degraded", _CSV)
