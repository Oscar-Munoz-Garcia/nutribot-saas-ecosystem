"""
database.py — Capa de datos del ecosistema NutriBot.

Gestiona la base de datos SQLite 'nutricion.db'.
Todas las operaciones usan context managers para garantizar
el cierre seguro de conexiones y transacciones atómicas.

Tablas:
  - usuarios          → perfil y estado de onboarding de cada paciente
  - registros_diarios → check-in diario: peso, entrenamiento, adherencia, foto
"""

import sqlite3
from datetime import date
from typing import Optional

from config import DB_PATH


# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES INTERNAS
# ──────────────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Devuelve una conexión con Row Factory para acceso por nombre de columna."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# INICIALIZACIÓN
# ──────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Crea las tablas de la base de datos si aún no existen.
    Llamar una sola vez al arrancar la aplicación.
    """
    with _get_conn() as conn:
        conn.executescript("""
            -- ── Tabla de perfiles de usuario ─────────────────────────────────
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram      INTEGER PRIMARY KEY,
                nombre           TEXT,
                objetivo         TEXT,   -- 'perder grasa' | 'ganar musculo' | 'mantener'
                actividad        TEXT,   -- 'sedentario' | 'moderado' | 'activo'
                dieta_tipo       TEXT,   -- 'omnivoro' | 'vegetariano' | 'vegano'
                intolerancias    TEXT,   -- ej. 'lactosa,gluten' (CSV)
                comidas_al_dia   INTEGER,
                hora_cena        TEXT,   -- formato 'HH:MM', ej. '21:30'
                paso_onboarding  INTEGER DEFAULT 0  -- 0 = no iniciado, 6 = completo
            );

            -- ── Tabla de check-ins diarios ────────────────────────────────────
            CREATE TABLE IF NOT EXISTS registros_diarios (
                id_registro    INTEGER PRIMARY KEY AUTOINCREMENT,
                id_telegram    INTEGER NOT NULL,
                fecha          TEXT NOT NULL,   -- 'YYYY-MM-DD'
                peso           REAL,            -- nullable hasta que el usuario lo reporte
                entrena_hoy    INTEGER,         -- 0 = no | 1 = sí
                cumplio_dieta  INTEGER,         -- 0 = no | 1 = sí | 2 = parcial
                lugar_comida   TEXT,            -- 'Casa' | 'Oficina' | 'Restaurante'
                ruta_foto      TEXT,            -- ruta local de la foto, nullable
                FOREIGN KEY (id_telegram) REFERENCES usuarios(id_telegram)
            );
        """)


# ──────────────────────────────────────────────────────────────────────────────
# CRUD — USUARIOS
# ──────────────────────────────────────────────────────────────────────────────

def crear_usuario(id_telegram: int, nombre: str) -> None:
    """Inserta un nuevo usuario con paso_onboarding = 0."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO usuarios (id_telegram, nombre, paso_onboarding) VALUES (?, ?, 0)",
            (id_telegram, nombre)
        )


