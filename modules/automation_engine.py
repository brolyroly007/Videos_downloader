"""
Automation Engine - Motor de automatización masiva
Coordina detección, procesamiento y publicación de videos virales
"""

import asyncio
import os
import json
import uuid
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import random

from modules.viral_detector import ViralDetector, ViralVideo
from modules.downloader import VideoDownloader
from modules.video_processor import VideoProcessor
from modules.subtitle_generator import SubtitleGenerator
from modules.uploader import TikTokUploader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    DETECTING = "detecting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    GENERATING_SUBS = "generating_subs"
    SCHEDULED = "scheduled"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AutomationJob:
    """Representa un trabajo de automatización"""
    id: str
    video_url: str
    platform: str
    viral_score: float
    status: JobStatus
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    local_video_path: Optional[str] = None
    processed_video_path: Optional[str] = None
    transcription: Optional[str] = None
    tiktok_description: Optional[str] = None
    upload_result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> dict:
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if self.scheduled_at:
            data['scheduled_at'] = self.scheduled_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class AutomationDatabase:
    """Base de datos SQLite para tracking de automatización"""

    def __init__(self, db_path: str = "automation.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa las tablas de la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de videos procesados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_videos (
                id TEXT PRIMARY KEY,
                video_url TEXT UNIQUE,
                platform TEXT,
                viral_score REAL,
                status TEXT,
                created_at TEXT,
                scheduled_at TEXT,
                completed_at TEXT,
                local_video_path TEXT,
                processed_video_path TEXT,
                transcription TEXT,
                tiktok_description TEXT,
                upload_result TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0
            )
        ''')

        # Tabla de métricas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                videos_detected INTEGER,
                videos_processed INTEGER,
                videos_uploaded INTEGER,
                videos_failed INTEGER,
                total_views INTEGER,
                total_likes INTEGER
            )
        ''')

        # Tabla de configuración
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Tabla de cuentas TikTok (para rotación)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiktok_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                cookies_path TEXT,
                is_active INTEGER DEFAULT 1,
                last_upload TEXT,
                uploads_today INTEGER DEFAULT 0,
                daily_limit INTEGER DEFAULT 5
            )
        ''')

        conn.commit()
        conn.close()

    def add_job(self, job: AutomationJob) -> bool:
        """Agrega un nuevo job a la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO processed_videos
                (id, video_url, platform, viral_score, status, created_at,
                 scheduled_at, local_video_path, processed_video_path,
                 transcription, tiktok_description, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job.id, job.video_url, job.platform, job.viral_score,
                job.status.value, job.created_at.isoformat(),
                job.scheduled_at.isoformat() if job.scheduled_at else None,
                job.local_video_path, job.processed_video_path,
                job.transcription, job.tiktok_description, job.retry_count
            ))

            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error adding job: {e}")
            return False

    def update_job(self, job: AutomationJob):
        """Actualiza un job existente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE processed_videos SET
                status = ?,
                scheduled_at = ?,
                completed_at = ?,
                local_video_path = ?,
                processed_video_path = ?,
                transcription = ?,
                tiktok_description = ?,
                upload_result = ?,
                error = ?,
                retry_count = ?
            WHERE id = ?
        ''', (
            job.status.value,
            job.scheduled_at.isoformat() if job.scheduled_at else None,
            job.completed_at.isoformat() if job.completed_at else None,
            job.local_video_path,
            job.processed_video_path,
            job.transcription,
            job.tiktok_description,
            json.dumps(job.upload_result) if job.upload_result else None,
            job.error,
            job.retry_count,
            job.id
        ))

        conn.commit()
        conn.close()

    def is_video_processed(self, video_url: str) -> bool:
        """Verifica si un video ya fue procesado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id FROM processed_videos WHERE video_url = ?',
            (video_url,)
        )
        result = cursor.fetchone()
        conn.close()

        return result is not None

    def get_pending_jobs(self, limit: int = 10) -> List[AutomationJob]:
        """Obtiene jobs pendientes de procesar"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM processed_videos
            WHERE status IN ('pending', 'scheduled')
            AND (scheduled_at IS NULL OR scheduled_at <= ?)
            ORDER BY viral_score DESC
            LIMIT ?
        ''', (datetime.now().isoformat(), limit))

        jobs = []
        for row in cursor.fetchall():
            jobs.append(self._row_to_job(row))

        conn.close()
        return jobs

    def get_stats(self, days: int = 7) -> Dict:
        """Obtiene estadísticas de los últimos N días"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(viral_score) as avg_score
            FROM processed_videos
            WHERE created_at >= ?
        ''', (since,))

        row = cursor.fetchone()
        conn.close()

        return {
            'total': row[0] or 0,
            'completed': row[1] or 0,
            'failed': row[2] or 0,
            'avg_viral_score': row[3] or 0
        }

    def _row_to_job(self, row) -> AutomationJob:
        """Convierte una fila de BD a AutomationJob"""
        return AutomationJob(
            id=row[0],
            video_url=row[1],
            platform=row[2],
            viral_score=row[3],
            status=JobStatus(row[4]),
            created_at=datetime.fromisoformat(row[5]),
            scheduled_at=datetime.fromisoformat(row[6]) if row[6] else None,
            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
            local_video_path=row[8],
            processed_video_path=row[9],
            transcription=row[10],
            tiktok_description=row[11],
            upload_result=json.loads(row[12]) if row[12] else None,
            error=row[13],
            retry_count=row[14] or 0
        )


