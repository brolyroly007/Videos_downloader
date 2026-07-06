# Videos_downloader — Checklist de mejoras (GOAL del /loop)

> Generado 2026-07-06 tras revisión exhaustiva (frontend + backend).
> **Un /loop procesa este archivo cada 10 min:** toma el siguiente ítem `- [ ]` en orden
> (Crítico → Alto → Medio → Bajo), lo implementa, verifica que no rompe nada, hace commit
> (SIN co-author de Claude) y lo marca `- [x]`. El loop termina cuando no quedan `- [ ]`.
>
> Mejoras YA documentadas en `docs/MEJORAS.md` / `ROADMAP.md` (admin123, Celery+Redis,
> JWT+rate limiting, singleton Whisper, tests ≥40%, modal legal): seguir ese documento; NO duplicar aquí.

---

## BACKEND (`D:\Videos_downloader`)

### 🔴 Crítico

- [x] B1. `app.py:1037-1038` usa `video_processor` (no existe; la global es `processor`) → `NameError` tragado por el `except` de 1051: el auto-flow **nunca procesa** el video y sube el original. Además `VideoProcessor` no tiene `process(...)` async, sino `process_video(...)` síncrono. Corregir nombre y llamada (vía executor).
- [x] B2. `modules/subtitle_generator.py:220` usa `SubtitlesClip` sin importarlo → `NameError` siempre que `burn_subtitles=True` (default). Importar/implementar correctamente el quemado de subtítulos.
- [x] B3. Mezcla incompatible MoviePy 1.x/2.x: usa `resized`/`with_effects` (2.x) y también `.crop()` (video_processor.py:181), `.fl()` (194,343), `verbose=` (subtitle_generator.py:79), `fontsize=`/`set_position` (subtitle_generator.py:211,231). Ninguna versión hace funcionar todo. Fijar una versión de MoviePy y unificar la API. → Unificado a 2.x: `crop`→`cropped`, `fl`→`transform`, `fontsize`→`font_size`, `set_position`→`with_position`, quitado `verbose=`; requirements pin `moviepy>=2.0.0,<3.0.0`.
- [x] B4. Auth decorativa: `get_current_user`/`require_role` se importan pero no se aplican como `Depends` en ningún endpoint. `POST /api/auth/users` (app.py:1613) permite crear admin sin auth; `GET /api/auth/users` lista usuarios sin auth. Aplicar dependencias de auth a los endpoints sensibles. → Añadido `Depends(require_role("admin"))` a create_user y list_users (no-op si AUTH_ENABLED=false, enforce si true) e importado `Depends`. (Los endpoints destructivos de backup se cubren en B5.)
- [x] B5. Backup destructivo sin auth + Zip Slip: `POST /api/backup/restore/{name}` (app.py:1510) sobreescribe las 5 DB y hace `rmtree` de `cookies/`/`processed/`; `extractall()` sin sanitizar (backup_manager.py:175) = Zip Slip. Añadir auth + validar miembros del zip + no restaurar con conexiones abiertas. → `_safe_extract` valida cada miembro contra Zip Slip; `backup_name` saneado con `Path(name).name` en restore/delete/info (path traversal); `Depends(require_role("admin"))` en restore y delete. (Restaurar sin conexiones abiertas queda como nota operativa; los endpoints ahora exigen admin.)
- [x] B6. Bloqueo del event loop: `downloader.download()`, `processor.process_video()`, Whisper y transcripción corren directo en endpoints async (app.py:214,253,277,285,394,415,436,442,1006; automation_engine.py:580,591,614; viral_detector.py:381). Envolver en `run_in_executor`/`asyncio.to_thread`. → Envueltas todas en `loop.run_in_executor`: descargas, process_video y process_video_with_subtitles en `/api/download`, `/api/process`, `/api/complete-flow` y auto-flow; `_process_job` de automation_engine; y el `subprocess.run` de yt-dlp en viral_detector.get_video_details.

### 🟠 Alto

