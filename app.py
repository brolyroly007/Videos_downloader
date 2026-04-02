"""
Main FastAPI Application
Dashboard para automatización de contenido viral
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from pathlib import Path
import os
import asyncio
import uuid
import time
from typing import Optional
import logging
from pydantic import BaseModel

# Importar módulos personalizados
from modules.downloader import VideoDownloader
from modules.video_processor import VideoProcessor
from modules.subtitle_generator import SubtitleGenerator
from modules.uploader import TikTokUploader
from modules.viral_detector import ViralDetector
from modules.automation_engine import AutomationEngine, AutomationDatabase, JobStatus
from modules.tiktok_discover import TikTokDiscovery, discover_videos
from modules.description_generator import DescriptionGenerator, generate_description
from modules.analytics import AnalyticsManager
from modules.queue_manager import QueueManager, JobPriority
from modules.hashtag_recommender import HashtagRecommender
from modules.backup_manager import BackupManager
from modules.auth import AuthManager, get_current_user, get_optional_user, require_role

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="Viral Content Automation Dashboard",
    description="Automatiza la descarga, edición y subida de contenido viral",
    version="1.0.0"
)

# Configurar CORS para permitir el frontend React
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar rutas de archivos estáticos y templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Inicializar módulos
downloader = VideoDownloader("downloads")
processor = VideoProcessor("temp", "processed")
subtitle_gen = None  # Se inicializará bajo demanda
uploader = TikTokUploader("cookies")
viral_detector = ViralDetector()
automation_db = AutomationDatabase()
automation_engine = None  # Se inicializa bajo demanda
tiktok_discovery = TikTokDiscovery()  # Descubrimiento de TikTok con yt-dlp

# Nuevos módulos
description_gen = DescriptionGenerator()
analytics_manager = AnalyticsManager()
queue_manager = QueueManager(max_workers=3)
hashtag_recommender = HashtagRecommender()
backup_manager = BackupManager()
auth_manager = AuthManager(enabled=os.getenv("AUTH_ENABLED", "false").lower() == "true")

# Diccionario para almacenar el estado de las tareas
tasks_status = {}

TASK_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours

# --- Concurrency limiters ---
_download_semaphore = asyncio.Semaphore(3)   # max 3 concurrent downloads
_process_semaphore = asyncio.Semaphore(2)    # max 2 concurrent processing jobs


# --- Structured error responses ---

def _error_response(status_code: int, error_code: str, message: str, retryable: bool = False) -> JSONResponse:
    """Return a structured JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "retryable": retryable,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any unhandled exception and return a structured 500 response."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return _error_response(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        retryable=True,
    )


def _cleanup_old_tasks():
    """Remove tasks older than 24 hours to prevent memory leaks."""
    now = time.time()
    expired = [
        tid for tid, tdata in tasks_status.items()
        if now - tdata.get("created_at", now) > TASK_MAX_AGE_SECONDS
    ]
    for tid in expired:
        del tasks_status[tid]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired tasks from tasks_status")


# Modelos Pydantic
class VideoDownloadRequest(BaseModel):
    url: str
    custom_filename: Optional[str] = None


class VideoProcessRequest(BaseModel):
    video_path: str
    output_filename: str
    reframe: bool = True
    background_type: str = "blur"  # "blur" o "solid"
    background_color: str = "#000000"  # Hex color
    apply_mirror: bool = True
    apply_speed: bool = True
    speed_factor: float = 1.02
    apply_color_adjust: bool = True
    generate_subtitles: bool = True
    subtitle_language: Optional[str] = "es"
    burn_subtitles: bool = True


class UploadRequest(BaseModel):
    video_path: str
    description: str
    headless: bool = False


class CompleteFlowRequest(BaseModel):
    url: str
    description: str
    reframe: bool = True
    background_type: str = "blur"
    background_color: str = "#000000"
    apply_mirror: bool = True
    apply_speed: bool = True
    speed_factor: float = 1.02
    generate_subtitles: bool = True
    subtitle_language: Optional[str] = "es"
    burn_subtitles: bool = True
    auto_upload: bool = False


# Función para convertir hex a RGB
def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# Rutas
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Página principal del dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/info")
async def get_info():
    """Información de la API"""
    return {
        "app": "Viral Content Automation Dashboard",
        "version": "1.0.0",
        "modules": {
            "downloader": "Ready",
            "processor": "Ready",
            "subtitle_generator": "Ready (Whisper)",
            "uploader": "Ready (TikTok)"
        }
    }


@app.post("/api/download")
async def download_video_endpoint(request: VideoDownloadRequest):
    """Descarga un video desde una URL"""
    if _download_semaphore.locked():
        return _error_response(
            429, "TOO_MANY_DOWNLOADS",
            "Maximum concurrent downloads reached. Try again later.",
            retryable=True,
        )
    async with _download_semaphore:
        try:
            logger.info(f"Downloading video from: {request.url}")
            result = downloader.download(request.url, request.custom_filename)

            if result['success']:
                return JSONResponse({
                    "success": True,
                    "message": "Video downloaded successfully",
                    "data": result
                })
            else:
                raise HTTPException(status_code=400, detail=result.get('error', 'Unknown error'))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in download endpoint: {e}", exc_info=True)
            return _error_response(500, "DOWNLOAD_FAILED", f"Failed to download video: {e}", retryable=True)