class ScheduleManager:
    """
    Gestiona la programación de publicaciones para evitar detección de spam
    """

    def __init__(self):
        # Horarios óptimos de publicación (hora local)
        self.optimal_hours = [
            7, 8, 9,      # Mañana
            12, 13,       # Mediodía
            17, 18, 19,   # Tarde
            21, 22, 23    # Noche
        ]

        # Límites de publicación
        self.max_uploads_per_hour = 2
        self.max_uploads_per_day = 10
        self.min_interval_minutes = 30

        self.last_upload_time: Optional[datetime] = None
        self.uploads_today: int = 0
        self.uploads_this_hour: int = 0

    def get_next_slot(self) -> datetime:
        """Calcula el próximo slot disponible para publicar"""
        now = datetime.now()

        # Resetear contadores si es nuevo día/hora
        if self.last_upload_time:
            if self.last_upload_time.date() != now.date():
                self.uploads_today = 0
            if self.last_upload_time.hour != now.hour:
                self.uploads_this_hour = 0

        # Verificar límites
        if self.uploads_today >= self.max_uploads_per_day:
            # Programar para mañana
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(
                hour=self.optimal_hours[0],
                minute=random.randint(0, 30),
                second=0
            )

        # Calcular siguiente slot
        next_slot = now

        # Respetar intervalo mínimo
        if self.last_upload_time:
            min_next = self.last_upload_time + timedelta(minutes=self.min_interval_minutes)
            if min_next > next_slot:
                next_slot = min_next

        # Ajustar a hora óptima si es necesario
        if next_slot.hour not in self.optimal_hours:
            # Buscar próxima hora óptima
            for hour in self.optimal_hours:
                if hour > next_slot.hour:
                    next_slot = next_slot.replace(
                        hour=hour,
                        minute=random.randint(0, 30)
                    )
                    break
            else:
                # Siguiente día
                next_slot = next_slot + timedelta(days=1)
                next_slot = next_slot.replace(
                    hour=self.optimal_hours[0],
                    minute=random.randint(0, 30)
                )

        # Agregar variación aleatoria para parecer más natural
        next_slot = next_slot + timedelta(minutes=random.randint(0, 10))

        return next_slot

    def record_upload(self):
        """Registra una publicación realizada"""
        self.last_upload_time = datetime.now()
        self.uploads_today += 1
        self.uploads_this_hour += 1


