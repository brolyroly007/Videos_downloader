"""
Queue Manager Module
Sistema de colas para procesamiento paralelo de videos
"""

import asyncio
import sqlite3
import json
import logging
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import uuid
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    GENERATING_SUBS = "generating_subs"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueueJob:
    """Trabajo en la cola"""
    id: str
    url: str
    platform: str
    title: str
    category: str
    priority: int
    status: str
    progress: int
    message: str
    video_info: Dict
    options: Dict  # Opciones de procesamiento
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Dict]
    error: Optional[str]
    worker_id: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


class QueueDatabase:
    """Base de datos para la cola de trabajos"""

    def __init__(self, db_path: str = "queue.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                platform TEXT DEFAULT 'unknown',
                title TEXT,
                category TEXT DEFAULT 'default',
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'queued',
                progress INTEGER DEFAULT 0,
                message TEXT,
                video_info TEXT,
                options TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                result TEXT,
                error TEXT,
                worker_id TEXT
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)')

        conn.commit()
        conn.close()

    def add_job(self, job: QueueJob) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO jobs (id, url, platform, title, category, priority, status, progress, message, video_info, options, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job.id, job.url, job.platform, job.title, job.category,
            job.priority, job.status, job.progress, job.message,
            json.dumps(job.video_info), json.dumps(job.options), job.created_at
        ))

        conn.commit()
        conn.close()
        return job.id

    def get_next_job(self, worker_id: str) -> Optional[QueueJob]:
        """Obtiene el siguiente trabajo disponible (por prioridad).

        La reclamación es a prueba de carreras: si otro worker toma la fila
        entre el SELECT y el UPDATE, `rowcount` será 0 y se reintenta con la
        siguiente fila en cola en lugar de devolver un job ya tomado.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            while True:
                # Obtener trabajo con mayor prioridad que esté en cola
                cursor.execute('''
                    SELECT id, url, platform, title, category, priority, status, progress, message,
                           video_info, options, created_at, started_at, completed_at, result, error, worker_id
                    FROM jobs
                    WHERE status = 'queued'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                ''')

                row = cursor.fetchone()
                if not row:
                    return None

                # Intentar reclamar la fila de forma atómica
                started_at = datetime.now().isoformat()
                cursor.execute('''
                    UPDATE jobs SET status = 'downloading', worker_id = ?, started_at = ?
                    WHERE id = ? AND status = 'queued'
                ''', (worker_id, started_at, row[0]))
                conn.commit()

                if cursor.rowcount == 1:
                    job = self._row_to_job(row)
                    job.status = 'downloading'
                    job.worker_id = worker_id
                    job.started_at = started_at
                    return job
                # Otro worker la tomó primero; probar con la siguiente
        finally:
            conn.close()

    def update_job(self, job_id: str, status: str = None, progress: int = None,
                   message: str = None, result: Dict = None, error: str = None):
        """Actualiza el estado de un trabajo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status)
            if status in ['completed', 'failed', 'cancelled']:
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat())

        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)

        if message:
            updates.append("message = ?")
            params.append(message)

        if result:
            updates.append("result = ?")
            params.append(json.dumps(result))

        if error:
            updates.append("error = ?")
            params.append(error)

        if updates:
            params.append(job_id)
            cursor.execute(f'''
                UPDATE jobs SET {", ".join(updates)} WHERE id = ?
            ''', params)

        conn.commit()
        conn.close()

    def get_job(self, job_id: str) -> Optional[QueueJob]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, url, platform, title, category, priority, status, progress, message,
                   video_info, options, created_at, started_at, completed_at, result, error, worker_id
            FROM jobs WHERE id = ?
        ''', (job_id,))

        row = cursor.fetchone()
        conn.close()

        return self._row_to_job(row) if row else None

    def get_queue_status(self) -> Dict:
        """Obtiene estadísticas de la cola"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
        ''')

        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute('SELECT COUNT(*) FROM jobs')
        total = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "queued": by_status.get("queued", 0),
            "processing": by_status.get("downloading", 0) + by_status.get("processing", 0) + by_status.get("generating_subs", 0),
            "uploading": by_status.get("uploading", 0),
            "completed": by_status.get("completed", 0),
            "failed": by_status.get("failed", 0),
            "by_status": by_status
        }

    def get_all_jobs(self, status: str = None, limit: int = 50) -> List[QueueJob]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute('''
                SELECT id, url, platform, title, category, priority, status, progress, message,
                       video_info, options, created_at, started_at, completed_at, result, error, worker_id
                FROM jobs WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT id, url, platform, title, category, priority, status, progress, message,
                       video_info, options, created_at, started_at, completed_at, result, error, worker_id
                FROM jobs ORDER BY created_at DESC LIMIT ?
            ''', (limit,))

        jobs = [self._row_to_job(row) for row in cursor.fetchall()]
        conn.close()
        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancela un trabajo si está en cola"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE jobs SET status = 'cancelled', completed_at = ?
            WHERE id = ? AND status = 'queued'
        ''', (datetime.now().isoformat(), job_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def clear_completed(self, older_than_hours: int = 24):
        """Limpia trabajos completados antiguos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM jobs
            WHERE status IN ('completed', 'failed', 'cancelled')
            AND completed_at < datetime('now', ? || ' hours')
        ''', (f'-{older_than_hours}',))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def _row_to_job(self, row) -> QueueJob:
        return QueueJob(
            id=row[0],
            url=row[1],
            platform=row[2],
            title=row[3],
            category=row[4],
            priority=row[5],
            status=row[6],
            progress=row[7],
            message=row[8],
            video_info=json.loads(row[9]) if row[9] else {},
            options=json.loads(row[10]) if row[10] else {},
            created_at=row[11],
            started_at=row[12],
            completed_at=row[13],
            result=json.loads(row[14]) if row[14] else None,
            error=row[15],
            worker_id=row[16]
        )


