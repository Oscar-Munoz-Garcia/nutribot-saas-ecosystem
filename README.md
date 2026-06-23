# 🥦 NutriBot SaaS Ecosystem

> **Ecosistema de Soporte y Analítica para Clínicas de Nutrición**
> Bot de Telegram 24/7 para pacientes + Base de datos SQLite lista para Power BI

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![pyTelegramBotAPI](https://img.shields.io/badge/pyTelegramBotAPI-4.21-blue?style=flat-square)
![APScheduler](https://img.shields.io/badge/APScheduler-3.10-green?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Power BI](https://img.shields.io/badge/Power_BI-Ready-F2C811?style=flat-square&logo=powerbi&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

---

## 📋 Índice

- [El Problema de Negocio](#-el-problema-de-negocio)
- [La Solución: Arquitectura de dos capas](#-la-solución)
- [Demo de flujos](#-demo-de-flujos)
- [Arquitectura técnica](#-arquitectura-técnica)
- [Modelo de datos relacional](#-modelo-de-datos-relacional)
- [Conectar con Power BI](#-conectar-con-power-bi)
- [Instalación y puesta en marcha](#-instalación-y-puesta-en-marcha)
- [Estructura del repositorio](#-estructura-del-repositorio)
- [Roadmap](#-roadmap)

---

## 🎯 El Problema de Negocio

Los nutricionistas pierden entre el **40% y el 60% de sus pacientes en los primeros 3 meses**, no por falta de planificación dietética, sino por un fallo sistémico en el seguimiento:

| Problema | Consecuencia |
|---|---|
| Los registros de peso y adherencia se hacen en papel o en Excel manual | El paciente olvida, falsea o abandona el registro |
| Sin datos continuos, el nutricionista no puede ajustar la dieta en tiempo real | Las revisiones mensuales se basan en recuerdos subjetivos |
| El paciente no tiene apoyo entre consultas | El abandono ocurre en los días "difíciles" |
| No hay correlación entre lugar de comida y adherencia | Se pierden insights clave (oficina = mayor riesgo de incumplimiento) |

**NutriBot** es un sistema SaaS de soporte que actúa como asistente personal del paciente y fuente de verdad de datos para el nutricionista, eliminando el papel del proceso.

---

## 💡 La Solución

El ecosistema opera en dos capas independientes:

```
┌─────────────────────────────────────────────────────────────────────┐
│  CAPA 1: INTERFAZ DEL PACIENTE (Telegram Bot)                       │
│                                                                     │
│  Paciente  ──►  Bot 24/7  ──►  Onboarding  ──►  Check-ins diarios  │
│                               (6 pasos)         (peso, foto, dieta) │
│                                    │                                │
│                                    ▼                                │
│                           APIs externas                             │
│                     Spoonacular / Open Food Facts                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  Escritura en SQLite
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CAPA 2: ANALÍTICA PARA EL NUTRICIONISTA (Power BI)                 │
│                                                                     │
│  nutricion.db  ──►  Power BI Desktop  ──►  Dashboards de           │
│                      (importación)          correlación             │
│                                             Peso vs Adherencia      │
│                                             Lugar vs Cumplimiento   │
└─────────────────────────────────────────────────────────────────────┘
```

### ¿Por qué sin LLMs?

El bot es **100% determinista**: lógica pura de eventos, máquina de estados y APIs REST.
Esto garantiza:
- ✅ Respuestas predecibles y auditables (crítico en entornos de salud)
- ✅ Coste de operación prácticamente cero (sin tokens de OpenAI)
- ✅ Tiempo de respuesta < 200ms en cualquier consulta
- ✅ Sin alucinaciones que puedan dar consejos nutricionales peligrosos

---

## 🎥 Demo de Flujos

### Flujo 1: Onboarding del paciente nuevo

```
Paciente: /start
Bot: 👋 ¡Hola, María! Voy a hacerte 6 preguntas rápidas...

[Paso 1] ¿Cuál es tu objetivo?
         [🔥 Perder grasa] [💪 Ganar músculo] [⚖️ Mantener]
                  ↓ pulsa botón
[Paso 2] ¿Nivel de actividad física?
         [🛋️ Sedentario] [🚶 Moderado] [🏋️ Activo]
                  ↓ ... (6 pasos en total)
Bot: 🎉 ¡Perfil configurado! Recibirás recordatorios cada mañana.
```

### Flujo 2: Check-in matutino automatizado

```
08:00 AM — Bot (proactivo): ☀️ ¡Buenos días, María!
           ¿Cuánto pesas hoy? Escríbelo así: 74.5
           💪 Recuerda que hoy tienes entrenamiento programado.

Paciente:  74.2
Bot:       ⚖️ ¡Peso registrado! 74.2 kg → guardado en la BD.
```

### Flujo 3: Registro fotográfico de comida

```
Paciente:  [envía foto del plato]
Bot:       📸 ¡Foto guardada!
           ¿Cumpliste la dieta hoy?
           [✅ Sí] [⚠️ Parcialmente] [❌ No]
                  ↓
           ¿Dónde comiste?
           [🏠 Casa] [🏢 Oficina] [🍽️ Restaurante]
```

### Flujo 4: Consulta de receta con /quecomo

```
Paciente:  /quecomo
Bot:       🍽️ ¿Para qué comida?
           [☀️ Desayuno] [🥗 Almuerzo] [🌙 Cena] [🍎 Snack]
                  ↓ selecciona "Almuerzo"
Bot:       🍽️ Sugerencia para tu almuerzo
           📌 Grilled Chicken Bowl with Quinoa
           ⏱️ 25 minutos
           🔥 Calorías: 490 kcal
           💪 Proteína: 42g | 🍞 Carbos: 38g | 🥑 Grasas: 14g
           🔗 Ver receta completa
```

---

## 🏗️ Arquitectura Técnica

```
nutribot-saas-ecosystem/
│
├── bot.py              ← Punto de entrada. Handlers y máquina de estados
├── config.py           ← Variables de entorno y constantes
├── database.py         ← Capa de datos SQLite (CRUD limpio)
├── scheduler_jobs.py   ← APScheduler: tareas mañana (08:00) y noche (21:30)
│
├── services/
│   └── food_api.py     ← Puente con Spoonacular y Open Food Facts
│
├── dashboard/
│   └── nutribot_analytics.pbix  ← Informe Power BI preconfigurado
│
└── fotos_comida/       ← Almacenamiento local de imágenes de pacientes
```

### Stack tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Interfaz de usuario | Telegram Bot API (pyTelegramBotAPI) | Penetración masiva, sin app propia que mantener |
| Base de datos | SQLite 3 | Zero-config, portable, compatible directo con Power BI |
| Scheduler | APScheduler 3 (BackgroundScheduler) | Ligero, sin necesidad de Redis/Celery en v1 |
| API de recetas | Spoonacular REST API | +365K recetas, filtros por dieta y macros |
| API de productos | Open Food Facts (open source) | Gratuita, sin API key, datos de calidad |
| Analítica | Microsoft Power BI Desktop | Gratuito, dominante en entornos clínicos y empresariales |

---

## 🗄️ Modelo de Datos Relacional

```sql
┌─────────────────────────────────────┐
│           usuarios                  │
├─────────────────────────────────────┤
│ id_telegram      INTEGER  PK        │
│ nombre           TEXT               │
│ objetivo         TEXT               │  'perder grasa' | 'ganar musculo' | 'mantener'
│ actividad        TEXT               │  'sedentario' | 'moderado' | 'activo'
│ dieta_tipo       TEXT               │  'omnivoro' | 'vegetariano' | 'vegano'
│ intolerancias    TEXT               │  CSV: 'lactosa,gluten'
│ comidas_al_dia   INTEGER            │
│ hora_cena        TEXT               │  'HH:MM'
│ paso_onboarding  INTEGER            │  0-6 (máquina de estados)
└────────────────┬────────────────────┘
                 │ 1:N
                 ▼
┌─────────────────────────────────────┐
│         registros_diarios           │
├─────────────────────────────────────┤
│ id_registro    INTEGER  PK AUTOINCR │
│ id_telegram    INTEGER  FK          │
│ fecha          TEXT                 │  'YYYY-MM-DD'
│ peso           REAL                 │  nullable
│ entrena_hoy    INTEGER              │  0 | 1
│ cumplio_dieta  INTEGER              │  0=No | 1=Sí | 2=Parcial
│ lugar_comida   TEXT                 │  'Casa' | 'Oficina' | 'Restaurante'
│ ruta_foto      TEXT                 │  nullable, ruta local
└─────────────────────────────────────┘
```

### Queries analíticas de ejemplo

```sql
-- Adherencia semanal por paciente
SELECT
    u.nombre,
    AVG(CASE WHEN r.cumplio_dieta = 1 THEN 100
             WHEN r.cumplio_dieta = 2 THEN 50
             ELSE 0 END) AS pct_adherencia
FROM registros_diarios r
JOIN usuarios u ON u.id_telegram = r.id_telegram
WHERE r.fecha >= DATE('now', '-7 days')
GROUP BY u.nombre;

-- Correlación lugar de comida con cumplimiento (insight clave)
SELECT
    lugar_comida,
    COUNT(*) AS total_dias,
    ROUND(AVG(CASE WHEN cumplio_dieta = 1 THEN 100.0
                   WHEN cumplio_dieta = 2 THEN 50.0
                   ELSE 0 END), 1) AS adherencia_pct
FROM registros_diarios
WHERE lugar_comida IS NOT NULL
GROUP BY lugar_comida
ORDER BY adherencia_pct DESC;

-- Evolución de peso de un paciente
SELECT fecha, peso
FROM registros_diarios
WHERE id_telegram = ?
  AND peso IS NOT NULL
ORDER BY fecha ASC;
```

---

## 📊 Conectar con Power BI

El archivo `nutricion.db` que genera el bot está **listo para importarse en Power BI Desktop** sin ninguna transformación adicional.

### Pasos de conexión (5 minutos)

1. Abre **Power BI Desktop** → `Obtener datos` → `Más...`
2. Busca y selecciona **ODBC**
3. En el DSN, escribe la ruta del archivo: `Driver=SQLite3 ODBC Driver;Database=C:\ruta\nutricion.db`
4. Selecciona las tablas `usuarios` y `registros_diarios`
5. Pulsa **Transformar datos** y verifica los tipos (fecha → Date, peso → Decimal)
6. Cierra el editor y crea tus visualizaciones

> 💡 **Alternativa más sencilla:** En Power BI Desktop → `Obtener datos` → `Base de datos SQLite` (disponible en versiones recientes).

### Dashboards sugeridos

| Página | Visualizaciones | Insights que revela |
|---|---|---|
| **Vista General** | KPI cards: pacientes activos, adherencia media, peso promedio | Salud global de la clínica |
| **Adherencia** | Gráfico de barras: `lugar_comida` vs `pct_adherencia` | ¿Dónde falla la dieta? (suele ser Oficina) |
| **Evolución de Peso** | Línea temporal filtrable por paciente | Efectividad real de cada plan |
| **Entrenamiento** | Heatmap semanal de días de entreno | Correlación entreno-peso |

<!-- Añade capturas aquí cuando tengas el dashboard configurado -->
<!--
![Vista General](dashboard/screenshots/vista_general.png)
![Análisis de Adherencia](dashboard/screenshots/analisis_adherencia.png)
-->

---

## 🚀 Instalación y Puesta en Marcha

### Prerrequisitos

- Python 3.10 o superior
- Una cuenta de Telegram y un bot creado con [@BotFather](https://t.me/BotFather)
- (Opcional) API key gratuita de [Spoonacular](https://spoonacular.com/food-api)

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/nutribot-saas-ecosystem.git
cd nutribot-saas-ecosystem
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
# Linux / macOS
export TELEGRAM_TOKEN="tu_token_de_botfather"
export SPOONACULAR_KEY="tu_api_key_spoonacular"   # opcional

# Windows (CMD)
set TELEGRAM_TOKEN=tu_token_de_botfather
set SPOONACULAR_KEY=tu_api_key_spoonacular
```

> ⚠️ **Nunca escribas tus tokens directamente en el código ni los subas a GitHub.**
> El archivo `.gitignore` ya excluye `.env`, pero siempre usa variables de entorno.

### 4. Iniciar el bot

```bash
python bot.py
```

Verás en la consola:
```
2024-01-15 08:00:00 [INFO] root: Base de datos inicializada.
2024-01-15 08:00:00 [INFO] root: Scheduler iniciado.
2024-01-15 08:00:00 [INFO] root: NutriBot arrancando en modo polling...
```

### 5. Probar en Telegram

Busca tu bot por su nombre de usuario y envía `/start`.

---

## 📁 Estructura del Repositorio

```
nutribot-saas-ecosystem/
│
├── .gitignore                  # Excluye .db, fotos, credenciales
├── README.md                   # Esta documentación
├── requirements.txt            # pyTelegramBotAPI, APScheduler, requests
│
├── config.py                   # Variables de entorno y constantes
├── database.py                 # Capa SQLite: init_db() + CRUD
├── bot.py                      # Handlers, máquina de estados, comandos
├── scheduler_jobs.py           # Tareas automáticas: 08:00 y 21:30
│
├── services/
│   ├── __init__.py
│   └── food_api.py             # Spoonacular + Open Food Facts
│
├── dashboard/
│   ├── nutribot_analytics.pbix # Informe Power BI (añadir manualmente)
│   └── screenshots/            # Capturas para el README
│
└── fotos_comida/
    └── .gitkeep                # Carpeta versionada pero vacía
```

---

## 🗺️ Roadmap

### v1.0 — MVP actual
- [x] Onboarding completo en 6 pasos con máquina de estados
- [x] Check-ins automáticos de mañana y noche
- [x] Registro de peso, foto, adherencia y lugar
- [x] Consulta de recetas personalizadas (Spoonacular)
- [x] Escaneo de código de barras (Open Food Facts)
- [x] Base de datos lista para Power BI

### v1.1 — Próximas mejoras
- [ ] Notificaciones personalizadas por hora_cena del usuario
- [ ] Gráfica de evolución de peso inline (matplotlib → imagen en Telegram)
- [ ] Panel web mínimo para el nutricionista (Flask)
- [ ] Exportación automática de informe PDF mensual

### v2.0 — Versión avanzada
- [ ] Despliegue en servidor (Railway / Render / VPS)
- [ ] Multi-clínica: soporte para múltiples nutricionistas
- [ ] Reconocimiento de alimentos en fotos (Vision API)
- [ ] Integración con Google Fit / Apple Health

---

## 📄 Licencia

MIT © 2024 — Libre para uso personal, educativo y comercial con atribución.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Haz fork del repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commitea tus cambios: `git commit -m 'feat: añadir X'`
4. Abre un Pull Request describiendo qué resuelve

---

<div align="center">
  <sub>Construido con Python 🐍 · Telegram Bot API · SQLite · Power BI</sub>
</div>
