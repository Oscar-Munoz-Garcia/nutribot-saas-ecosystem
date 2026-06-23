"""
services/food_api.py — Puente con APIs de nutrición externas.

Funciones:
  - obtener_receta()    → Spoonacular: sugerencia de receta personalizada
  - escanear_codigo()   → Open Food Facts: análisis de producto por código de barras

Todas las funciones manejan errores de red y devuelven siempre un string
formateado listo para enviarse como mensaje de Telegram.
"""

import requests
from config import SPOONACULAR_API_KEY, SPOONACULAR_BASE_URL, OPEN_FOOD_FACTS_URL


# ──────────────────────────────────────────────────────────────────────────────
# MAPEOS DE TRADUCCIÓN PARA LA API
# ──────────────────────────────────────────────────────────────────────────────

# Conversión de dieta en español al parámetro que acepta Spoonacular
_DIETA_MAP = {
    "vegetariano": "vegetarian",
    "vegano":      "vegan",
    "omnivoro":    "",           # Sin filtro de dieta especial
}

# Conversión de objetivo al rango calórico aproximado por comida
_OBJETIVO_CALORIAS = {
    "perder grasa":   {"minCalories": 300, "maxCalories": 550},
    "ganar musculo":  {"minCalories": 600, "maxCalories": 900},
    "mantener":       {"minCalories": 450, "maxCalories": 700},
}

# Tipos de comida reconocidos por Spoonacular
_TIPO_COMIDA_MAP = {
    "desayuno":  "breakfast",
    "almuerzo":  "main course",
    "cena":      "main course",
    "snack":     "snack",
}


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIÓN: OBTENER RECETA
# ──────────────────────────────────────────────────────────────────────────────

