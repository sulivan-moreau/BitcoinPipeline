# BitcoinPipeline — Registre et procédures RGPD (C4)

## Registre des traitements de données personnelles

| Traitement | Données concernées | Finalité | Base légale | Durée de conservation |
|---|---|---|---|---|
| Authentification API | Compte admin (table `users` : username, hashed_password) | Sécuriser l'accès en écriture/lecture à l'API BitcoinPipeline (C5) | Intérêt légitime (sécurité du service) | Durée de vie du projet pédagogique |

Aucune autre donnée personnelle n'est traitée par ce projet. Les prix
Bitcoin collectés (table `bitcoin_prices`) sont des données de marché
publiques, non nominatives, et ne constituent pas des données personnelles
au sens du RGPD.

## Principe général

Le volume de données personnelles traitées est minimal : un seul compte
administrateur (`ADMIN_USERNAME` défini via `.env`). Aucune procédure
automatisée n'est nécessaire vu ce volume ; un responsable technique
applique les procédures ci-dessous manuellement, sur demande ou de façon
périodique.

## Tableau des procédures de conformité

| Procédure | Mode | Fréquence | Traitement de conformité |
|---|---|---|---|
| Revue du compte admin | Manuelle | À chaque changement de contexte projet | Vérifier que le compte `users` correspond toujours à un administrateur actif |
| Suppression du compte admin | Manuelle | Sur demande (fin de projet, exercice de droit) | Voir Procédure 1 |
| Rotation du secret JWT | Manuelle | En cas de doute sur une fuite | Régénérer `JWT_SECRET_KEY` dans `.env`, redémarrer l'API — invalide tous les tokens en cours |
| Purge de l'historique de prix | Manuelle | Optionnelle | Les prix ne sont pas des données personnelles, mais peuvent être purgés pour limiter le volume de la table `bitcoin_prices` |

## Procédure 1 — Suppression du compte administrateur

```sql
-- Identifier le compte
SELECT id, username, created_at FROM users;

-- Supprimer le compte
DELETE FROM users WHERE username = 'nom_admin';

-- Vérifier la suppression
SELECT * FROM users WHERE username = 'nom_admin';
-- Résultat attendu : 0 lignes
```

Délai de traitement : immédiat.

## Procédure 2 — Rotation du secret JWT

```bash
# 1. Générer un nouveau secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# 2. Mettre à jour .env
JWT_SECRET_KEY=nouveau_secret

# 3. Redémarrer l'API
```

Note : tous les tokens existants sont invalidés immédiatement après rotation.

## Procédure 3 — Réinitialisation complète

```bash
docker compose down -v
rm -rf data/raw/* data/processed/*
```

Supprime les volumes PostgreSQL (y compris le compte admin) et les données
collectées localement. Aucune donnée personnelle n'est conservée en dehors
des volumes Docker.