@app.post("/api/process")
async def process_video_endpoint(request: VideoProcessRequest):
    """Procesa un video con efectos y subtítulos"""
    if _process_semaphore.locked():
        return _error_response(
            429, "TOO_MANY_PROCESSING",
            "Maximum concurrent processing jobs reached. Try again later.",
            retryable=True,
        )
    await _process_semaphore.acquire()
    try:
        logger.info(f"Processing video: {request.video_path}")

        # Verificar que el archivo existe
        if not os.path.exists(request.video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Convertir color hex a RGB
        bg_color = hex_to_rgb(request.background_color)

        # Procesar video (sin subtítulos primero)
        processed_video = processor.process_video(
            video_path=request.video_path,
            output_filename=request.output_filename,
            reframe=request.reframe,
            background_type=request.background_type,
            background_color=bg_color,
            apply_mirror=request.apply_mirror,
            apply_speed=request.apply_speed,
            speed_factor=request.speed_factor,
            apply_color_adjust=request.apply_color_adjust
        )

        result = {
            "video_path": processed_video,
            "subtitles_generated": False
        }

        # Generar subtítulos si se solicita
        if request.generate_subtitles:
            logger.info("Generating subtitles...")

            # Inicializar generador de subtítulos (carga Whisper)
            global subtitle_gen
            if subtitle_gen is None:
                subtitle_gen = SubtitleGenerator(model_size="base")

            # Generar nombre de archivo para video con subs y archivo SRT
            base_name = Path(request.output_filename).stem
            video_with_subs = str(processor.output_path / f"{base_name}_with_subs.mp4")
            srt_file = str(processor.output_path / f"{base_name}.srt")

            # Procesar con subtítulos
            sub_result = subtitle_gen.process_video_with_subtitles(
                video_path=processed_video,
                output_video_path=video_with_subs,
                output_srt_path=srt_file,
                language=request.subtitle_language,
                burn_subs=request.burn_subtitles,
                font_size=70,
                font_color='yellow',
                stroke_color='black',
                stroke_width=4
            )

            result.update({
                "video_path": sub_result['video_path'] if request.burn_subtitles else processed_video,
                "srt_path": sub_result['srt_path'],
                "transcription": sub_result['transcription'],
                "language": sub_result['language'],
                "subtitles_generated": True
            })

        return JSONResponse({
            "success": True,
            "message": "Video processed successfully",
            "data": result
        })

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"File not found in process endpoint: {e}")
        return _error_response(404, "FILE_NOT_FOUND", f"Video file not found: {e}", retryable=False)
    except Exception as e:
        logger.error(f"Error in process endpoint: {e}", exc_info=True)
        return _error_response(500, "PROCESSING_FAILED", f"Failed to process video: {e}", retryable=True)
    finally:
        _process_semaphore.release()


@app.post("/api/upload")
async def upload_video_endpoint(request: UploadRequest):
    """Sube un video a TikTok"""
    try:
        logger.info(f"Uploading video to TikTok: {request.video_path}")

        # Verificar que el archivo existe
        if not os.path.exists(request.video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Subir a TikTok
        result = await uploader.upload_video(
            video_path=request.video_path,
            description=request.description,
            headless=request.headless
        )

        if result['success']:
            return JSONResponse({
                "success": True,
                "message": result.get('message', 'Video uploaded successfully'),
                "data": result
            })
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Upload failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}", exc_info=True)
        return _error_response(500, "UPLOAD_FAILED", f"Failed to upload video: {e}", retryable=True)