def obtener_receta(dieta: str, objetivo: str, tipo_comida: str = "almuerzo") -> str:
    """
    Consulta Spoonacular y devuelve una receta personalizada.

    Parámetros:
        dieta       → 'omnivoro' | 'vegetariano' | 'vegano'
        objetivo    → 'perder grasa' | 'ganar musculo' | 'mantener'
        tipo_comida → 'desayuno' | 'almuerzo' | 'cena' | 'snack'

    Devuelve un string formateado con título, macros y tiempo de preparación.
    """
    # ── Construir parámetros de la petición ───────────────────────────────────
    params = {
        "apiKey":   SPOONACULAR_API_KEY,
        "number":   1,                          # Solo 1 resultado
        "addRecipeNutrition": True,
        "type":     _TIPO_COMIDA_MAP.get(tipo_comida, "main course"),
        "sort":     "random",
        "fillIngredients": False,
        **_OBJETIVO_CALORIAS.get(objetivo, {"minCalories": 400, "maxCalories": 700}),
    }

    dieta_api = _DIETA_MAP.get(dieta, "")
    if dieta_api:
        params["diet"] = dieta_api

    # ── Petición HTTP con timeout y manejo de errores ─────────────────────────
    try:
        response = requests.get(SPOONACULAR_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        resultados = data.get("results", [])
        if not resultados:
            return (
                "🍽️ No encontré recetas con tus filtros exactos ahora mismo.\n"
                "Prueba con /quecomo en un momento o ajusta tus preferencias."
            )

        receta = resultados[0]
        nombre  = receta.get("title", "Receta sin nombre")
        tiempo  = receta.get("readyInMinutes", "?")
        url     = receta.get("sourceUrl", "")

        # Extraer macros del objeto de nutrición
        nutrientes = {
            n["name"]: round(n["amount"], 1)
            for n in receta.get("nutrition", {}).get("nutrients", [])
            if n["name"] in ("Calories", "Protein", "Carbohydrates", "Fat")
        }

        calorias    = nutrientes.get("Calories", "?")
        proteina    = nutrientes.get("Protein", "?")
        carbos      = nutrientes.get("Carbohydrates", "?")
        grasas      = nutrientes.get("Fat", "?")

        return (
            f"🍽️ *Sugerencia para tu {tipo_comida}*\n\n"
            f"📌 *{nombre}*\n"
            f"⏱️ Preparación: {tiempo} minutos\n\n"
            f"📊 *Macronutrientes por porción:*\n"
            f"  🔥 Calorías: {calorias} kcal\n"
            f"  💪 Proteína: {proteina} g\n"
            f"  🍞 Carbohidratos: {carbos} g\n"
            f"  🥑 Grasas: {grasas} g\n\n"
            f"🔗 [Ver receta completa]({url})"
        )

    except requests.exceptions.Timeout:
        return "⏳ La API de recetas tardó demasiado. Intenta de nuevo en un momento."

    except requests.exceptions.ConnectionError:
        return "🌐 Sin conexión a internet. Verifica tu red y vuelve a intentarlo."

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 402:
            # Quota agotada en el plan gratuito de Spoonacular
            return _receta_fallback(dieta, objetivo, tipo_comida)
        return f"❌ Error al consultar recetas (HTTP {e.response.status_code if e.response else '?'})."

    except Exception as e:
        return f"❌ Error inesperado al obtener receta: {str(e)}"


def _receta_fallback(dieta: str, objetivo: str, tipo_comida: str) -> str:
    """
    Devuelve una receta hardcoded cuando la API no está disponible.
    Garantiza que el bot siempre responda algo útil.
    """
    recetas_fallback = {
        ("omnivoro", "perder grasa", "almuerzo"): (
            "Pechuga de pollo a la plancha con ensalada verde",
            "~420 kcal | 45g proteína | 15g carbs | 12g grasa"
        ),
        ("vegetariano", "perder grasa", "almuerzo"): (
            "Bowl de quinoa con garbanzos y verduras asadas",
            "~380 kcal | 18g proteína | 52g carbs | 9g grasa"
        ),
        ("vegano", "ganar musculo", "almuerzo"): (
            "Lentejas rojas con arroz integral y aguacate",
            "~680 kcal | 28g proteína | 88g carbs | 18g grasa"
        ),
    }

    clave = (dieta, objetivo, tipo_comida)
    titulo, macros = recetas_fallback.get(
        clave,
        ("Arroz integral con verduras salteadas", "~450 kcal | 12g proteína | 75g carbs | 10g grasa")
    )

    return (
        f"🍽️ *Sugerencia para tu {tipo_comida}* _(modo offline)_\n\n"
        f"📌 *{titulo}*\n\n"
        f"📊 {macros}\n\n"
        f"_💡 Tip: La API de recetas está temporalmente limitada. "
        f"Esta sugerencia es parte de tu perfil guardado._"
    )


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIÓN: ESCANEAR CÓDIGO DE BARRAS
# ──────────────────────────────────────────────────────────────────────────────

def escanear_codigo(codigo_barras: str) -> str:
    """
    Consulta Open Food Facts con un código de barras y devuelve un análisis
    del producto: ingredientes, grado NOVA de procesamiento y alertas de azúcar.

    Open Food Facts es una API abierta, no requiere API key.

    Parámetro:
        codigo_barras → string numérico, ej. '3017624010701' (Nutella)
    """
    url = OPEN_FOOD_FACTS_URL.format(barcode=codigo_barras)

    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "NutriBot/1.0"})
        response.raise_for_status()
        data = response.json()

        # Open Food Facts devuelve status=0 si el producto no existe
        if data.get("status") == 0:
            return (
                f"❓ Producto con código *{codigo_barras}* no encontrado en Open Food Facts.\n"
                "Puedes contribuir añadiéndolo en https://world.openfoodfacts.org"
            )

        producto = data.get("product", {})
        nombre   = producto.get("product_name", "Producto sin nombre")
        marca    = producto.get("brands", "Marca desconocida")

        # ── Grado NOVA (1=mínimo procesado, 4=ultraprocesado) ────────────────
        nova = producto.get("nova_group")
        nova_desc = {
            1: "✅ Mínimamente procesado",
            2: "🟡 Ingrediente culinario procesado",
            3: "🟠 Procesado",
            4: "🔴 Ultraprocesado — consumo ocasional recomendado",
        }.get(nova, "❓ Sin clasificar")

        # ── Información nutricional por 100g ─────────────────────────────────
        nutriments = producto.get("nutriments", {})
        calorias   = nutriments.get("energy-kcal_100g", "?")
        azucares   = nutriments.get("sugars_100g", "?")
        grasas_sat = nutriments.get("saturated-fat_100g", "?")
        sal        = nutriments.get("salt_100g", "?")

        # ── Alertas de azúcar ─────────────────────────────────────────────────
        alerta_azucar = ""
        if isinstance(azucares, (int, float)):
            if azucares > 22.5:
                alerta_azucar = "⚠️ *ALTO en azúcar* (>22.5g/100g)"
            elif azucares > 5:
                alerta_azucar = "🟡 Azúcar moderada"
            else:
                alerta_azucar = "✅ Azúcar baja"

        # ── Ingredientes (primeros 200 caracteres para no saturar el chat) ────
        ingredientes_raw = producto.get("ingredients_text", "No disponibles")
        ingredientes = (ingredientes_raw[:200] + "...") if len(ingredientes_raw) > 200 else ingredientes_raw

        # ── Nutri-Score ───────────────────────────────────────────────────────
        nutriscore = producto.get("nutriscore_grade", "").upper()
        nutriscore_str = f"Nutri-Score: *{nutriscore}*" if nutriscore else "Nutri-Score: no disponible"

        return (
            f"🔍 *Análisis del producto*\n\n"
            f"📦 *{nombre}* — {marca}\n\n"
            f"🏭 Procesamiento NOVA: {nova_desc}\n"
            f"{nutriscore_str}\n\n"
            f"📊 *Nutrición por 100g:*\n"
            f"  🔥 Calorías: {calorias} kcal\n"
            f"  🍬 Azúcares: {azucares}g  {alerta_azucar}\n"
            f"  🧈 Grasas saturadas: {grasas_sat}g\n"
            f"  🧂 Sal: {sal}g\n\n"
            f"🧾 *Ingredientes:*\n_{ingredientes}_"
        )

    except requests.exceptions.Timeout:
        return "⏳ Open Food Facts tardó demasiado en responder. Inténtalo de nuevo."

    except requests.exceptions.ConnectionError:
        return "🌐 Sin conexión a internet para consultar el código de barras."

    except requests.exceptions.HTTPError as e:
        return f"❌ Error al consultar el producto (HTTP {e.response.status_code if e.response else '?'})."

    except Exception as e:
        return f"❌ Error inesperado al escanear código: {str(e)}"
