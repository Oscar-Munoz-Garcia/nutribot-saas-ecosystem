"""
scheduler_jobs.py — Tareas proactivas programadas del ecosistema NutriBot.

Usa APScheduler (BackgroundScheduler) para disparar mensajes
automáticos a todos los usuarios registrados en horarios fijos.

Tareas:
  - tarea_manana()  → 08:00 AM: pide el peso del día y recuerda el entrenamiento
  - tarea_noche()   → 21:30 PM: pregunta con botones si entrenará mañana

El bot de Telegram debe pasarse como dependencia para poder llamar a bot.send_message().
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db
from config import MORNING_HOUR, MORNING_MINUTE, EVENING_HOUR, EVENING_MINUTE

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# TAREAS
# ──────────────────────────────────────────────────────────────────────────────

def tarea_manana(bot) -> None:
    """
    Tarea de la mañana (08:00 AM).

    Para cada usuario registrado:
      1. Envía un recordatorio para registrar el peso del día.
      2. Si el usuario indicó que hoy entrena, añade un recordatorio motivacional.
    """
    usuarios = db.obtener_todos_usuarios()
    logger.info(f"[Scheduler Mañana] Enviando mensajes a {len(usuarios)} usuarios.")

    for usuario in usuarios:
        # Solo contactar usuarios que completaron el onboarding
        if usuario["paso_onboarding"] < 6:
            continue

        chat_id = usuario["id_telegram"]
        nombre  = usuario["nombre"] or "campeón"

        # Obtener (o crear) el registro de hoy para verificar si entrena
        registro_hoy = db.obtener_o_crear_registro_hoy(chat_id)
        entrena_hoy  = registro_hoy["entrena_hoy"]

        mensaje = (
            f"☀️ ¡Buenos días, {nombre}!\n\n"
            f"📏 ¿Cuánto pesas hoy? Escríbelo así: *74.5*\n"
            f"_(Solo el número en kg, con punto decimal si aplica)_"
        )

        if entrena_hoy == 1:
            mensaje += "\n\n💪 *Recuerda que hoy tienes entrenamiento programado.* ¡Tú puedes!"

        try:
            bot.send_message(chat_id, mensaje, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[Scheduler Mañana] No se pudo enviar mensaje a {chat_id}: {e}")


def tarea_noche(bot) -> None:
    """
    Tarea de la noche (21:30 PM o según hora_cena del usuario).

    Envía un Inline Keyboard preguntando si el usuario entrenará mañana.
    Nota: el scheduler ejecuta esta tarea a las 21:30 globalmente.
    Para personalización por usuario se podría usar triggers individuales
    en una versión avanzada del producto.
    """
    import telebot

    usuarios = db.obtener_todos_usuarios()
    logger.info(f"[Scheduler Noche] Enviando mensajes a {len(usuarios)} usuarios.")

    for usuario in usuarios:
        if usuario["paso_onboarding"] < 6:
            continue

        chat_id = usuario["id_telegram"]
        nombre  = usuario["nombre"] or "campeón"

        # Crear Inline Keyboard con botones de respuesta rápida
        teclado = telebot.types.InlineKeyboardMarkup()
        teclado.row(
            telebot.types.InlineKeyboardButton("💪 Sí, entreno mañana", callback_data="entrena_manana_1"),
            telebot.types.InlineKeyboardButton("🛌 No, descanso",        callback_data="entrena_manana_0"),
        )

        mensaje = (
            f"🌙 Buenas noches, {nombre}.\n\n"
            f"¿Tienes planificado entrenar *mañana*?"
        )

        try:
            bot.send_message(chat_id, mensaje, reply_markup=teclado, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[Scheduler Noche] No se pudo enviar mensaje a {chat_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# INICIALIZACIÓN DEL SCHEDULER
# ──────────────────────────────────────────────────────────────────────────────

def iniciar_scheduler(bot) -> BackgroundScheduler:
    """
    Crea, configura e inicia el scheduler en segundo plano.

    Parámetros:
        bot → instancia de telebot.TeleBot ya configurada

    Devuelve el scheduler activo (para poder detenerlo al cerrar la app).
    """
    scheduler = BackgroundScheduler(timezone="Europe/Madrid")  # Ajusta a tu zona horaria

    # ── Tarea mañana ─────────────────────────────────────────────────────────
    scheduler.add_job(
        func=lambda: tarea_manana(bot),
        trigger=CronTrigger(hour=MORNING_HOUR, minute=MORNING_MINUTE),
        id="tarea_manana",
        name="Recordatorio de peso matutino",
        replace_existing=True,
        misfire_grace_time=300,   # 5 minutos de tolerancia si el servidor reinicia
    )

    # ── Tarea noche ───────────────────────────────────────────────────────────
    scheduler.add_job(
        func=lambda: tarea_noche(bot),
        trigger=CronTrigger(hour=EVENING_HOUR, minute=EVENING_MINUTE),
        id="tarea_noche",
        name="Check-in nocturno de entrenamiento",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info(
        f"[Scheduler] Iniciado. "
        f"Mañana: {MORNING_HOUR:02d}:{MORNING_MINUTE:02d} | "
        f"Noche: {EVENING_HOUR:02d}:{EVENING_MINUTE:02d}"
    )

    return scheduler