- [ ] B7. Inyección de args a yt-dlp: URL de usuario como posicional sin `--` (downloader.py:336-346, tiktok_discover.py:314-319, viral_detector.py:374-381). Añadir `--` y validar esquema `https?://`.
- [ ] B8. Path traversal (Windows) en `/files/downloads/{filename}` y `/files/processed/{filename}` (app.py:1230-1245) y en `backup_name` (app.py:1498,1510,1517). Sanitizar con `Path(x).name` y verificar prefijo resuelto.
- [ ] B9. `GET /api/backup/stats` (app.py:1527) registrado después de `GET /api/backup/{backup_name}` (1498) → 404 permanente. Mover antes de la ruta paramétrica.
- [ ] B10. TLS deshabilitado: `no_check_certificates: True` (downloader.py:126,402) y `--no-check-certificates` (338). Quitar salvo flag explícito.
- [ ] B11. Rutas hardcodeadas del dev en repo público: tiktok_discover.py:31-32, scripts/start.bat:21, export_cookies.py:160. Parametrizar por config/PATH.
- [ ] B12. Playwright roto en Docker: `playwright install chromium` como root (Dockerfile:47-48), luego `USER appuser` no lo encuentra; `headless=False` hardcodeado (app.py:474, automation_engine.py:691). Fijar `PLAYWRIGHT_BROWSERS_PATH` y headless configurable.
- [ ] B13. Race en cola: `queue_manager.get_next_job` (128-152) no verifica `rowcount` → doble toma. Usar `UPDATE ... RETURNING` o verificar rowcount.
- [ ] B14. Tres subsistemas muertos: `QueueManager` nunca `start()`/`set_processor()`; `AnalyticsManager.track_*` nunca invocado; `backup_manager.start_scheduled_backups` nunca llamado. Cablearlos o eliminarlos.
- [ ] B15. Caption de TikTok es `repr` de dataclass: app.py:1074 usa `full_description` (no existe; es `full_text`, description_generator.py:28). Corregir atributo.
- [ ] B16. Colisiones de temporales concurrentes: `temp-audio.m4a` (video_processor.py:215,261,288,315,349), `temp_audio.wav` (subtitle_generator.py:76), `_find_latest_download()` (downloader.py:307-309,377-390). Usar nombres con uuid.

### 🟡 Medio

- [ ] B17. Timeout de descarga inútil: se revisa tras `extract_info` (downloader.py:293-298); re-descarga videos ya completados vía `@_retry_download`. Aplicar timeout real o quitarlo del reintento.
- [ ] B18. Doble `AuthManager` (app.py:81 y auth.py:446). Consolidar en uno.
- [ ] B19. Auth: lockout por username sin IP (DoS de `admin`, auth.py:380-385); hash no constant-time (139 → `hmac.compare_digest`); `login_attempts`/`sessions` sin límite y `cleanup_expired_sessions` (299) nunca llamado; `remaining` negativo (402).
- [ ] B20. Crashes 500 por inputs: `avg_score/found` sin `found=0` (hashtag_recommender.py:446); `limit // len(hashtags)` con lista vacía (app.py:693); `hex_to_rgb` sin validar (app.py:175); `speed_factor` sin rango. Añadir validaciones/Pydantic.
- [ ] B21. `/api/complete-flow` y `/api/auto-flow` corren todo el pipeline dentro del request (app.py:356-497, 924-1135) pese a declarar `BackgroundTasks`. Ejecutar en background real y devolver task_id.
- [ ] B22. Upload reporta `success=True` con "confirmation pending" (uploader.py:294-298) y sleeps fijos (209: 5s) → métricas falsas y publicaciones a medias. Esperar confirmación real.
- [ ] B23. Deadlock SQLite en analytics: `record_processed_video` sin commit + `_log_event` abre 2ª conexión al mismo archivo (analytics.py:176). Reusar conexión/commit antes.
- [ ] B24. `/api/tiktok/login` bloquea 5 min con navegador visible y sin auth (app.py:1138-1188). Volver asíncrono con estado.
- [ ] B25. IDs de job con timestamp en segundos (app.py:760, automation_engine.py:717) → colisiones + `INSERT OR IGNORE` descarta. Usar uuid.
- [ ] B26. docker-compose.yml: monta SQLite como archivos (crea dirs si no existen), `auth.db` sin montar, Redis 6379 sin password, backup copia `cookies/` en claro, `version` obsoleto. Corregir volúmenes/seguridad.
- [ ] B27. Re-encode x4 (un `write_videofile` por efecto, video_processor.py:403-428) + intermedios `reframed_/mirrored_/speed_/color_*.mp4` nunca borrados. Componer en un render y limpiar temp.
- [ ] B28. Whisper opcional pero `generate_subtitles=True` por defecto → `AttributeError` con `model=None` (subtitle_generator.py:113). Chequear `WHISPER_AVAILABLE` y responder 422 claro.
- [ ] B29. pyproject.toml: `build-backend` inválido (`setuptools.backends._legacy:_Backend` → `setuptools.build_meta`); `requires-python=">=3.8"` falso (usa `list[str]`, 3.9+). Corregir.

