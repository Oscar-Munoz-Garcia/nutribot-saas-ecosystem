"""
bot.py — Núcleo del ecosistema NutriBot.

Inicializa el bot de Telegram e implementa:
  - Máquina de estados para el onboarding (6 pasos con Inline Keyboards)
  - Handlers de mensajes: peso diario (float), fotos de comida
  - Comandos de asistente: /quecomo, /progreso, /dieta
  - Callbacks de botones: adherencia, lugar, entrenamiento mañana

Arquitectura: sin LLMs, 100% determinista y basada en eventos.
"""

import os
import logging
import telebot
from telebot import types
from datetime import datetime

import database as db
import scheduler_jobs as sched
from services.food_api import obtener_receta, escanear_codigo
from config import TELEGRAM_TOKEN, PHOTOS_DIR, TOTAL_ONBOARDING_STEPS

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")

# Asegurar que existe la carpeta de fotos
os.makedirs(PHOTOS_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS DE TECLADOS
# ──────────────────────────────────────────────────────────────────────────────

def _kb_objetivo() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔥 Perder grasa",   callback_data="obj_perder grasa"))
    kb.row(types.InlineKeyboardButton("💪 Ganar músculo",  callback_data="obj_ganar musculo"))
    kb.row(types.InlineKeyboardButton("⚖️ Mantener peso",  callback_data="obj_mantener"))
    return kb

def _kb_actividad() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🛋️ Sedentario (0-1 días/semana)",   callback_data="act_sedentario"))
    kb.row(types.InlineKeyboardButton("🚶 Moderado (2-4 días/semana)",      callback_data="act_moderado"))
    kb.row(types.InlineKeyboardButton("🏋️ Activo (5+ días/semana)",         callback_data="act_activo"))
    return kb

def _kb_dieta() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🥩 Omnívoro",    callback_data="dieta_omnivoro"),
        types.InlineKeyboardButton("🥦 Vegetariano", callback_data="dieta_vegetariano"),
        types.InlineKeyboardButton("🌱 Vegano",      callback_data="dieta_vegano"),
    )
    return kb

def _kb_comidas() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("2", callback_data="comidas_2"),
        types.InlineKeyboardButton("3", callback_data="comidas_3"),
        types.InlineKeyboardButton("4", callback_data="comidas_4"),
        types.InlineKeyboardButton("5", callback_data="comidas_5"),
    )
    return kb

def _kb_hora_cena() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("19:00", callback_data="cena_19:00"),
        types.InlineKeyboardButton("20:00", callback_data="cena_20:00"),
        types.InlineKeyboardButton("21:00", callback_data="cena_21:00"),
    )
    kb.row(
        types.InlineKeyboardButton("21:30", callback_data="cena_21:30"),
        types.InlineKeyboardButton("22:00", callback_data="cena_22:00"),
        types.InlineKeyboardButton("22:30", callback_data="cena_22:30"),
    )
    return kb

def _kb_cumplio_dieta() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Sí, la cumplí",   callback_data="dieta_cumplio_1"),
        types.InlineKeyboardButton("⚠️ Parcialmente",    callback_data="dieta_cumplio_2"),
        types.InlineKeyboardButton("❌ No la cumplí",    callback_data="dieta_cumplio_0"),
    )
    return kb

def _kb_lugar_comida() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🏠 Casa",         callback_data="lugar_Casa"),
        types.InlineKeyboardButton("🏢 Oficina",      callback_data="lugar_Oficina"),
        types.InlineKeyboardButton("🍽️ Restaurante",  callback_data="lugar_Restaurante"),
    )
    return kb

def _kb_tipo_comida() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("☀️ Desayuno",  callback_data="quecomo_desayuno"),
        types.InlineKeyboardButton("🥗 Almuerzo",  callback_data="quecomo_almuerzo"),
    )
    kb.row(
        types.InlineKeyboardButton("🌙 Cena",      callback_data="quecomo_cena"),
        types.InlineKeyboardButton("🍎 Snack",     callback_data="quecomo_snack"),
    )
    return kb
def _kb_tipo_entreno() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("💪 Fuerza",    callback_data="entreno_fuerza"),
        types.InlineKeyboardButton("🏃 Cardio",    callback_data="entreno_cardio"),
    )
    kb.row(
        types.InlineKeyboardButton("🧘 Movilidad", callback_data="entreno_movilidad"),
        types.InlineKeyboardButton("🏊 Otro",      callback_data="entreno_otro"),
    )
    return kb

