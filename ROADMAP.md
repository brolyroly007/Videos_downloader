# ROADMAP consolidado — Mejoras de los 4 proyectos

> Línea de tiempo unificada para midword, Videos_downloader, docschat y trackbeat.
> Generado el 2026-06-28. Las fechas son orientativas (sprints de ~2 semanas).

---

## 🧭 Principio rector

Los 4 proyectos comparten la misma carencia: **buen producto, poca ingeniería de soporte**. Por eso el roadmap se ordena por la misma prioridad transversal en todos:

1. **Seguridad** (donde aplica: Videos_downloader, docschat) — bloqueante.
2. **Robustez/observabilidad** (logging, errores, fiabilidad).
3. **Tests + CI**.
4. **Features y escalado**.

---

## 📅 Línea de tiempo

### Fase 1 — Cimientos (Sprints 1-2 · Jul 2026)
*Objetivo: cerrar agujeros de seguridad y volver todo diagnosticable.*

| Proyecto | Entregable |
|----------|-----------|
| Videos_downloader | Gestión de secretos + JWT + rate limiting; eliminar `admin123` |
| docschat | Activar auth JWT + rate limiting en Redis + sanitizar errores |
| trackbeat | Logging estructurado + excepciones específicas + refactor `pathlib` |
| midword | Tema centralizado (`THEME`) + CI básico (validar sintaxis) |

### Fase 2 — Fiabilidad y pruebas (Sprints 3-4 · Ago 2026)
*Objetivo: que nada se rompa en silencio y los refactors sean seguros.*

| Proyecto | Entregable |
|----------|-----------|
| Videos_downloader | Celery+Redis, singleton de Whisper, tests ≥ 40% |
| docschat | Transacciones ChromaDB↔SQLite + comando `doctor`, caché de embeddings |
| trackbeat | Suite de tests del algoritmo + CI en windows-latest, type hints |
| midword | Capa de datos extraída + suite de tests + búsqueda indexada |

### Fase 3 — Cumplimiento, escalado y pulido (Sprints 5-6 · Sep 2026)
*Objetivo: producción y nuevas capacidades.*

| Proyecto | Entregable |
|----------|-----------|
| Videos_downloader | Modal legal + modo manual, observabilidad, streaming |
| docschat | Búsqueda híbrida BM25+vectorial, fuentes remotas, ingesta con progreso |
| trackbeat | Streaming de archivos grandes, `settings.json`, validación de entrada |
| midword | Modo oscuro, recuperación ante crash, sincronización entre dispositivos |

---

## 🎯 Meta global Q3 2026

Al cerrar la Fase 3, los 4 repos cumplen:

- ✅ **CI verde** en cada push.
- ✅ **Cobertura ≥ 40%** en los módulos críticos.
- ✅ **Cero secretos** en el código (escaneo en CI).
- ✅ **Errores observables** (logging estructurado en los que hoy no lo tienen).
- ✅ **Tags de versión** y releases reproducibles.

---

## ⏱️ Esfuerzo estimado por proyecto (top mejoras)

| Proyecto | Esfuerzo total estimado | Devs sugeridos |
|----------|-------------------------|----------------|
| midword | ~10-14 días | 1 |
| Videos_downloader | ~40-60 h (≈1 semana) | 2 |
| docschat | ~40-60 h (≈1 semana) | 2 |
| trackbeat | ~20-30 h | 1 |

> Total aproximado del programa completo: **6-8 semanas** con 1-2 devs rotando entre proyectos.