### 🟢 Bajo

- [ ] B30. Config drift en .env.example/Dockerfile: variables documentadas que nadie lee (WHISPER_MODEL_SIZE, *_PATH, TIKTOK_*, DEFAULT_*, REDIS_URL) y faltan las reales (AUTH_ENABLED, MAX_DOWNLOAD_RETRIES, etc.). Migrar a `pydantic-settings` (ya en requirements).
- [ ] B31. Deps muertas/laxas: `selenium` sin uso (+100MB), `schedule` solo para scheduler apagado, `moviepy` cruza major, `yt-dlp`/`playwright` sin techo. Limpiar + lockfile.
- [ ] B32. Duplicación: `DescriptionGenerator` x2, `JobStatus` x2, `add_to_queue` x2 (app.py:741 y 1410, F811), viral score duplicado con pesos distintos (viral_detector.py:138 vs tiktok_discover.py:656). Unificar.
- [ ] B33. viral_detector: `async_playwright().start()` sin guardar (no `.stop()`, 125-126); `seen_videos` sin límite (74); selectores CSS rotos (260); `monitor_hashtags` `while True` sin parada (449).
- [ ] B34. `logging.basicConfig` repetido en los 14 módulos. Centralizar en app.py.
- [ ] B35. Basic auth re-hashea PBKDF2 100k por request (auth.py:466-470). Preferir tokens.
- [ ] B36. `static/`/`templates/` solo se crean en `__main__` (app.py:1637); `uvicorn app:app` en checkout limpio revienta (app.py:62). Crear en import.
- [ ] B37. CI: no instala ffmpeg, no ejecuta cobertura, sin escaneo de secretos (gitleaks), docker.yml con `push:false` y nombre viejo `proyectojudietha-*`. Completar.
- [ ] B38. `scripts/test_discover.py` y `scripts/test_yt.py`: tests manuales con `sys.path` hardcodeado y dataclass duplicado. Mover a tests/ o borrar.
- [ ] B39. hashtag_recommender.py:78-202 puebla `hashtags.db` con cifras inventadas servidas como reales. Marcar como estimado o quitar.
- [ ] B40. Tipado: `x: str = None` → `Optional[str]` (app.py:1377,1446; analytics.py:383; queue_manager.py:157,241); `limit`/`days` sin cota superior.

---

## FRONTEND (`D:\Videos_downloader\frontend`)

### 🔴 Crítico

- [ ] F1. No compila: `src/lib/api.ts` y `src/lib/utils.ts` se importan en toda la base pero no existen en git. Crear/commitear `lib/utils.ts` (`cn`) y `lib/api.ts` (cliente API tipado).
- [ ] F2. URLs hardcodeadas a `http://localhost:8000` (output-section.tsx:133,144,233,269; discover-section.tsx:103). Centralizar en `NEXT_PUBLIC_API_URL`.
- [ ] F3. Dockerfile copia `/app/.next/standalone` (Dockerfile:36-37) pero `next.config.ts` no declara `output: "standalone"`. Añadir la línea.