def _kb_duracion_entreno() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("30 min", callback_data="duracion_30"),
        types.InlineKeyboardButton("45 min", callback_data="duracion_45"),
        types.InlineKeyboardButton("60 min", callback_data="duracion_60"),
        types.InlineKeyboardButton("90 min", callback_data="duracion_90"),
    )
    return kb

# ──────────────────────────────────────────────────────────────────────────────
# MÁQUINA DE ESTADOS — ONBOARDING
# ──────────────────────────────────────────────────────────────────────────────

def _enviar_pregunta_onboarding(chat_id: int, paso: int, msg_id: int = None) -> None:
    """
    Envía la pregunta correspondiente al paso actual del onboarding.
    Si msg_id está presente, edita el mensaje anterior para mantener el chat limpio.
    """
    preguntas = {
        1: ("🎯 ¿Cuál es tu *objetivo principal*?",                           _kb_objetivo()),
        2: ("🏃 ¿Cuál es tu nivel de *actividad física* semanal?",            _kb_actividad()),
        3: ("🥗 ¿Qué tipo de *dieta* sigues?",                                _kb_dieta()),
        4: ("🍽️ ¿Cuántas *comidas al día* sueles hacer?",                     _kb_comidas()),
        5: ("🕘 ¿A qué hora sueles cenar?",                                   _kb_hora_cena()),
        6: ("⚠️ ¿Tienes alguna *intolerancia alimentaria*?\n\n"
            "Escríbelas separadas por coma (ej: `lactosa, gluten`) "
            "o escribe *ninguna* si no tienes.", None),
    }

    if paso not in preguntas:
        return

    texto, teclado = preguntas[paso]

    if msg_id and teclado:
        # Editar mensaje anterior (sin scroll de chat)
        try:
            bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=texto, reply_markup=teclado, parse_mode="Markdown"
            )
        except Exception:
            bot.send_message(chat_id, texto, reply_markup=teclado, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, texto, reply_markup=teclado, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# COMANDO /start
# ──────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message) -> None:
    chat_id = message.chat.id
    nombre  = message.from_user.first_name or "usuario"
    usuario = db.obtener_usuario(chat_id)

    if usuario is None:
        # Usuario nuevo: crear perfil e iniciar onboarding
        db.crear_usuario(chat_id, nombre)
        bot.send_message(
            chat_id,
            f"👋 ¡Hola, *{nombre}*! Bienvenido/a a *NutriBot*.\n\n"
            f"Soy tu asistente de nutrición 24/7. Voy a hacerte "
            f"*{TOTAL_ONBOARDING_STEPS} preguntas rápidas* para personalizar tu experiencia.\n\n"
            f"_Puedes responder en cualquier momento — guardamos tu progreso._",
        )
        db.avanzar_paso_onboarding(chat_id)   # paso 0 → 1
        _enviar_pregunta_onboarding(chat_id, 1)

    elif usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        # Onboarding incompleto: retomar donde lo dejó
        paso_actual = usuario["paso_onboarding"]
        bot.send_message(
            chat_id,
            f"👋 ¡Hola de nuevo, *{nombre}*! Continuemos el registro donde lo dejaste:",
        )
        _enviar_pregunta_onboarding(chat_id, paso_actual)

    else:
        # Usuario ya registrado
        bot.send_message(
            chat_id,
            f"✅ ¡Hola de nuevo, *{nombre}*! Ya tienes tu perfil configurado.\n\n"
            f"*Comandos disponibles:*\n"
            f"  /quecomo — Sugerencia de receta personalizada\n"
            f"  /progreso — Tu evolución de la última semana\n"
            f"  /dieta — Ver tu menú según tu perfil\n\n"
            f"_También puedes enviarme tu peso (ej: `74.5`) o una foto de tu comida._"
        )


# ──────────────────────────────────────────────────────────────────────────────
# CALLBACKS — ONBOARDING Y BOTONES GENERALES
# ──────────────────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery) -> None:
    """Centraliza todos los callbacks de Inline Keyboards."""
    chat_id = call.message.chat.id
    msg_id  = call.message.message_id
    data    = call.data

    # Responder al callback para eliminar el "reloj de carga" del botón
    bot.answer_callback_query(call.id)

    # ── ONBOARDING ────────────────────────────────────────────────────────────

    if data.startswith("obj_"):
        objetivo = data.replace("obj_", "")
        db.actualizar_campo_usuario(chat_id, "objetivo", objetivo)
        db.avanzar_paso_onboarding(chat_id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ Objetivo guardado: *{objetivo}*", parse_mode="Markdown"
        )
        _enviar_pregunta_onboarding(chat_id, 2)
    
    elif data.startswith("entreno_"):
        tipo = data.replace("entreno_", "")
        etiquetas = {
            "fuerza": "💪 Fuerza", "cardio": "🏃 Cardio",
            "movilidad": "🧘 Movilidad", "otro": "🏊 Otro"
        }
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"Tipo: *{etiquetas[tipo]}*\n\n¿Cuánto tiempo entrenaste?",
            reply_markup=_kb_duracion_entreno(),
            parse_mode="Markdown"
        )

    elif data.startswith("duracion_"):
        minutos = data.replace("duracion_", "")
        db.registrar_entrenamiento_hoy(chat_id, 1)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ *Entrenamiento registrado*\n\n"
                 f"⏱️ Duración: {minutos} minutos\n\n"
                 f"_¡Buen trabajo! Sigue así._",
            parse_mode="Markdown"
        )

    elif data.startswith("act_"):
        actividad = data.replace("act_", "")
        db.actualizar_campo_usuario(chat_id, "actividad", actividad)
        db.avanzar_paso_onboarding(chat_id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ Actividad guardada: *{actividad}*", parse_mode="Markdown"
        )
        _enviar_pregunta_onboarding(chat_id, 3)

    elif data.startswith("dieta_") and not data.startswith("dieta_cumplio"):
        dieta = data.replace("dieta_", "")
        db.actualizar_campo_usuario(chat_id, "dieta_tipo", dieta)
        db.avanzar_paso_onboarding(chat_id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ Dieta guardada: *{dieta}*", parse_mode="Markdown"
        )
        _enviar_pregunta_onboarding(chat_id, 4)

    elif data.startswith("comidas_"):
        comidas = int(data.replace("comidas_", ""))
        db.actualizar_campo_usuario(chat_id, "comidas_al_dia", comidas)
        db.avanzar_paso_onboarding(chat_id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ {comidas} comidas al día registradas.", parse_mode="Markdown"
        )
        _enviar_pregunta_onboarding(chat_id, 5)

    elif data.startswith("cena_"):
        hora = data.replace("cena_", "")
        db.actualizar_campo_usuario(chat_id, "hora_cena", hora)
        db.avanzar_paso_onboarding(chat_id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ Hora de cena: *{hora}*", parse_mode="Markdown"
        )
        _enviar_pregunta_onboarding(chat_id, 6)

    # ── ADHERENCIA A LA DIETA (tras enviar foto) ──────────────────────────────

    elif data.startswith("dieta_cumplio_"):
        cumplio = int(data.replace("dieta_cumplio_", ""))
        etiqueta = {0: "❌ No cumplida", 1: "✅ Cumplida", 2: "⚠️ Parcial"}[cumplio]

        # Guardar adherencia y pedir lugar de comida
        db.registrar_adherencia(chat_id, cumplio, "Pendiente")
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"Adherencia: *{etiqueta}*\n\n¿Dónde comiste hoy?",
            reply_markup=_kb_lugar_comida(),
            parse_mode="Markdown"
        )

    elif data.startswith("lugar_"):
        lugar = data.replace("lugar_", "")
        # Actualizar solo el lugar (la adherencia ya estaba guardada)
        registro = db.obtener_o_crear_registro_hoy(chat_id)
        db.registrar_adherencia(chat_id, registro["cumplio_dieta"] or 0, lugar)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"📍 Lugar guardado: *{lugar}*\n\n"
                 f"¡Registro del día actualizado correctamente! 🎯",
            parse_mode="Markdown"
        )

    # ── ENTRENAMIENTO MAÑANA (scheduler noche) ────────────────────────────────

    elif data.startswith("entrena_manana_"):
        valor   = int(data.replace("entrena_manana_", ""))
        texto   = "💪 ¡Perfecto! Mañana te recuerdo el entrenamiento." if valor == 1 \
                  else "🛌 Entendido, mañana es día de descanso activo."
        db.registrar_entrenamiento_manana(chat_id, valor)
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=texto, parse_mode="Markdown"
        )

    # ── SELECTOR DE COMIDA PARA /quecomo ─────────────────────────────────────

    elif data.startswith("quecomo_"):
        tipo_comida = data.replace("quecomo_", "")
        usuario = db.obtener_usuario(chat_id)

        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text="🔍 Buscando una receta perfecta para ti...",
            parse_mode="Markdown"
        )

        receta = obtener_receta(
            dieta=usuario["dieta_tipo"] or "omnivoro",
            objetivo=usuario["objetivo"] or "mantener",
            tipo_comida=tipo_comida
        )

        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=receta, parse_mode="Markdown",
            disable_web_page_preview=True
        )