class TikTokDescriptionGenerator:
    """Genera descripciones optimizadas para TikTok (uso interno del engine).

    Distinto de modules.description_generator.DescriptionGenerator, que es
    async y devuelve un dataclass; esta versión es síncrona y devuelve str.
    """

    def __init__(self):
        # Hashtags por categoría
        self.hashtags = {
            'viral': ['#fyp', '#viral', '#foryou', '#trending', '#parati'],
            'engagement': ['#duet', '#stitch', '#reply', '#pov'],
            'niches': {
                'humor': ['#funny', '#comedy', '#meme', '#humor'],
                'lifestyle': ['#lifestyle', '#aesthetic', '#vibes'],
                'motivation': ['#motivation', '#inspiration', '#mindset'],
            }
        }

        # Templates de descripciones
        self.templates = [
            "{caption} {hashtags}",
            "Wait for it... {hashtags}",
            "POV: {caption} {hashtags}",
            "This is insane {hashtags}",
            "{hashtags}",
        ]

    def generate(
        self,
        original_title: str = "",
        niche: str = "general",
        include_cta: bool = True
    ) -> str:
        """Genera una descripción optimizada"""

        # Seleccionar hashtags
        tags = self.hashtags['viral'].copy()
        tags.extend(random.sample(self.hashtags['engagement'], 2))

        if niche in self.hashtags['niches']:
            tags.extend(self.hashtags['niches'][niche])

        # Limitar a 5-7 hashtags
        tags = random.sample(tags, min(len(tags), 6))
        hashtags_str = ' '.join(tags)

        # Generar caption
        if original_title:
            caption = original_title[:50]
        else:
            caption = ""

        # Seleccionar template
        template = random.choice(self.templates)
        description = template.format(caption=caption, hashtags=hashtags_str)

        # Agregar CTA
        if include_cta:
            ctas = [
                "\n\nFollow for more!",
                "\n\nLike if you agree!",
                "\n\nSave this!",
                "\n\nShare with a friend!",
            ]
            description += random.choice(ctas)

        return description.strip()


