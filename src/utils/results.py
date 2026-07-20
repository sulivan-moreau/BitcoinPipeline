"""Sauvegarde du dernier resultat d'un collecteur (C1 : sauvegarde des resultats)."""

import json
from pathlib import Path

LOGS_DIR = Path("data/logs")


def save_last_result(source: str, results: list[dict]) -> None:
    """Ecrit le dernier resultat d'un collecteur dans data/logs/<source>_last_result.json.

    Complement a la persistance finale (src/persist.py, qui insere en base) :
    ce fichier garantit que chaque script d'extraction, execute seul, sauvegarde
    reellement son resultat a l'issue du traitement, comme l'exige le critere C1
    du referentiel ("la fin du traitement et la sauvegarde des resultats").
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"{source}_last_result.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