# ──────────────────────────────────────────────────────────────────────────────
# HANDLER: TEXTO — PESO DIARIO E INTOLERANCIAS
# ──────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: not m.text.startswith('/'), content_types=["text"])
def handler_texto(message: types.Message) -> None:
    chat_id = message.chat.id
    texto   = message.text.strip()
    usuario = db.obtener_usuario(chat_id)

    # ── Si el usuario no existe, invitarle a registrarse ─────────────────────
    if usuario is None:
        bot.reply_to(message, "👋 Usa /start para registrarte y comenzar.")
        return

    paso = usuario["paso_onboarding"]

    # ── Paso 6 del onboarding: respuesta de texto para intolerancias ──────────
    if paso == 6:
        intolerancias = "ninguna" if texto.lower() == "ninguna" else texto.lower()
        db.actualizar_campo_usuario(chat_id, "intolerancias", intolerancias)
        db.avanzar_paso_onboarding(chat_id)   # paso 6 → 7 (completo)

        bot.send_message(
            chat_id,
            f"✅ Intolerancias registradas: *{intolerancias}*\n\n"
            f"🎉 ¡Tu perfil está *100% configurado*!\n\n"
            f"A partir de ahora recibirás:\n"
            f"  ☀️ Recordatorios de peso cada mañana\n"
            f"  🌙 Check-in nocturno de entrenamiento\n\n"
            f"*Comandos disponibles:*\n"
            f"  /quecomo — Receta personalizada\n"
            f"  /progreso — Evolución semanal\n"
            f"  /dieta — Tu menú asignado",
            parse_mode="Markdown"
        )
        return

    # ── Onboarding no completado: guiar al usuario ───────────────────────────
    if paso < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Por favor, completa el registro primero usando los botones de arriba. 👆")
        return

    # ── Registro de peso: número flotante ────────────────────────────────────
    try:
        peso = float(texto.replace(",", "."))   # acepta coma decimal también
        if 20.0 <= peso <= 300.0:               # rango fisiológicamente razonable
            db.registrar_peso(chat_id, peso)
            hora_actual = datetime.now().strftime("%H:%M")
            bot.reply_to(
                message,
                f"⚖️ ¡Peso registrado! *{peso} kg* a las {hora_actual}.\n\n"
                f"_Sigue así, la constancia es la clave._",
                parse_mode="Markdown"
            )
        else:
            bot.reply_to(message, "⚠️ El peso debe estar entre 20 y 300 kg. ¿Es correcto ese valor?")
        return
    except ValueError:
        pass  # No es un número, continuar con otros handlers

    # ── Código de barras: cadena numérica de 8-13 dígitos ────────────────────
    if texto.isdigit() and 8 <= len(texto) <= 13:
        bot.reply_to(message, "🔍 Consultando Open Food Facts...")
        resultado = escanear_codigo(texto)
        bot.send_message(chat_id, resultado, parse_mode="Markdown", disable_web_page_preview=True)
        return

    # ── Mensaje no reconocido ─────────────────────────────────────────────────
    bot.reply_to(
        message,
        "🤖 No entendí ese mensaje.\n\n"
        "Puedes:\n"
        "  • Enviar tu peso (ej: *74.5*)\n"
        "  • Enviar un código de barras (ej: *3017624010701*)\n"
        "  • Usar /quecomo, /progreso o /dieta",
        parse_mode="Markdown"
    )


