# Videos_downloader — Análisis y Mejoras

> Plataforma full-stack de automatización de contenido viral: descubre, descarga (sin marca de agua), procesa (9:16 + subtítulos IA), genera descripción/hashtags y **sube a TikTok** automatizado.
> Repo: https://github.com/brolyroly007/Videos_downloader

---

## 1. Radiografía

| Aspecto | Detalle |
|---------|---------|
| **Backend** | Python 3.8+, FastAPI, Uvicorn (`app.py` ~1.654 líneas + 14 módulos, ~9.500 LOC) |
| **Frontend** | Next.js 16, React 19, Tailwind v4, Radix UI |
| **Video/IA** | FFmpeg, MoviePy, OpenCV, Whisper (opcional), Ollama/ChatGPT |
| **Automatización** | Playwright + Selenium (upload a TikTok), yt-dlp |
| **Datos** | 5x SQLite (auth, automation, analytics, queue, hashtags) + Redis opcional |
| **Deploy** | Docker Compose (backend, frontend, redis, backup) |
| **Tests** | ⚠️ 4 pruebas básicas (GET), cobertura < 10% |
| **CI/CD** | ✅ GitHub Actions (lint + test + docker build) |

**Fortalezas:** arquitectura modular y clara, documentación buena en README, CI presente, pipeline de procesamiento bien separado.

**Debilidades críticas:**
- 🔴 **Contraseña admin hardcodeada** (`modules/auth.py:115` → `admin123`).
- 🔴 **Secretos sin proteger**: cookies de TikTok en JSON plano, API keys sin validación, sin cifrado en reposo.
- 🔴 **Sin rate limiting** → `/api/auth/login` vulnerable a fuerza bruta.
- 🟠 **Estado en memoria** (`tasks_status` global) → no es thread-safe ni sobrevive a reinicios; semáforos locales no funcionan multi-worker.
- 🟠 **Whisper se recarga por request** (`app.py:276,434`) → coste de RAM/latencia enorme.
- 🟠 **Legalidad**: descarga sin marca de agua + upload automatizado viola los ToS de TikTok (riesgo de ban/DMCA).
- `except:` silencioso (`auth.py:141`), type hints incorrectos (`callable`/`any`).

---

## 2. 🎯 Mejora consistencial

**Convertir el prototipo en una plataforma segura y escalable: secretos gestionados + cola de trabajos persistente + auth real.**

El problema de fondo no es una función concreta, sino que **el estado y los secretos viven en el proceso**. La mejora coherente es mover los tres pilares fuera del proceso:

1. **Secretos** → variables de entorno + cifrado (`cryptography`), nada hardcodeado, contraseña admin aleatoria con cambio forzado.
2. **Trabajos** → reemplazar `tasks_status` + semáforos locales por **Celery + Redis** (persistencia, reintentos, escalado multi-worker).
3. **Acceso** → JWT + rate limiting por IP (Redis).

Es "consistencial" porque desbloquea simultáneamente seguridad, escalabilidad y fiabilidad — las tres debilidades de mayor severidad.

---

## 3. 🚀 Supermejoras (ordenadas por impacto)

| # | Mejora | Por qué | Esfuerzo |
|---|--------|---------|----------|
| 1 | **Gestión de secretos** (env + cifrado, admin pass aleatoria, cookies cifradas) | Cierra el agujero de seguridad más grave | Medio (3-4h) |
| 2 | **Cola con Celery + Redis** (sustituye estado en memoria y semáforos) | Escalable, persistente, con reintentos | Alto (6-8h) |
| 3 | **Tests críticos ≥ 40%** (VideoProcessor, Uploader, ViralDetector + integración, mocks de yt-dlp/Playwright/Whisper) | Detecta regresiones antes de deploy | Medio (4-6h) |
| 4 | **JWT + rate limiting** (10 req/min/IP, refresh tokens, audit log) | Frena fuerza bruta y bots | Medio (3-4h) |
| 5 | **Singleton de Whisper en startup** + connection pooling SQLite/Redis | Elimina recarga de modelo; multi-worker safe | Medio (4-5h) |
| 6 | **Cumplimiento legal** (modal de consentimiento, modo manual de upload, `docs/LEGAL.md`) | Reduce riesgo legal y de ban | Bajo (2-3h) |
| 7 | **Observabilidad** (structlog JSON, Prometheus, Sentry) | Debug en producción | Bajo (3h) |
| 8 | **Performance** (descarga en streaming, caché de metadatos, gzip) | Menos latencia y memoria | Alto (5-6h) |

---

## 4. 🏁 Metas / Roadmap

- **Sprint 1 — Seguridad (bloqueante para producción):** secretos gestionados + JWT + rate limiting + quitar `admin123`.
- **Sprint 2 — Fiabilidad:** Celery+Redis, singleton de Whisper, estado persistente, tests ≥ 40%.
- **Sprint 3 — Cumplimiento y pulido:** modal legal + modo manual, observabilidad, streaming.

> Estimación top-5: **40-60 horas** (≈1 semana, 2 devs).

### Métricas de éxito
- ✅ 0 secretos en el repo (escaneo con `gitleaks` en CI).
- ✅ La app sobrevive a un reinicio sin perder trabajos en curso.
- ✅ Cobertura ≥ 40% y CI verde.
- ✅ Login resiste 1.000 intentos/min sin degradarse (rate limit activo).

---

## 5. 💻 Snippet de referencia

**Eliminar la contraseña admin hardcodeada** (`modules/auth.py:115`):

```python
# --- antes (inseguro) ---
# password_hash = self._hash_password("admin123")

# --- después: aleatoria en el primer arranque, forzar cambio ---
import secrets

def ensure_admin(self):
    if self.user_exists("admin"):
        return
    temp = secrets.token_urlsafe(16)
    self.create_user("admin", self._hash_password(temp), must_change=True)
    logger.warning("Admin creado. Contraseña temporal (cámbiala ya): %s", temp)
```

**Rate limiting por IP con Redis** (FastAPI middleware), frena la fuerza bruta en `/api/auth/login`:

```python
from fastapi import Request, HTTPException

async def rate_limit(request: Request, limit=10, window=60):
    ip = request.client.host
    key = f"rl:{ip}:{request.url.path}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window)
    if n > limit:
        raise HTTPException(429, "Demasiadas solicitudes, intenta más tarde.")
```

**Cola persistente con Celery** (reemplaza `tasks_status` global + semáforos):

```python
# tasks.py
@celery_app.task(bind=True, max_retries=3)
def download_task(self, url: str):
    try:
        return downloader.download(url)
    except TransientError as e:
        raise self.retry(exc=e, countdown=10)

# en el endpoint: task = download_task.delay(url) -> sobrevive a reinicios
```

