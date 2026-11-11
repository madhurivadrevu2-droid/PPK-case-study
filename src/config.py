"""Shared paths and constants for the PPK proposal pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"
REPORTING = ROOT / "reporting"

EXTRACT_DATE = "2026-10-15"
YEARS = (2025, 2026)

# Statuses that close a proposal. Won/Lost are "decisions"; Withdrawn closes it without one.
DECISION_STATUSES = ("Won", "Lost")
CLOSED_STATUSES = ("Won", "Lost", "Withdrawn")

# Accepted date formats in proposals.submitted_date (slash dates verified as day-first).
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y")

PRACTICES = [
    "Consumer Products", "Customer Strategy & Marketing", "Digital", "Energy & Natural Resources",
    "Financial Services", "Healthcare", "Industrials", "M&A", "Performance Improvement",
    "Strategy", "Technology, Media & Telecom",
]

# Practice renamed on 2026-01-01; both labels are the same practice.
PRACTICE_ALIASES = {"customer": "Customer Strategy & Marketing"}

# Values below this are treated as entered in USD thousands; above the upper bound as a 1000x typo.
VALUE_THOUSANDS_BELOW = 10_000
VALUE_TYPO_ABOVE = 100_000_000

# Placeholder clients that mark test records.
TEST_CLIENT_PATTERN = r"(?i)test|dummy|demo"