# ──────────────────────────────────────────────────────────────────────────────
# HANDLER: FOTOS DE COMIDA
# ──────────────────────────────────────────────────────────────────────────────

@bot.message_handler(content_types=["photo"])
def handler_foto(message: types.Message) -> None:
    chat_id = message.chat.id
    usuario = db.obtener_usuario(chat_id)

    if usuario is None or usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Completa el registro con /start antes de enviar fotos.")
        return

    # Descargar la foto en mayor resolución disponible
    foto_info   = message.photo[-1]
    file_info   = bot.get_file(foto_info.file_id)
    file_bytes  = bot.download_file(file_info.file_path)

    # Guardar localmente con timestamp para evitar colisiones
    from datetime import datetime as dt
    timestamp  = dt.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{PHOTOS_DIR}/{chat_id}_{timestamp}.jpg"

    with open(nombre_archivo, "wb") as f:
        f.write(file_bytes)

    # Guardar la ruta en la BD
    db.registrar_foto(chat_id, nombre_archivo)

    # Preguntar si cumplió la dieta
    bot.reply_to(
        message,
        "📸 ¡Foto guardada! Ahora dime...\n\n*¿Cumpliste la dieta hoy?*",
        reply_markup=_kb_cumplio_dieta(),
        parse_mode="Markdown"
    )