class QueueWorker:
    """Worker que procesa trabajos de la cola"""

    def __init__(self, worker_id: str, db: QueueDatabase, processor_callback: Callable):
        self.worker_id = worker_id
        self.db = db
        self.processor = processor_callback
        self.running = False
        self._current_job: Optional[QueueJob] = None

    async def start(self):
        """Inicia el worker"""
        self.running = True
        logger.info(f"Worker {self.worker_id} started")

        while self.running:
            job = self.db.get_next_job(self.worker_id)

            if job:
                self._current_job = job
                logger.info(f"Worker {self.worker_id} processing job {job.id}")

                try:
                    await self._process_job(job)
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error: {e}")
                    self.db.update_job(job.id, status='failed', error=str(e))

                self._current_job = None
            else:
                # No hay trabajos, esperar
                await asyncio.sleep(2)

    async def _process_job(self, job: QueueJob):
        """Procesa un trabajo individual"""
        try:
            # Actualizar progreso
            self.db.update_job(job.id, progress=10, message="Iniciando descarga...")

            # Llamar al procesador real
            result = await self.processor(job, self._progress_callback)

            # Marcar como completado
            self.db.update_job(
                job.id,
                status='completed',
                progress=100,
                message="Completado",
                result=result
            )

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            self.db.update_job(job.id, status='failed', error=str(e), message=f"Error: {str(e)}")
            raise

    def _progress_callback(self, progress: int, message: str, status: str = None):
        """Callback para actualizar progreso"""
        if self._current_job:
            self.db.update_job(
                self._current_job.id,
                progress=progress,
                message=message,
                status=status
            )

    def stop(self):
        """Detiene el worker"""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopping")


