"""Configuration centralisée de l'API : variables d'environnement.

Toutes les valeurs sensibles ou d'environnement (secret JWT, identifiants
admin) passent par ce module, jamais en dur dans le reste du code de l'API.
"""

import os

from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY manquante : définir la variable d'environnement (voir .env.example)")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