# ──────────────────────────────────────────────────────────────────────────────
# COMANDOS DE ASISTENTE 24/7
# ──────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["quecomo"])
def cmd_quecomo(message: types.Message) -> None:
    """Sugiere una receta personalizada según el perfil del usuario."""
    chat_id = message.chat.id
    usuario = db.obtener_usuario(chat_id)

    if usuario is None or usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Primero completa tu registro con /start 🙂")
        return

    bot.send_message(
        chat_id,
        "🍽️ ¿Para qué comida quieres una sugerencia?",
        reply_markup=_kb_tipo_comida()
    )


@bot.message_handler(commands=["progreso"])
def cmd_progreso(message: types.Message) -> None:
    """Genera un reporte de progreso de la última semana."""
    chat_id = message.chat.id
    usuario = db.obtener_usuario(chat_id)

    if usuario is None or usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Primero completa tu registro con /start 🙂")
        return

    registros = db.obtener_ultimos_registros(chat_id, dias=7)

    if not registros:
        bot.reply_to(message, "📭 Aún no tienes registros esta semana. Empieza enviando tu peso hoy.")
        return

    # ── Calcular métricas ─────────────────────────────────────────────────────
    pesos   = [r["peso"] for r in registros if r["peso"] is not None]
    dietas  = [r["cumplio_dieta"] for r in registros if r["cumplio_dieta"] is not None]

    peso_inicial = pesos[-1] if pesos else None   # más antiguo
    peso_actual  = pesos[0]  if pesos else None   # más reciente
    diferencia   = round(peso_actual - peso_inicial, 2) if (peso_inicial and peso_actual) else None

    dias_con_dieta   = sum(1 for d in dietas if d == 1)
    dias_parcial     = sum(1 for d in dietas if d == 2)
    total_dias       = len(dietas)
    adherencia_pct   = round(((dias_con_dieta + dias_parcial * 0.5) / total_dias) * 100, 1) if total_dias else 0

    # ── Construir reporte de texto ────────────────────────────────────────────
    tendencia = ""
    if diferencia is not None:
        if diferencia < 0:
            tendencia = f"📉 Has bajado *{abs(diferencia)} kg* esta semana. ¡Excelente!"
        elif diferencia > 0:
            tendencia = f"📈 Has subido *{diferencia} kg*. Revisa con tu nutricionista."
        else:
            tendencia = "⚖️ Tu peso se ha mantenido estable."

    reporte = (
        f"📊 *Tu progreso — últimos 7 días*\n\n"
    )

    if peso_actual:
        reporte += f"⚖️ Peso actual: *{peso_actual} kg*\n"
    if tendencia:
        reporte += f"{tendencia}\n"

    reporte += (
        f"\n🥗 *Adherencia a la dieta:* {adherencia_pct}%\n"
        f"  ✅ Días cumplidos: {dias_con_dieta}/{total_dias}\n"
        f"  ⚠️ Días parciales: {dias_parcial}/{total_dias}\n"
    )

    # Desglose por lugar de comida
    lugares = {}
    for r in registros:
        if r["lugar_comida"] and r["lugar_comida"] != "Pendiente":
            lugares[r["lugar_comida"]] = lugares.get(r["lugar_comida"], 0) + 1

    if lugares:
        reporte += "\n📍 *Dónde comiste más:*\n"
        for lugar, count in sorted(lugares.items(), key=lambda x: x[1], reverse=True):
            reporte += f"  • {lugar}: {count} día(s)\n"

    reporte += "\n_💡 Tip: Comparte estos datos con tu nutricionista._"

    bot.reply_to(message, reporte, parse_mode="Markdown")