class QueueManager:
    """Manager principal del sistema de colas"""

    def __init__(self, db_path: str = "queue.db", max_workers: int = 3):
        self.db = QueueDatabase(db_path)
        self.max_workers = max_workers
        self.workers: List[QueueWorker] = []
        self.running = False
        self._processor_callback: Optional[Callable] = None
        self._tasks: List[asyncio.Task] = []

    def set_processor(self, callback: Callable):
        """Establece la función de procesamiento"""
        self._processor_callback = callback

    def add_job(self, url: str, platform: str = "unknown", title: str = "",
                category: str = "default", priority: JobPriority = JobPriority.NORMAL,
                video_info: Dict = None, options: Dict = None) -> str:
        """Agrega un trabajo a la cola"""
        job = QueueJob(
            id=f"job_{uuid.uuid4().hex[:8]}",
            url=url,
            platform=platform,
            title=title or url[:50],
            category=category,
            priority=priority.value,
            status=JobStatus.QUEUED.value,
            progress=0,
            message="En cola",
            video_info=video_info or {},
            options=options or {},
            created_at=datetime.now().isoformat(),
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
            worker_id=None
        )

        self.db.add_job(job)
        logger.info(f"Job {job.id} added to queue")
        return job.id

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Obtiene el estado de un trabajo"""
        job = self.db.get_job(job_id)
        return job.to_dict() if job else None

    def get_queue_status(self) -> Dict:
        """Obtiene el estado general de la cola"""
        status = self.db.get_queue_status()
        status["workers"] = {
            "total": self.max_workers,
            "active": len([w for w in self.workers if w.running])
        }
        return status

    def get_all_jobs(self, status: str = None, limit: int = 50) -> List[Dict]:
        """Obtiene todos los trabajos"""
        jobs = self.db.get_all_jobs(status, limit)
        return [j.to_dict() for j in jobs]

    def cancel_job(self, job_id: str) -> bool:
        """Cancela un trabajo"""
        return self.db.cancel_job(job_id)

    async def start(self):
        """Inicia los workers"""
        if not self._processor_callback:
            raise ValueError("No processor callback set. Call set_processor() first.")

        self.running = True
        logger.info(f"Starting queue manager with {self.max_workers} workers")

        # Crear workers
        for i in range(self.max_workers):
            worker = QueueWorker(f"worker_{i}", self.db, self._processor_callback)
            self.workers.append(worker)
            task = asyncio.create_task(worker.start())
            self._tasks.append(task)

    async def stop(self):
        """Detiene todos los workers"""
        self.running = False
        logger.info("Stopping queue manager")

        for worker in self.workers:
            worker.stop()

        for task in self._tasks:
            task.cancel()

        self.workers.clear()
        self._tasks.clear()

    def clear_old_jobs(self, hours: int = 24) -> int:
        """Limpia trabajos antiguos"""
        return self.db.clear_completed(hours)


# Función de procesamiento de ejemplo
async def example_processor(job: QueueJob, progress_callback: Callable) -> Dict:
    """Procesador de ejemplo"""
    import random

    # Simular descarga
    progress_callback(20, "Descargando video...", "downloading")
    await asyncio.sleep(random.uniform(1, 3))

    # Simular procesamiento
    progress_callback(50, "Procesando video...", "processing")
    await asyncio.sleep(random.uniform(2, 5))

    # Simular subtítulos
    progress_callback(80, "Generando subtítulos...", "generating_subs")
    await asyncio.sleep(random.uniform(1, 2))

    return {
        "processed_path": f"/processed/{job.id}.mp4",
        "duration": random.randint(15, 60),
        "size_mb": random.uniform(5, 50)
    }


# Test
if __name__ == "__main__":
    async def test():
        manager = QueueManager("test_queue.db", max_workers=2)
        manager.set_processor(example_processor)

        # Agregar algunos trabajos
        job1 = manager.add_job(
            url="https://tiktok.com/video/1",
            platform="tiktok",
            title="Video 1",
            category="cats",
            priority=JobPriority.HIGH
        )

        job2 = manager.add_job(
            url="https://tiktok.com/video/2",
            platform="tiktok",
            title="Video 2",
            category="dogs",
            priority=JobPriority.NORMAL
        )

        job3 = manager.add_job(
            url="https://tiktok.com/video/3",
            platform="tiktok",
            title="Video 3",
            category="funny",
            priority=JobPriority.LOW
        )

        print(f"\n📋 Cola inicial: {manager.get_queue_status()}")

        # Iniciar procesamiento
        await manager.start()

        # Esperar a que se procesen
        for _ in range(20):
            await asyncio.sleep(1)
            status = manager.get_queue_status()
            print(f"⏳ Procesando... Queued: {status['queued']}, Processing: {status['processing']}, Completed: {status['completed']}")

            if status['completed'] == 3:
                break

        await manager.stop()

        print(f"\n✅ Cola final: {manager.get_queue_status()}")

        # Mostrar resultados
        for job_id in [job1, job2, job3]:
            job = manager.get_job_status(job_id)
            print(f"\nJob {job_id}: {job['status']} - {job['message']}")
            if job['result']:
                print(f"  Result: {job['result']}")

        # Limpiar
        import os
        os.remove("test_queue.db")

    asyncio.run(test())
