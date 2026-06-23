"""
config.py — Configuración central del ecosistema NutriBot.

Lee credenciales desde variables de entorno para producción.
Si no las encuentra, usa valores por defecto seguros para testing local.

Uso en producción (Linux/Mac):
    export TELEGRAM_TOKEN="tu_token_real"
    export SPOONACULAR_KEY="tu_api_key"

Uso en producción (Windows CMD):
    set TELEGRAM_TOKEN=tu_token_real
"""

import os

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.environ.get(
    "TELEGRAM_TOKEN",
    "TU_TOKEN_AQUI_PARA_TESTING"   # Reemplazar antes de ejecutar
)

# ─────────────────────────────────────────────
# SPOONACULAR (recetas e información nutricional)
# Registro gratuito: https://spoonacular.com/food-api
# ─────────────────────────────────────────────
SPOONACULAR_API_KEY: str = os.environ.get(
    "SPOONACULAR_KEY",
    "TU_SPOONACULAR_KEY_AQUI"
)
SPOONACULAR_BASE_URL: str = "https://api.spoonacular.com/recipes/complexSearch"

# ─────────────────────────────────────────────
# OPEN FOOD FACTS (código de barras, sin API key requerida)
# ─────────────────────────────────────────────
OPEN_FOOD_FACTS_URL: str = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────
DB_PATH: str = os.environ.get("DB_PATH", "nutricion.db")

# ─────────────────────────────────────────────
# PATHS LOCALES
# ─────────────────────────────────────────────
PHOTOS_DIR: str = "fotos_comida"

# ─────────────────────────────────────────────
# SCHEDULER — Horarios por defecto (formato 24h, hora local del servidor)
# ─────────────────────────────────────────────
MORNING_HOUR: int = 8
MORNING_MINUTE: int = 0

EVENING_HOUR: int = 21
EVENING_MINUTE: int = 30

# ─────────────────────────────────────────────
# ONBOARDING — Número total de pasos del cuestionario inicial
# ─────────────────────────────────────────────
TOTAL_ONBOARDING_STEPS: int = 6