def obtener_usuario(id_telegram: int) -> Optional[sqlite3.Row]:
    """Devuelve la fila completa del usuario o None si no existe."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE id_telegram = ?",
            (id_telegram,)
        ).fetchone()


def actualizar_campo_usuario(id_telegram: int, campo: str, valor) -> None:
    """
    Actualiza un campo específico del perfil del usuario.

    Parámetros seguros (campo debe ser uno de los permitidos para evitar SQLi).
    """
    campos_permitidos = {
        "nombre", "objetivo", "actividad", "dieta_tipo",
        "intolerancias", "comidas_al_dia", "hora_cena", "paso_onboarding"
    }
    if campo not in campos_permitidos:
        raise ValueError(f"Campo no permitido: {campo}")

    with _get_conn() as conn:
        conn.execute(
            f"UPDATE usuarios SET {campo} = ? WHERE id_telegram = ?",
            (valor, id_telegram)
        )


def avanzar_paso_onboarding(id_telegram: int) -> int:
    """
    Incrementa el paso_onboarding en 1 y devuelve el nuevo valor.
    Útil para la máquina de estados del flujo de registro.
    """
    with _get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET paso_onboarding = paso_onboarding + 1 WHERE id_telegram = ?",
            (id_telegram,)
        )
        row = conn.execute(
            "SELECT paso_onboarding FROM usuarios WHERE id_telegram = ?",
            (id_telegram,)
        ).fetchone()
        return row["paso_onboarding"]


def obtener_todos_usuarios() -> list:
    """Devuelve todos los usuarios registrados (para el scheduler)."""
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM usuarios").fetchall()


# ──────────────────────────────────────────────────────────────────────────────
# CRUD — REGISTROS DIARIOS
# ──────────────────────────────────────────────────────────────────────────────

def _hoy() -> str:
    """Retorna la fecha actual en formato YYYY-MM-DD."""
    return date.today().isoformat()


def obtener_o_crear_registro_hoy(id_telegram: int) -> sqlite3.Row:
    """
    Devuelve el registro de hoy para el usuario.
    Si no existe, lo crea con valores nulos para completar más tarde.
    """
    hoy = _hoy()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM registros_diarios WHERE id_telegram = ? AND fecha = ?",
            (id_telegram, hoy)
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO registros_diarios (id_telegram, fecha) VALUES (?, ?)",
                (id_telegram, hoy)
            )
            row = conn.execute(
                "SELECT * FROM registros_diarios WHERE id_telegram = ? AND fecha = ?",
                (id_telegram, hoy)
            ).fetchone()

        return row


def registrar_peso(id_telegram: int, peso: float) -> None:
    """Actualiza el peso del registro de hoy."""
    hoy = _hoy()
    obtener_o_crear_registro_hoy(id_telegram)  # garantiza que el registro existe
    with _get_conn() as conn:
        conn.execute(
            "UPDATE registros_diarios SET peso = ? WHERE id_telegram = ? AND fecha = ?",
            (peso, id_telegram, hoy)
        )


def registrar_entrenamiento_manana(id_telegram: int, entrena: int) -> None:
    """
    Registra si el usuario entrenará mañana.
    Crea el registro de mañana si no existe.
    """
    from datetime import timedelta
    manana = (date.today() + timedelta(days=1)).isoformat()
    with _get_conn() as conn:
        # Upsert: inserta o actualiza el registro de mañana
        conn.execute(
            """
            INSERT INTO registros_diarios (id_telegram, fecha, entrena_hoy)
            VALUES (?, ?, ?)
            ON CONFLICT(id_telegram) DO NOTHING
            """,
            (id_telegram, manana, entrena)
        )
        conn.execute(
            "UPDATE registros_diarios SET entrena_hoy = ? WHERE id_telegram = ? AND fecha = ?",
            (entrena, id_telegram, manana)
        )


def registrar_foto(id_telegram: int, ruta: str) -> None:
    """Guarda la ruta local de la foto en el registro de hoy."""
    hoy = _hoy()
    obtener_o_crear_registro_hoy(id_telegram)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE registros_diarios SET ruta_foto = ? WHERE id_telegram = ? AND fecha = ?",
            (ruta, id_telegram, hoy)
        )


def registrar_adherencia(id_telegram: int, cumplio: int, lugar: str) -> None:
    """
    Actualiza si el usuario cumplió la dieta y dónde comió hoy.

    cumplio: 0 = no | 1 = sí | 2 = parcial
    lugar:   'Casa' | 'Oficina' | 'Restaurante'
    """
    hoy = _hoy()
    obtener_o_crear_registro_hoy(id_telegram)
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE registros_diarios
            SET cumplio_dieta = ?, lugar_comida = ?
            WHERE id_telegram = ? AND fecha = ?
            """,
            (cumplio, lugar, id_telegram, hoy)
        )


def obtener_ultimos_registros(id_telegram: int, dias: int = 7) -> list:
    """
    Devuelve los últimos `dias` registros del usuario ordenados por fecha DESC.
    Usado por /progreso para calcular adherencia semanal.
    """
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT fecha, peso, cumplio_dieta, entrena_hoy, lugar_comida
            FROM registros_diarios
            WHERE id_telegram = ?
            ORDER BY fecha DESC
            LIMIT ?
            """,
            (id_telegram, dias)
        ).fetchall()


def registrar_entrenamiento_hoy(id_telegram: int, entrena: int) -> None:
    """Registra si el usuario entrenó hoy."""
    hoy = _hoy()
    obtener_o_crear_registro_hoy(id_telegram)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE registros_diarios SET entrena_hoy = ? WHERE id_telegram = ? AND fecha = ?",
            (entrena, id_telegram, hoy)
        )