@app.post("/api/complete-flow")
async def complete_flow_endpoint(request: CompleteFlowRequest, background_tasks: BackgroundTasks):
    """Flujo completo: Descargar -> Procesar -> Subir"""
    # Check capacity for both stages before starting
    if _download_semaphore.locked():
        return _error_response(
            429, "TOO_MANY_DOWNLOADS",
            "Maximum concurrent downloads reached. Try again later.",
            retryable=True,
        )
    if _process_semaphore.locked():
        return _error_response(
            429, "TOO_MANY_PROCESSING",
            "Maximum concurrent processing jobs reached. Try again later.",
            retryable=True,
        )
    try:
        task_id = str(uuid.uuid4())
        _cleanup_old_tasks()
        tasks_status[task_id] = {
            "status": "started",
            "progress": "Downloading video...",
            "created_at": time.time(),
            "data": {}
        }

        logger.info(f"Starting complete flow [Task: {task_id}]")

        # 1. Descargar video
        logger.info("Step 1: Downloading...")
        await _download_semaphore.acquire()
        try:
            def _on_download_progress(info):
                tasks_status[task_id]["download_progress"] = info
                pct = info.get("percent", 0)
                spd = info.get("speed_mb", 0)
                tasks_status[task_id]["progress"] = f"Downloading... {pct}% ({spd} MB/s)"

            download_result = downloader.download(request.url, progress_callback=_on_download_progress)
        finally:
            _download_semaphore.release()

        if not download_result['success']:
            tasks_status[task_id] = {
                "status": "failed",
                "error": download_result.get('error', 'Download failed')
            }
            raise HTTPException(status_code=400, detail="Download failed")

        tasks_status[task_id]['progress'] = "Processing video..."
        video_path = download_result['filename']

        # 2. Procesar video
        logger.info("Step 2: Processing...")
        await _process_semaphore.acquire()
        try:
            bg_color = hex_to_rgb(request.background_color)
            output_filename = f"processed_{Path(video_path).name}"

            processed_video = processor.process_video(
                video_path=video_path,
                output_filename=output_filename,
                reframe=request.reframe,
                background_type=request.background_type,
                background_color=bg_color,
                apply_mirror=request.apply_mirror,
                apply_speed=request.apply_speed,
                speed_factor=request.speed_factor,
                apply_color_adjust=True
            )

            tasks_status[task_id]['data']['processed_video'] = processed_video

            # 3. Generar subtítulos (si se solicita)
            if request.generate_subtitles:
                tasks_status[task_id]['progress'] = "Generating subtitles..."
                logger.info("Step 3: Generating subtitles...")

                global subtitle_gen
                if subtitle_gen is None:
                    subtitle_gen = SubtitleGenerator(model_size="base")

                base_name = Path(output_filename).stem
                video_with_subs = str(processor.output_path / f"{base_name}_with_subs.mp4")
                srt_file = str(processor.output_path / f"{base_name}.srt")

                sub_result = subtitle_gen.process_video_with_subtitles(
                    video_path=processed_video,
                    output_video_path=video_with_subs,
                    output_srt_path=srt_file,
                    language=request.subtitle_language,
                    burn_subs=request.burn_subtitles,
                    font_size=70,
                    font_color='yellow',
                    stroke_color='black',
                    stroke_width=4
                )

                final_video = sub_result['video_path'] if request.burn_subtitles else processed_video
                tasks_status[task_id]['data'].update({
                    'final_video': final_video,
                    'srt_file': sub_result['srt_path'],
                    'transcription': sub_result['transcription']
                })
            else:
                final_video = processed_video
                tasks_status[task_id]['data']['final_video'] = final_video
        finally:
            _process_semaphore.release()

        # 4. Subir a TikTok (si auto_upload está activado)
        if request.auto_upload:
            tasks_status[task_id]['progress'] = "Uploading to TikTok..."
            logger.info("Step 4: Uploading to TikTok...")

            upload_result = await uploader.upload_video(
                video_path=final_video,
                description=request.description,
                headless=False
            )

            tasks_status[task_id]['data']['upload_result'] = upload_result

        tasks_status[task_id]['status'] = "completed"
        tasks_status[task_id]['progress'] = "All done!"

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Flow completed successfully",
            "data": tasks_status[task_id]['data']
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in complete flow: {e}", exc_info=True)
        tasks_status[task_id] = {
            "status": "failed",
            "error": str(e)
        }
        return _error_response(500, "PROCESSING_FAILED", f"Complete flow failed: {e}", retryable=True)