class AutomationEngine:
    """
    Motor principal de automatización

    Flujo:
    1. Detectar videos virales
    2. Filtrar duplicados y contenido no deseado
    3. Descargar videos
    4. Procesar (reframe, efectos, subtítulos)
    5. Programar publicación
    6. Subir a TikTok
    7. Registrar métricas
    """

    def __init__(
        self,
        downloads_dir: str = "downloads",
        processed_dir: str = "processed",
        cookies_dir: str = "cookies"
    ):
        # Componentes
        self.detector = ViralDetector()
        self.downloader = VideoDownloader(downloads_dir)
        self.processor = VideoProcessor("temp", processed_dir)
        self.subtitle_gen = None  # Lazy loading
        self.uploader = TikTokUploader(cookies_dir)

        # Managers
        self.db = AutomationDatabase()
        self.scheduler = ScheduleManager()
        self.desc_generator = TikTokDescriptionGenerator()

        # Configuración
        self.config = {
            'min_viral_score': 40,
            'auto_process': True,
            'auto_upload': False,  # Requiere confirmación manual por defecto
            'process_subtitles': True,
            'subtitle_language': 'es',
            'reframe_to_vertical': True,
            'apply_mirror': True,
            'apply_speed': True,
            'max_concurrent_jobs': 3,
        }

        # Estado
        self.is_running = False
        self.active_jobs: Dict[str, AutomationJob] = {}

    async def start(self):
        """Inicia el motor de automatización"""
        logger.info("🚀 Starting Automation Engine...")
        self.is_running = True

        # Iniciar tareas en paralelo
        await asyncio.gather(
            self._detection_loop(),
            self._processing_loop(),
            self._upload_loop(),
        )

    async def stop(self):
        """Detiene el motor"""
        logger.info("Stopping Automation Engine...")
        self.is_running = False
        await self.detector.close_browser()

    async def _detection_loop(self):
        """Loop de detección de videos virales"""
        while self.is_running:
            try:
                logger.info("🔍 Scanning for viral videos...")

                # Escanear videos trending
                videos = await self.detector.scrape_tiktok_discover(limit=30)

                new_count = 0
                for video in videos:
                    # Filtrar por score mínimo
                    if video.viral_score < self.config['min_viral_score']:
                        continue

                    # Verificar si ya existe
                    if self.db.is_video_processed(video.url):
                        continue

                    # Crear job
                    job = AutomationJob(
                        id=f"job_{video.video_id}_{uuid.uuid4().hex[:8]}",
                        video_url=video.url,
                        platform=video.platform,
                        viral_score=video.viral_score,
                        status=JobStatus.PENDING,
                        created_at=datetime.now(),
                    )

                    if self.db.add_job(job):
                        new_count += 1
                        logger.info(f"✅ New viral video queued: {video.title[:40]}... (score: {video.viral_score:.1f})")

                logger.info(f"Detection complete. {new_count} new videos queued.")

                # Esperar antes del próximo escaneo
                await asyncio.sleep(30 * 60)  # 30 minutos

            except Exception as e:
                logger.error(f"Detection error: {e}")
                await asyncio.sleep(5 * 60)  # Retry in 5 minutes

    async def _processing_loop(self):
        """Loop de procesamiento de videos"""
        while self.is_running:
            try:
                # Obtener jobs pendientes
                pending_jobs = self.db.get_pending_jobs(limit=self.config['max_concurrent_jobs'])

                if not pending_jobs:
                    await asyncio.sleep(60)
                    continue

                # Procesar en paralelo
                tasks = []
                for job in pending_jobs:
                    if job.id not in self.active_jobs:
                        tasks.append(self._process_job(job))

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                await asyncio.sleep(60)

    async def _process_job(self, job: AutomationJob):
        """Procesa un job individual"""
        self.active_jobs[job.id] = job

        try:
            logger.info(f"📥 Processing job: {job.id}")

            # 1. Descargar video
            job.status = JobStatus.DOWNLOADING
            self.db.update_job(job)

            loop = asyncio.get_event_loop()
            download_result = await loop.run_in_executor(
                None, lambda: self.downloader.download(job.video_url)
            )
            if not download_result['success']:
                raise Exception(f"Download failed: {download_result.get('error')}")

            job.local_video_path = download_result['filename']

            # 2. Procesar video
            job.status = JobStatus.PROCESSING
            self.db.update_job(job)

            output_filename = f"processed_{Path(job.local_video_path).stem}.mp4"
            processed_path = await loop.run_in_executor(
                None,
                lambda: self.processor.process_video(
                    video_path=job.local_video_path,
                    output_filename=output_filename,
                    reframe=self.config['reframe_to_vertical'],
                    background_type='blur',
                    apply_mirror=self.config['apply_mirror'],
                    apply_speed=self.config['apply_speed'],
                    speed_factor=1.02
                )
            )
            job.processed_video_path = processed_path

            # 3. Generar subtítulos (si está habilitado)
            if self.config['process_subtitles']:
                job.status = JobStatus.GENERATING_SUBS
                self.db.update_job(job)

                if self.subtitle_gen is None:
                    self.subtitle_gen = SubtitleGenerator(model_size="base")

                base_name = Path(output_filename).stem
                video_with_subs = str(Path("processed") / f"{base_name}_subs.mp4")
                srt_path = str(Path("processed") / f"{base_name}.srt")

                sub_result = await loop.run_in_executor(
                    None,
                    lambda: self.subtitle_gen.process_video_with_subtitles(
                        video_path=processed_path,
                        output_video_path=video_with_subs,
                        output_srt_path=srt_path,
                        language=self.config['subtitle_language'],
                        burn_subs=True
                    )
                )

                job.processed_video_path = sub_result['video_path']
                job.transcription = sub_result['transcription']

            # 4. Generar descripción
            job.tiktok_description = self.desc_generator.generate(
                original_title=job.transcription[:50] if job.transcription else "",
                niche="general"
            )

            # 5. Programar publicación
            job.scheduled_at = self.scheduler.get_next_slot()
            job.status = JobStatus.SCHEDULED
            self.db.update_job(job)

            logger.info(f"✅ Job {job.id} processed. Scheduled for: {job.scheduled_at}")

        except Exception as e:
            logger.error(f"❌ Job {job.id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.retry_count += 1
            self.db.update_job(job)

        finally:
            del self.active_jobs[job.id]

    async def _upload_loop(self):
        """Loop de publicación a TikTok"""
        while self.is_running:
            try:
                if not self.config['auto_upload']:
                    await asyncio.sleep(60)
                    continue

                # Buscar jobs programados listos para subir
                conn = sqlite3.connect(self.db.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM processed_videos
                    WHERE status = 'scheduled'
                    AND scheduled_at <= ?
                    ORDER BY scheduled_at ASC
                    LIMIT 1
                ''', (datetime.now().isoformat(),))

                row = cursor.fetchone()
                conn.close()

                if row:
                    job = self.db._row_to_job(row)
                    await self._upload_job(job)

                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Upload loop error: {e}")
                await asyncio.sleep(300)

    async def _upload_job(self, job: AutomationJob):
        """Sube un video a TikTok"""
        try:
            logger.info(f"📤 Uploading job: {job.id}")
            job.status = JobStatus.UPLOADING
            self.db.update_job(job)

            result = await self.uploader.upload_video(
                video_path=job.processed_video_path,
                description=job.tiktok_description,
                headless=os.getenv("TIKTOK_HEADLESS", "false").lower() == "true"
            )

            if result['success']:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                job.upload_result = result
                self.scheduler.record_upload()
                logger.info(f"✅ Upload successful: {job.id}")
            else:
                raise Exception(result.get('error', 'Upload failed'))

        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)

        finally:
            self.db.update_job(job)

    # API para control manual
    async def add_video_manually(self, url: str) -> AutomationJob:
        """Agrega un video manualmente a la cola"""
        video = await self.detector.analyze_url(url)

        job = AutomationJob(
            id=f"manual_{uuid.uuid4().hex[:12]}",
            video_url=url,
            platform=video.platform if video else 'unknown',
            viral_score=video.viral_score if video else 0,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
        )

        self.db.add_job(job)
        return job

    def get_queue_status(self) -> Dict:
        """Obtiene el estado de la cola"""
        stats = self.db.get_stats()
        pending = self.db.get_pending_jobs(limit=100)

        return {
            'stats': stats,
            'pending_count': len(pending),
            'active_jobs': len(self.active_jobs),
            'next_upload': self.scheduler.get_next_slot().isoformat(),
            'config': self.config
        }

    def update_config(self, key: str, value):
        """Actualiza configuración"""
        if key in self.config:
            self.config[key] = value
            logger.info(f"Config updated: {key} = {value}")


# CLI para pruebas
async def main():
    engine = AutomationEngine()

    print("🤖 Automation Engine Ready")
    print("\nCommands:")
    print("  scan    - Scan for viral videos")
    print("  add URL - Add video manually")
    print("  status  - Show queue status")
    print("  start   - Start automation")
    print("  quit    - Exit")

    while True:
        cmd = input("\n> ").strip().lower()

        if cmd == 'quit':
            break
        elif cmd == 'scan':
            videos = await engine.detector.scrape_tiktok_discover(limit=10)
            for v in videos:
                print(f"  [{v.viral_score:.0f}] {v.title[:50]}...")
        elif cmd.startswith('add '):
            url = cmd[4:].strip()
            job = await engine.add_video_manually(url)
            print(f"Added: {job.id}")
        elif cmd == 'status':
            status = engine.get_queue_status()
            print(json.dumps(status, indent=2, default=str))
        elif cmd == 'start':
            await engine.start()

    await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