### 🟠 Alto

- [ ] F4. Progreso de jobs falso: salta a 30% hardcodeado y un único `await` de minutos sin job id/polling/`AbortController` (index.tsx:183-189; video-processor.tsx:93-129). Implementar polling real del estado.
- [ ] F5. Estado `transcription` global compartido entre jobs (race, index.tsx:209-211). Usar `job.result.transcription` y eliminar el global.
- [ ] F6. Race en Preview sin `AbortController`/token de secuencia (index.tsx:106-121).
- [ ] F7. Toast casero sin cleanup ni solapamiento (index.tsx:80-83) + doble sistema (sonner montado y nunca usado, layout.tsx:39). Migrar a sonner, borrar ToastNotification.
- [ ] F8. ~700 líneas muertas/duplicadas en `src/components/dashboard/` (video-processor.tsx duplica index.tsx; header/stats-cards/file-list no se importan). Eliminar o consolidar.
- [ ] F9. `discover-section.tsx:103-139` no valida `response.ok` y cae a `generateMockVideos()` (videos falsos que rompen "Procesar"). Mostrar error real y quitar mocks.
- [ ] F10. Errores de polling invisibles (solo `console.error`: index.tsx:94-96, file-list.tsx:51-53, stats-cards.tsx:27-29). Mostrar estado de error; pausar con `document.visibilityState`.

### 🟡 Medio

- [ ] F11. `index.tsx` monolítico (487 líneas, ~20 useState, 25 props a InputSection). Agrupar opciones en `useReducer`/context; memoizar.
- [ ] F12. Tipado `any` (index.tsx:116,218; video-processor.tsx:123; discover-section.tsx:111). Tipar y usar `error instanceof Error`.
- [ ] F13. Sin validación real de URL (index.tsx:107,125). Validar formato/plataforma.
- [ ] F14. Límite mágico `5` duplicado (index.tsx:78, input-section.tsx:73). Extraer constante compartida.
- [ ] F15. `selectedJob` inconsistente tras borrar (index.tsx:75 vs processing-history.tsx:69).
- [ ] F16. IDs de job con `Date.now()` (index.tsx:140). Usar `crypto.randomUUID()`.
- [ ] F17. Manipulación directa del DOM en onError de imagen (discover-section.tsx:277-281). Usar estado `imgError` por ítem.
- [ ] F18. `<img>` en vez de `next/image` (input-section.tsx:121, discover-section.tsx:273) y `next.config.ts` con `hostname: '**'`. Restringir a CDNs reales.
- [ ] F19. Accesibilidad: labels sin `htmlFor`, botones icon-only sin `aria-label`, toast sin `aria-live`, resizer sin teclado/rol, filas sin `role="button"`, `select-none` global que impide copiar.
- [ ] F20. i18n inconsistente (inglés/español mezclados; `lang="en"` en layout.tsx:28). Unificar.

### 🟢 Bajo

- [ ] F21. Utilidades de formato duplicadas (output-section/file-list/discover-section). Extraer `lib/format.ts`.
- [ ] F22. Tema claro inexistente pero toggle presente (`.dark` == `:root`, globals.css:35-55). Implementar o quitar next-themes.
- [ ] F23. `alert()`/`confirm()` nativos en dashboard. Migrar a toasts/diálogos si se rescatan.
- [ ] F24. `speedFactor` sin usar (video-processor.tsx:59); `1.02` hardcodeado (index.tsx:175).
- [ ] F25. `processAsync()` promesa flotante (index.tsx:237). Marcar `void`.
- [ ] F26. Config: `lint` sin path, sin `typecheck`, sin tests/CI del front, `target: ES2017` (→ES2022), sin `reactStrictMode`, sin `.env.example`.
- [ ] F27. `window.open` sin `noopener,noreferrer` (discover-section.tsx:349, output-section.tsx:233,269).
- [ ] F28. Descarga cross-origin con `link.click()` ignora `download` (output-section.tsx:142-147); usar blob o `Content-Disposition`.