@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Obtiene el estado de una tarea"""
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")

    return JSONResponse(tasks_status[task_id])


@app.get("/api/video-info")
async def get_video_info(url: str):
    """Obtiene información de un video sin descargarlo"""
    try:
        result = downloader.get_video_info(url)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error getting video info: {e}", exc_info=True)
        return _error_response(500, "INVALID_URL", f"Failed to get video info: {e}", retryable=False)


@app.get("/api/files/downloads")
async def list_downloads():
    """Lista los videos descargados"""
    downloads_path = Path("downloads")
    files = []

    if downloads_path.exists():
        for file in downloads_path.iterdir():
            if file.is_file():
                files.append({
                    "name": file.name,
                    "path": str(file),
                    "size": file.stat().st_size,
                    "modified": file.stat().st_mtime
                })

    return JSONResponse({"files": files})


@app.get("/api/files/processed")
async def list_processed():
    """Lista los videos procesados"""
    processed_path = Path("processed")
    files = []

    if processed_path.exists():
        for file in processed_path.iterdir():
            if file.is_file() and file.suffix in ['.mp4', '.mov', '.avi']:
                files.append({
                    "name": file.name,
                    "path": str(file),
                    "size": file.stat().st_size,
                    "modified": file.stat().st_mtime
                })

    return JSONResponse({"files": files})


@app.delete("/api/clear-session")
async def clear_tiktok_session():
    """Elimina las cookies de sesión de TikTok"""
    try:
        await uploader.clear_session()
        return JSONResponse({"success": True, "message": "Session cleared"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DISCOVER ENDPOINTS - Videos de TikTok reales
# ============================================

@app.get("/api/discover/categories")
async def get_discover_categories():
    """
    Obtiene las categorías disponibles para descubrir videos
    """
    try:
        categories = tiktok_discovery.get_categories()
        return JSONResponse({
            "success": True,
            "categories": categories
        })
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/discover/{category}")
async def discover_by_category(
    category: str,
    limit: int = 12,
    sort_by: str = "predicted_viral",  # "predicted_viral", "viral_score", "recency", "engagement"
    min_hashtag_match: float = 0.0,    # Filtrar por mínimo match de hashtags (0-100)
    min_engagement: float = 0.0         # Filtrar por engagement mínimo
):
    """
    Descubre videos virales de TikTok por categoría usando yt-dlp
    Retorna videos reales con thumbnails y métricas predictivas de viralidad

    Query Parameters:
    - limit: Número máximo de videos (default: 12)
    - sort_by: Criterio de ordenamiento:
        - "predicted_viral": Potencial viral predictivo (RECOMENDADO para contenido emergente)
        - "viral_score": Score viral tradicional basado en views
        - "recency": Videos más recientes primero
        - "engagement": Mayor tasa de engagement primero
    - min_hashtag_match: Filtrar videos con al menos este % de match con hashtags de categoría (0-100)
    - min_engagement: Filtrar videos con al menos esta tasa de engagement
    """
    try:
        logger.info(f"Discovering videos for category: {category}, limit: {limit}, sort_by: {sort_by}")

        videos = await tiktok_discovery.discover_category(
            category_id=category,
            limit=limit,
            sort_by=sort_by,
            min_hashtag_match=min_hashtag_match,
            min_engagement=min_engagement
        )

        return JSONResponse({
            "success": True,
            "category": category,
            "count": len(videos),
            "sort_by": sort_by,
            "filters": {
                "min_hashtag_match": min_hashtag_match,
                "min_engagement": min_engagement
            },
            "videos": [v.to_dict() for v in videos]
        })
    except Exception as e:
        logger.error(f"Error discovering videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/discover/video/details")
async def get_video_details(url: str):
    """
    Obtiene detalles completos de un video específico de TikTok
    """
    try:
        video = await tiktok_discovery.get_video_details(url)

        if not video:
            raise HTTPException(status_code=404, detail="Could not get video details")

        return JSONResponse({
            "success": True,
            "video": video.to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting video details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# AUTOMATION ENDPOINTS - Detección de Virales
# ============================================

class ScanRequest(BaseModel):
    hashtags: list[str] = ["fyp", "viral", "trending"]
    limit: int = 20
    min_score: float = 40.0


class AddToQueueRequest(BaseModel):
    url: str
    auto_process: bool = True


class AutomationConfigRequest(BaseModel):
    min_viral_score: Optional[float] = None
    auto_process: Optional[bool] = None
    auto_upload: Optional[bool] = None
    process_subtitles: Optional[bool] = None
    subtitle_language: Optional[str] = None
    max_concurrent_jobs: Optional[int] = None


@app.post("/api/automation/scan")
async def scan_viral_videos(request: ScanRequest):
    """
    Escanea TikTok para encontrar videos virales
    """
    try:
        logger.info(f"Scanning hashtags: {request.hashtags}")
        all_videos = []

        for hashtag in request.hashtags:
            videos = await viral_detector.scrape_tiktok_trending(
                hashtag=hashtag,
                limit=request.limit // len(request.hashtags)
            )
            all_videos.extend(videos)

        # Filtrar por score mínimo
        filtered = [v for v in all_videos if v.viral_score >= request.min_score]

        # Ordenar por score
        filtered.sort(key=lambda v: v.viral_score, reverse=True)

        return JSONResponse({
            "success": True,
            "total_found": len(all_videos),
            "filtered_count": len(filtered),
            "videos": [v.to_dict() for v in filtered[:request.limit]]
        })

    except Exception as e:
        logger.error(f"Scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/automation/analyze")
async def analyze_video_url(url: str):
    """
    Analiza una URL específica y calcula su score de viralidad
    """
    try:
        video = await viral_detector.analyze_url(url)

        if not video:
            raise HTTPException(status_code=404, detail="Could not analyze video")

        return JSONResponse({
            "success": True,
            "video": video.to_dict(),
            "recommendation": "highly_viral" if video.viral_score >= 70 else
                             "viral" if video.viral_score >= 50 else
                             "moderate" if video.viral_score >= 30 else
                             "low_potential"
        })

    except Exception as e:
        logger.error(f"Analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/automation/queue/add")
async def add_to_queue(request: AddToQueueRequest):
    """
    Agrega un video a la cola de procesamiento
    """
    try:
        # Verificar si ya existe
        if automation_db.is_video_processed(request.url):
            return JSONResponse({
                "success": False,
                "error": "Video already in queue or processed"
            })

        # Analizar video
        video = await viral_detector.analyze_url(request.url)

        from modules.automation_engine import AutomationJob
        from datetime import datetime

        job = AutomationJob(
            id=f"job_{int(datetime.now().timestamp())}",
            video_url=request.url,
            platform=video.platform if video else 'unknown',
            viral_score=video.viral_score if video else 0,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
        )

        automation_db.add_job(job)

        return JSONResponse({
            "success": True,
            "job_id": job.id,
            "viral_score": job.viral_score,
            "status": job.status.value
        })

    except Exception as e:
        logger.error(f"Add to queue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/automation/queue")
async def get_queue():
    """
    Obtiene el estado de la cola de automatización
    """
    try:
        pending = automation_db.get_pending_jobs(limit=50)
        stats = automation_db.get_stats()

        return JSONResponse({
            "success": True,
            "stats": stats,
            "pending_jobs": [j.to_dict() for j in pending]
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/automation/stats")
async def get_automation_stats():
    """
    Obtiene estadísticas de automatización
    """
    try:
        stats = automation_db.get_stats(days=7)

        return JSONResponse({
            "success": True,
            "period": "7_days",
            "stats": stats
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/automation/config")
async def update_automation_config(request: AutomationConfigRequest):
    """
    Actualiza la configuración de automatización
    """
    global automation_engine

    if automation_engine is None:
        automation_engine = AutomationEngine()

    config_updates = {}
    if request.min_viral_score is not None:
        automation_engine.update_config('min_viral_score', request.min_viral_score)
        config_updates['min_viral_score'] = request.min_viral_score

    if request.auto_process is not None:
        automation_engine.update_config('auto_process', request.auto_process)
        config_updates['auto_process'] = request.auto_process

    if request.auto_upload is not None:
        automation_engine.update_config('auto_upload', request.auto_upload)
        config_updates['auto_upload'] = request.auto_upload

    if request.process_subtitles is not None:
        automation_engine.update_config('process_subtitles', request.process_subtitles)
        config_updates['process_subtitles'] = request.process_subtitles

    if request.subtitle_language is not None:
        automation_engine.update_config('subtitle_language', request.subtitle_language)
        config_updates['subtitle_language'] = request.subtitle_language

    if request.max_concurrent_jobs is not None:
        automation_engine.update_config('max_concurrent_jobs', request.max_concurrent_jobs)
        config_updates['max_concurrent_jobs'] = request.max_concurrent_jobs

    return JSONResponse({
        "success": True,
        "updated": config_updates,
        "current_config": automation_engine.config
    })


@app.post("/api/automation/start")
async def start_automation(background_tasks: BackgroundTasks):
    """
    Inicia el motor de automatización en background
    """
    global automation_engine

    if automation_engine is None:
        automation_engine = AutomationEngine()

    if automation_engine.is_running:
        return JSONResponse({
            "success": False,
            "message": "Automation already running"
        })

    # Iniciar en background
    background_tasks.add_task(automation_engine.start)

    return JSONResponse({
        "success": True,
        "message": "Automation engine started"
    })


@app.post("/api/automation/stop")
async def stop_automation():
    """
    Detiene el motor de automatización
    """
    global automation_engine

    if automation_engine is None or not automation_engine.is_running:
        return JSONResponse({
            "success": False,
            "message": "Automation not running"
        })

    await automation_engine.stop()

    return JSONResponse({
        "success": True,
        "message": "Automation engine stopped"
    })


# ============================================
# FLUJO AUTOMÁTICO COMPLETO
# Discover → Download → Process → Upload
# ============================================

class AutoFlowRequest(BaseModel):
    """Request para el flujo automático completo"""
    category: str = "funny"  # Categoría de videos a descubrir
    sort_by: str = "predicted_viral"  # Criterio de ordenamiento
    min_viral_potential: float = 50.0  # Mínimo potencial viral
    auto_upload: bool = False  # Si subir automáticamente a TikTok
    process_video: bool = True  # Si procesar el video (quitar marca de agua)
    max_videos: int = 1  # Cuántos videos procesar
    headless: bool = False  # Si el navegador debe ser headless (para upload)
    custom_description: Optional[str] = None  # Descripción personalizada


@app.post("/api/auto-flow")
async def auto_flow_endpoint(request: AutoFlowRequest, background_tasks: BackgroundTasks):
    """
    🚀 FLUJO AUTOMÁTICO COMPLETO:
    1. Descubre videos virales de TikTok
    2. Selecciona el mejor según potencial viral
    3. Lo descarga
    4. Lo procesa (quita marca de agua)
    5. Genera descripción viral
    6. Lo sube a TikTok (si auto_upload=true)

    ⚠️ IMPORTANTE: Para auto_upload, necesitas haber hecho login en TikTok
    al menos una vez usando /api/tiktok/login
    """
    task_id = str(uuid.uuid4())

    try:
        _cleanup_old_tasks()
        tasks_status[task_id] = {
            "status": "discovering",
            "progress": "Buscando videos virales...",
            "step": 1,
            "total_steps": 6 if request.auto_upload else 4,
            "created_at": time.time(),
            "data": {}
        }

        logger.info(f"[AutoFlow {task_id}] Starting - Category: {request.category}")

        # PASO 1: Descubrir videos virales
        logger.info(f"[AutoFlow {task_id}] Step 1: Discovering viral videos...")
        videos = await tiktok_discovery.discover_category(
            category_id=request.category,
            limit=10,  # Buscar 10 para elegir el mejor
            sort_by=request.sort_by
        )

        if not videos:
            tasks_status[task_id] = {
                "status": "error",
                "error": "No se encontraron videos virales"
            }
            return JSONResponse({
                "success": False,
                "task_id": task_id,
                "error": "No viral videos found for this category"
            })

        # Filtrar por potencial viral mínimo
        qualified_videos = [
            v for v in videos
            if v.predicted_viral_potential >= request.min_viral_potential
        ]

        if not qualified_videos:
            qualified_videos = videos[:request.max_videos]  # Tomar los mejores si ninguno califica

        selected_video = qualified_videos[0]  # El mejor video

        tasks_status[task_id]["data"]["discovered_video"] = {
            "url": selected_video.url,
            "title": selected_video.title,
            "author": selected_video.author,
            "views": selected_video.views,
            "viral_potential": selected_video.predicted_viral_potential,
            "engagement_rate": selected_video.engagement_rate
        }

        logger.info(f"[AutoFlow {task_id}] Selected video: {selected_video.title[:50]}... (Viral: {selected_video.predicted_viral_potential})")

        # PASO 2: Descargar el video
        tasks_status[task_id]["status"] = "downloading"
        tasks_status[task_id]["progress"] = f"Descargando video viral..."
        tasks_status[task_id]["step"] = 2

        def _on_viral_download_progress(info):
            tasks_status[task_id]["download_progress"] = info
            pct = info.get("percent", 0)
            spd = info.get("speed_mb", 0)
            tasks_status[task_id]["progress"] = f"Descargando video viral... {pct}% ({spd} MB/s)"

        logger.info(f"[AutoFlow {task_id}] Step 2: Downloading video...")
        download_result = downloader.download(selected_video.url,
                                              progress_callback=_on_viral_download_progress)

        if not download_result.get('success'):
            tasks_status[task_id] = {
                "status": "error",
                "error": f"Error descargando: {download_result.get('error', 'Unknown error')}"
            }
            return JSONResponse({
                "success": False,
                "task_id": task_id,
                "error": f"Download failed: {download_result.get('error')}"
            })

        # El downloader retorna 'filename' no 'file_path'
        downloaded_path = download_result.get('filename') or download_result.get('file_path')
        tasks_status[task_id]["data"]["downloaded_file"] = downloaded_path

        logger.info(f"[AutoFlow {task_id}] Downloaded to: {downloaded_path}")

        # PASO 3: Procesar video (quitar marca de agua)
        processed_path = downloaded_path  # Por defecto usar el original

        if request.process_video:
            tasks_status[task_id]["status"] = "processing"
            tasks_status[task_id]["progress"] = "Procesando video..."
            tasks_status[task_id]["step"] = 3

            logger.info(f"[AutoFlow {task_id}] Step 3: Processing video...")

            try:
                if video_processor:
                    process_result = await video_processor.process(
                        downloaded_path,
                        remove_watermark=True,
                        add_effects=False
                    )
                    if process_result.get('success'):
                        processed_path = process_result.get('output_path', downloaded_path)
                        tasks_status[task_id]["data"]["processed_file"] = processed_path
                        logger.info(f"[AutoFlow {task_id}] Processed: {processed_path}")
                    else:
                        logger.warning(f"[AutoFlow {task_id}] Processing failed, using original")
                else:
                    logger.warning(f"[AutoFlow {task_id}] VideoProcessor not available, using original")
            except Exception as proc_err:
                logger.warning(f"[AutoFlow {task_id}] Processing error: {proc_err}, using original")

        # PASO 4: Generar descripción viral
        tasks_status[task_id]["status"] = "generating_description"
        tasks_status[task_id]["progress"] = "Generando descripción viral..."
        tasks_status[task_id]["step"] = 4

        logger.info(f"[AutoFlow {task_id}] Step 4: Generating viral description...")

        if request.custom_description:
            final_description = request.custom_description
        else:
            try:
                desc_result = await description_gen.generate(
                    video_info={
                        "title": selected_video.title,
                        "category": request.category,
                        "hashtags": selected_video.hashtags
                    },
                    category=request.category,
                    language="es"
                )
                final_description = desc_result.full_description if hasattr(desc_result, 'full_description') else str(desc_result)
            except Exception as desc_err:
                logger.warning(f"[AutoFlow {task_id}] Description generation failed: {desc_err}")
                # Descripción por defecto
                hashtags = " ".join([f"#{h}" for h in selected_video.hashtags[:5]]) if selected_video.hashtags else "#viral #fyp #trending"
                final_description = f"🔥 {selected_video.title[:80]} {hashtags}"

        tasks_status[task_id]["data"]["description"] = final_description

        # PASO 5 & 6: Subir a TikTok (si está habilitado)
        if request.auto_upload:
            tasks_status[task_id]["status"] = "uploading"
            tasks_status[task_id]["progress"] = "Subiendo a TikTok..."
            tasks_status[task_id]["step"] = 5

            logger.info(f"[AutoFlow {task_id}] Step 5: Uploading to TikTok...")

            try:
                upload_result = await uploader.upload_video(
                    video_path=processed_path,
                    description=final_description,
                    headless=request.headless
                )

                tasks_status[task_id]["data"]["upload_result"] = upload_result

                if upload_result.get('success'):
                    tasks_status[task_id]["status"] = "completed"
                    tasks_status[task_id]["progress"] = "✅ Video subido exitosamente!"
                    tasks_status[task_id]["step"] = 6
                    logger.info(f"[AutoFlow {task_id}] Upload successful!")
                else:
                    tasks_status[task_id]["status"] = "upload_failed"
                    tasks_status[task_id]["progress"] = f"⚠️ Error en upload: {upload_result.get('error')}"
                    logger.error(f"[AutoFlow {task_id}] Upload failed: {upload_result.get('error')}")

            except Exception as upload_err:
                tasks_status[task_id]["status"] = "upload_failed"
                tasks_status[task_id]["data"]["upload_error"] = str(upload_err)
                logger.error(f"[AutoFlow {task_id}] Upload error: {upload_err}")
        else:
            tasks_status[task_id]["status"] = "ready_to_upload"
            tasks_status[task_id]["progress"] = "✅ Video listo para subir manualmente"

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Auto-flow completed" if not request.auto_upload else "Video uploaded!",
            "data": tasks_status[task_id]["data"],
            "video_ready": processed_path,
            "description": final_description
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AutoFlow {task_id}] Error: {e}", exc_info=True)
        tasks_status[task_id] = {
            "status": "error",
            "error": str(e)
        }
        return _error_response(500, "PROCESSING_FAILED", f"Auto-flow failed: {e}", retryable=True)


@app.post("/api/tiktok/login")
async def tiktok_login_endpoint():
    """
    🔐 Abre el navegador para hacer login en TikTok manualmente.
    Las cookies se guardarán para futuros uploads automáticos.

    Solo necesitas hacer esto UNA VEZ.
    """
    try:
        from playwright.async_api import async_playwright

        logger.info("Opening browser for TikTok login...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = await context.new_page()

            # Ir a login de TikTok
            await page.goto("https://www.tiktok.com/login")

            logger.info("Waiting for manual login (max 5 minutes)...")

            # Esperar a que el usuario haga login
            login_success = await uploader.wait_for_manual_login(page, timeout=300000)

            if login_success:
                await uploader.save_cookies(page)
                await browser.close()
                return JSONResponse({
                    "success": True,
                    "message": "Login exitoso! Cookies guardadas. Ahora puedes usar auto_upload=true"
                })
            else:
                await browser.close()
                return JSONResponse({
                    "success": False,
                    "message": "Login timeout o cancelado"
                })

    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tiktok/session-status")
async def check_tiktok_session():
    """Verifica si hay una sesión activa de TikTok"""
    cookies_file = Path("cookies") / "tiktok_cookies.json"

    if cookies_file.exists():
        import json
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)

            # Verificar si las cookies son válidas (tienen session)
            has_session = any(
                c.get('name') in ['sessionid', 'sessionid_ss', 'sid_tt']
                for c in cookies
            )

            return JSONResponse({
                "success": True,
                "session_exists": True,
                "session_valid": has_session,
                "message": "Sesión encontrada" if has_session else "Cookies existen pero sesión puede haber expirado",
                "cookies_count": len(cookies)
            })
        except Exception as e:
            return JSONResponse({
                "success": False,
                "session_exists": False,
                "error": str(e)
            })
    else:
        return JSONResponse({
            "success": True,
            "session_exists": False,
            "message": "No hay sesión. Usa POST /api/tiktok/login para iniciar sesión"
        })


# Servir archivos de video
@app.get("/files/downloads/{filename}")
async def serve_download(filename: str):
    """Sirve archivos descargados"""
    file_path = Path("downloads") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/files/processed/{filename}")
async def serve_processed(filename: str):
    """Sirve archivos procesados"""
    file_path = Path("processed") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ============================================
# DESCRIPTION GENERATOR ENDPOINTS
# ============================================

class DescriptionRequest(BaseModel):
    video_info: dict = {}
    category: str = "default"
    language: str = "es"


@app.post("/api/description/generate")
async def generate_video_description(request: DescriptionRequest):
    """Genera una descripción viral para un video"""
    try:
        result = await description_gen.generate(
            video_info=request.video_info,
            category=request.category,
            language=request.language
        )
        return JSONResponse({
            "success": True,
            "description": result.to_dict()
        })
    except Exception as e:
        logger.error(f"Error generating description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/description/hashtags/{category}")
async def get_trending_hashtags(category: str, limit: int = 20):
    """Obtiene hashtags trending para una categoría"""
    hashtags = description_gen.get_trending_hashtags(category, limit)
    return JSONResponse({
        "success": True,
        "category": category,
        "hashtags": hashtags
    })


# ============================================
# HASHTAG RECOMMENDER ENDPOINTS
# ============================================

class HashtagRequest(BaseModel):
    category: str = "general"
    video_title: str = ""
    max_hashtags: int = 15


@app.post("/api/hashtags/recommend")
async def recommend_hashtags(request: HashtagRequest):
    """Recomienda hashtags para un video"""
    result = hashtag_recommender.recommend(
        category=request.category,
        video_title=request.video_title,
        max_hashtags=request.max_hashtags
    )
    return JSONResponse({
        "success": True,
        "recommendation": result
    })


@app.get("/api/hashtags/trending")
async def get_trending_hashtags_list(limit: int = 30):
    """Obtiene los hashtags más trending"""
    hashtags = hashtag_recommender.get_trending_now(limit)
    return JSONResponse({
        "success": True,
        "hashtags": hashtags
    })


@app.get("/api/hashtags/category/{category}")
async def get_hashtags_by_category(category: str, limit: int = 20):
    """Obtiene hashtags por categoría"""
    hashtags = hashtag_recommender.get_by_category(category, limit)
    return JSONResponse({
        "success": True,
        "category": category,
        "hashtags": hashtags
    })


@app.post("/api/hashtags/analyze")
async def analyze_hashtags(hashtags: list[str]):
    """Analiza una lista de hashtags"""
    analysis = hashtag_recommender.analyze_hashtags(hashtags)
    return JSONResponse({
        "success": True,
        "analysis": analysis
    })


# ============================================
# ANALYTICS ENDPOINTS
# ============================================

@app.get("/api/analytics/dashboard")
async def get_analytics_dashboard():
    """Obtiene todos los datos del dashboard de analytics"""
    data = analytics_manager.get_dashboard_data()
    return JSONResponse({
        "success": True,
        "data": data
    })


@app.get("/api/analytics/stats")
async def get_overall_analytics():
    """Obtiene estadísticas generales"""
    stats = analytics_manager.db.get_overall_stats()
    return JSONResponse({
        "success": True,
        "stats": stats.to_dict()
    })


@app.get("/api/analytics/daily")
async def get_daily_analytics(days: int = 7):
    """Obtiene estadísticas diarias"""
    daily = analytics_manager.db.get_daily_stats(days)
    return JSONResponse({
        "success": True,
        "daily_stats": [d.to_dict() for d in daily]
    })


@app.get("/api/analytics/videos")
async def get_recent_videos_analytics(limit: int = 20, category: str = None, status: str = None):
    """Obtiene videos recientes con analytics"""
    videos = analytics_manager.db.get_recent_videos(limit, category, status)
    return JSONResponse({
        "success": True,
        "videos": [v.to_dict() for v in videos]
    })


@app.get("/api/analytics/categories")
async def get_category_analytics():
    """Obtiene estadísticas por categoría"""
    by_category = analytics_manager.db.get_category_stats()
    return JSONResponse({
        "success": True,
        "categories": by_category
    })


# ============================================
# QUEUE MANAGER ENDPOINTS
# ============================================

class QueueJobRequest(BaseModel):
    url: str
    platform: str = "unknown"
    title: str = ""
    category: str = "default"
    priority: str = "normal"  # low, normal, high, urgent
    options: dict = {}


@app.post("/api/queue/add")
async def add_to_queue(request: QueueJobRequest):
    """Agrega un video a la cola de procesamiento"""
    priority_map = {
        "low": JobPriority.LOW,
        "normal": JobPriority.NORMAL,
        "high": JobPriority.HIGH,
        "urgent": JobPriority.URGENT
    }

    job_id = queue_manager.add_job(
        url=request.url,
        platform=request.platform,
        title=request.title,
        category=request.category,
        priority=priority_map.get(request.priority, JobPriority.NORMAL),
        options=request.options
    )

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "message": "Video agregado a la cola"
    })


@app.get("/api/queue/status")
async def get_queue_status():
    """Obtiene el estado de la cola"""
    status = queue_manager.get_queue_status()
    return JSONResponse({
        "success": True,
        "status": status
    })


@app.get("/api/queue/jobs")
async def get_queue_jobs(status: str = None, limit: int = 50):
    """Obtiene los trabajos en la cola"""
    jobs = queue_manager.get_all_jobs(status, limit)
    return JSONResponse({
        "success": True,
        "jobs": jobs
    })


@app.get("/api/queue/job/{job_id}")
async def get_job_details(job_id: str):
    """Obtiene detalles de un trabajo específico"""
    job = queue_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({
        "success": True,
        "job": job
    })


@app.delete("/api/queue/job/{job_id}")
async def cancel_queue_job(job_id: str):
    """Cancela un trabajo en cola"""
    success = queue_manager.cancel_job(job_id)
    return JSONResponse({
        "success": success,
        "message": "Job cancelado" if success else "No se pudo cancelar el job"
    })


# ============================================
# BACKUP ENDPOINTS
# ============================================

@app.post("/api/backup/create")
async def create_backup(include_videos: bool = False):
    """Crea un backup manual"""
    result = backup_manager.create_backup(include_videos)
    return JSONResponse(result)


@app.get("/api/backup/list")
async def list_backups():
    """Lista todos los backups disponibles"""
    backups = backup_manager.list_backups()
    return JSONResponse({
        "success": True,
        "backups": backups
    })


@app.get("/api/backup/{backup_name}")
async def get_backup_info(backup_name: str):
    """Obtiene información de un backup"""
    info = backup_manager.get_backup_info(backup_name)
    if not info:
        raise HTTPException(status_code=404, detail="Backup not found")
    return JSONResponse({
        "success": True,
        "backup": info
    })


@app.post("/api/backup/restore/{backup_name}")
async def restore_backup(backup_name: str, restore_dbs: bool = True, restore_dirs: bool = True):
    """Restaura un backup"""
    result = backup_manager.restore_backup(backup_name, restore_dbs, restore_dirs)
    return JSONResponse(result)


@app.delete("/api/backup/{backup_name}")
async def delete_backup(backup_name: str):
    """Elimina un backup"""
    success = backup_manager.delete_backup(backup_name)
    return JSONResponse({
        "success": success,
        "message": "Backup eliminado" if success else "No se pudo eliminar"
    })


@app.get("/api/backup/stats")
async def get_backup_stats():
    """Obtiene estadísticas de backups"""
    stats = backup_manager.get_backup_stats()
    return JSONResponse({
        "success": True,
        "stats": stats
    })


# ============================================
# AUTH ENDPOINTS
# ============================================

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


@app.post("/api/auth/login")
async def login(request: LoginRequest, req: Request):
    """Inicia sesión"""
    ip = req.client.host if req.client else ""
    user_agent = req.headers.get("user-agent", "")

    result = auth_manager.login(request.username, request.password, ip, user_agent)
    return JSONResponse(result)


@app.post("/api/auth/logout")
async def logout(req: Request):
    """Cierra sesión"""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = req.headers.get("X-Auth-Token", "")

    result = auth_manager.logout(token)
    return JSONResponse(result)


@app.get("/api/auth/me")
async def get_current_user_info(req: Request):
    """Obtiene información del usuario actual"""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = req.headers.get("X-Auth-Token", "")

    user = auth_manager.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    return JSONResponse({
        "success": True,
        "user": user.to_dict()
    })


@app.post("/api/auth/change-password")
async def change_password(request: ChangePasswordRequest, req: Request):
    """Cambia la contraseña del usuario actual"""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth_manager.validate_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    success = auth_manager.change_password(user.id, request.old_password, request.new_password)

    if success:
        return JSONResponse({"success": True, "message": "Contraseña actualizada"})
    else:
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")


@app.post("/api/auth/users")
async def create_user(request: CreateUserRequest):
    """Crea un nuevo usuario (solo admin)"""
    # En producción, verificar que el usuario actual es admin
    user = auth_manager.create_user(request.username, request.password, request.role)
    return JSONResponse({
        "success": True,
        "user": user
    })


@app.get("/api/auth/users")
async def list_users():
    """Lista todos los usuarios (solo admin)"""
    users = auth_manager.get_all_users()
    return JSONResponse({
        "success": True,
        "users": users
    })


if __name__ == "__main__":
    import uvicorn

    # Crear directorios necesarios si no existen
    for directory in ["downloads", "processed", "temp", "cookies", "static", "templates", "cache"]:
        Path(directory).mkdir(exist_ok=True)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    logger.info("Starting Viral Content Automation Dashboard...")
    logger.info(f"Access the dashboard at: http://localhost:{port}")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
