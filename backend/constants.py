from __future__ import annotations

from pathlib import Path

# Scoring / rolling average
BAND_ROLLING_WINDOW = 10  # number of recent attempts for estimated_band average

# Dashboard
HEATMAP_DAYS = 180

# Prompt files directory (shared across scoring, ai_assist, improve services)
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Project root (two levels up from backend/constants.py)
PROJECT_ROOT = PROMPTS_DIR.parent.parent