@bot.message_handler(commands=["dieta"])
def cmd_dieta(message: types.Message) -> None:
    """Muestra un menú tipo basado en el perfil del usuario."""
    chat_id = message.chat.id
    usuario = db.obtener_usuario(chat_id)

    if usuario is None or usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Primero completa tu registro con /start 🙂")
        return

    objetivo  = usuario["objetivo"]  or "mantener"
    dieta     = usuario["dieta_tipo"] or "omnivoro"
    comidas   = usuario["comidas_al_dia"] or 3
    nombre    = usuario["nombre"] or "usuario"

    # Menús plantilla según perfil (expandibles en producción)
    menus = {
        ("omnivoro", "perder grasa"): {
            "desayuno":  "🍳 Tortilla de 2 huevos + 1 tostada integral + café/té sin azúcar",
            "almuerzo":  "🍗 Pechuga a la plancha (150g) + arroz integral (80g cocido) + ensalada",
            "merienda":  "🍎 1 manzana + 10 almendras",
            "cena":      "🐟 Merluza al horno (150g) + verduras salteadas + 1 yogur natural",
        },
        ("omnivoro", "ganar musculo"): {
            "desayuno":  "🥣 Avena (80g) + 1 plátano + 4 claras de huevo + 1 cucharada mantequilla de cacahuete",
            "almuerzo":  "🍚 Arroz integral (120g cocido) + pechuga de pavo (200g) + aguacate ½",
            "merienda":  "🍌 Batido: leche desnatada + plátano + 30g proteína whey",
            "cena":      "🥩 Solomillo de ternera (180g) + patata cocida (150g) + brócoli",
        },
        ("vegetariano", "perder grasa"): {
            "desayuno":  "🥑 Tostada integral + aguacate + tomate + queso fresco 0%",
            "almuerzo":  "🌮 Bowl de quinoa (80g cocida) + garbanzos (100g) + espinacas + limón",
            "merienda":  "🍊 1 naranja + 1 yogur griego natural",
            "cena":      "🧆 Tortilla de espinacas (2 huevos) + ensalada de pepino y tomate",
        },
        ("vegano", "ganar musculo"): {
            "desayuno":  "🌾 Avena (100g) + leche de avena + semillas de chía + 1 plátano",
            "almuerzo":  "🫘 Lentejas rojas guisadas (200g cocidas) + arroz integral (100g) + aguacate",
            "merienda":  "🥜 Hummus (100g) + bastones de zanahoria y pepino + 1 naranja",
            "cena":      "🥦 Tofu salteado (180g) + brócoli + arroz jazmín (80g cocido)",
        },
    }

@bot.message_handler(commands=["entrene"])
def cmd_entrene(message: types.Message) -> None:
    chat_id = message.chat.id
    usuario = db.obtener_usuario(chat_id)

    if usuario is None or usuario["paso_onboarding"] < TOTAL_ONBOARDING_STEPS:
        bot.reply_to(message, "Primero completa tu registro con /start 🙂")
        return

    db.obtener_o_crear_registro_hoy(chat_id)
    bot.reply_to(
        message,
        "💪 *¿Qué tipo de entrenamiento hiciste hoy?*",
        reply_markup=_kb_tipo_entreno(),
        parse_mode="Markdown"
    )
    # Buscar menú más cercano al perfil o usar el omnívoro mantenimiento como fallback
    menu = (
        menus.get((dieta, objetivo))
        or menus.get(("omnivoro", "perder grasa"))
    )

    respuesta = (
        f"🗓️ *Menú para {nombre}*\n"
        f"_{objetivo.capitalize()} · {dieta.capitalize()} · {comidas} comidas/día_\n\n"
    )

    iconos_momento = {
        "desayuno":  "☀️ Desayuno",
        "almuerzo":  "🥗 Almuerzo",
        "merienda":  "🍎 Merienda",
        "cena":      "🌙 Cena",
    }

    for momento, descripcion in menu.items():
        if comidas < 4 and momento == "merienda":
            continue   # Omitir merienda si el usuario hace menos de 4 comidas
        label = iconos_momento.get(momento, momento.capitalize())
        respuesta += f"*{label}*\n{descripcion}\n\n"

    respuesta += "_💡 Ajusta porciones con tu nutricionista según tu progreso._"

    bot.reply_to(message, respuesta, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# ARRANQUE
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Inicializar la base de datos
    db.init_db()
    logger.info("Base de datos inicializada.")

    # Arrancar el scheduler en segundo plano
    scheduler = sched.iniciar_scheduler(bot)
    logger.info("Scheduler iniciado.")

    logger.info("NutriBot arrancando en modo polling...")

    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=30,
            logger_level=logging.WARNING,
        )
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario.")
    finally:
        scheduler.shutdown()
        logger.info("Scheduler detenido. Hasta pronto.")
