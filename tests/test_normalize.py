"""Tests unitaires sur la validation des entrées (src/normalize.py, C3)."""

from src.normalize import is_valid_entry
from src.utils.logger import get_logger

logger = get_logger("test_normalize")


def test_entree_valide_est_acceptee():
    entry = {
        "source": "test_source",
        "price_usd": 64000.0,
        "timestamp": "2026-07-21T00:00:00Z",
        "collected_at": "2026-07-21T00:00:00Z",
    }
    assert is_valid_entry(entry, logger) is True


def test_prix_hors_bornes_est_rejete():
    entry = {
        "source": "test_source",
        "price_usd": 2_000_000,
        "timestamp": "2026-07-21T00:00:00Z",
        "collected_at": "2026-07-21T00:00:00Z",
    }
    assert is_valid_entry(entry, logger) is False
