"""
Analytics Module
Dashboard de estadísticas y métricas para videos procesados
"""

import sqlite3
import json
import uuid
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import os

logger = logging.getLogger(__name__)


@dataclass
class VideoStats:
    """Estadísticas de un video individual"""
    id: str
    url: str
    platform: str
    title: str
    category: str
    original_views: int
    original_likes: int
    original_comments: int
    viral_score: float
    processed_at: str
    uploaded_at: Optional[str]
    upload_status: str  # pending, uploaded, failed
    tiktok_url: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DailyStats:
    """Estadísticas diarias"""
    date: str
    videos_processed: int
    videos_uploaded: int
    total_original_views: int
    total_original_likes: int
    avg_viral_score: float
    top_category: str
    success_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OverallStats:
    """Estadísticas generales"""
    total_videos_processed: int
    total_videos_uploaded: int
    total_original_views: int
    total_original_likes: int
    avg_viral_score: float
    success_rate: float
    most_popular_category: str
    videos_by_platform: Dict[str, int]
    videos_by_category: Dict[str, int]
    videos_by_status: Dict[str, int]
    processing_trend: List[Dict]  # Últimos 7 días

    def to_dict(self) -> dict:
        return asdict(self)


class AnalyticsDatabase:
    """Base de datos para analytics"""

    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa las tablas de analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de videos procesados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_videos (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                platform TEXT DEFAULT 'unknown',
                title TEXT,
                category TEXT DEFAULT 'default',
                original_views INTEGER DEFAULT 0,
                original_likes INTEGER DEFAULT 0,
                original_comments INTEGER DEFAULT 0,
                original_shares INTEGER DEFAULT 0,
                viral_score REAL DEFAULT 0,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_at TIMESTAMP,
                upload_status TEXT DEFAULT 'pending',
                tiktok_url TEXT,
                local_path TEXT,
                description_used TEXT,
                hashtags_used TEXT,
                error_message TEXT
            )
        ''')

        # Tabla de métricas diarias (agregadas)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                videos_processed INTEGER DEFAULT 0,
                videos_uploaded INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                avg_viral_score REAL DEFAULT 0,
                top_category TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de eventos/logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                video_id TEXT,
                message TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Índices para búsquedas rápidas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_date ON processed_videos(processed_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_category ON processed_videos(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_platform ON processed_videos(platform)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_status ON processed_videos(upload_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)')

        conn.commit()
        conn.close()

    def record_processed_video(self, video_data: Dict) -> str:
        """Registra un video procesado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        video_id = video_data.get('id', f"vid_{uuid.uuid4().hex[:12]}")

        cursor.execute('''
            INSERT OR REPLACE INTO processed_videos
            (id, url, platform, title, category, original_views, original_likes,
             original_comments, original_shares, viral_score, local_path, description_used, hashtags_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            video_id,
            video_data.get('url', ''),
            video_data.get('platform', 'unknown'),
            video_data.get('title', ''),
            video_data.get('category', 'default'),
            video_data.get('views', 0),
            video_data.get('likes', 0),
            video_data.get('comments', 0),
            video_data.get('shares', 0),
            video_data.get('viral_score', 0),
            video_data.get('local_path', ''),
            video_data.get('description', ''),
            json.dumps(video_data.get('hashtags', []))
        ))

        conn.commit()
        conn.close()

        # Registrar evento DESPUÉS de cerrar la conexión: _log_event abre su
        # propia conexión y si la primera sigue con la transacción abierta se
        # produce un "database is locked".
        self._log_event('video_processed', video_id, f"Video procesado: {video_data.get('title', '')[:50]}")

        # Actualizar métricas diarias
        self._update_daily_metrics()

        return video_id

    def record_upload(self, video_id: str, tiktok_url: Optional[str] = None, success: bool = True, error: Optional[str] = None):
        """Registra una subida a TikTok"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        status = 'uploaded' if success else 'failed'

        cursor.execute('''
            UPDATE processed_videos
            SET upload_status = ?, uploaded_at = ?, tiktok_url = ?, error_message = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat() if success else None, tiktok_url, error, video_id))

        conn.commit()
        conn.close()

        # Registrar evento tras cerrar la conexión (evita "database is locked")
        event_type = 'video_uploaded' if success else 'upload_failed'
        self._log_event(event_type, video_id, f"Upload {'exitoso' if success else 'fallido'}: {error or tiktok_url}")

        self._update_daily_metrics()

    def _log_event(self, event_type: str, video_id: Optional[str] = None, message: Optional[str] = None, metadata: Optional[Dict] = None):
        """Registra un evento en el log"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO events (event_type, video_id, message, metadata)
            VALUES (?, ?, ?, ?)
        ''', (event_type, video_id, message, json.dumps(metadata) if metadata else None))

        conn.commit()
        conn.close()

    def _update_daily_metrics(self):
        """Actualiza las métricas diarias agregadas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Calcular métricas del día
        cursor.execute('''
            SELECT
                COUNT(*) as processed,
                SUM(CASE WHEN upload_status = 'uploaded' THEN 1 ELSE 0 END) as uploaded,
                SUM(original_views) as views,
                SUM(original_likes) as likes,
                AVG(viral_score) as avg_score
            FROM processed_videos
            WHERE DATE(processed_at) = ?
        ''', (today,))

        row = cursor.fetchone()

        # Obtener categoría más popular del día
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM processed_videos
            WHERE DATE(processed_at) = ?
            GROUP BY category
            ORDER BY count DESC
            LIMIT 1
        ''', (today,))

        cat_row = cursor.fetchone()
        top_category = cat_row[0] if cat_row else 'default'

        # Insertar o actualizar métricas
        cursor.execute('''
            INSERT OR REPLACE INTO daily_metrics
            (date, videos_processed, videos_uploaded, total_views, total_likes, avg_viral_score, top_category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            today,
            row[0] or 0,
            row[1] or 0,
            row[2] or 0,
            row[3] or 0,
            row[4] or 0,
            top_category,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def get_overall_stats(self) -> OverallStats:
        """Obtiene estadísticas generales"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Totales
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN upload_status = 'uploaded' THEN 1 ELSE 0 END) as uploaded,
                SUM(original_views) as views,
                SUM(original_likes) as likes,
                AVG(viral_score) as avg_score
            FROM processed_videos
        ''')
        totals = cursor.fetchone()

        # Por plataforma
        cursor.execute('''
            SELECT platform, COUNT(*) as count
            FROM processed_videos
            GROUP BY platform
        ''')
        by_platform = {row[0]: row[1] for row in cursor.fetchall()}

        # Por categoría
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM processed_videos
            GROUP BY category
            ORDER BY count DESC
        ''')
        by_category = {row[0]: row[1] for row in cursor.fetchall()}

        # Por status
        cursor.execute('''
            SELECT upload_status, COUNT(*) as count
            FROM processed_videos
            GROUP BY upload_status
        ''')
        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Trend últimos 7 días
        cursor.execute('''
            SELECT date, videos_processed, videos_uploaded, avg_viral_score
            FROM daily_metrics
            ORDER BY date DESC
            LIMIT 7
        ''')
        trend = [
            {"date": row[0], "processed": row[1], "uploaded": row[2], "avg_score": row[3]}
            for row in cursor.fetchall()
        ]
        trend.reverse()

        conn.close()

        total = totals[0] or 0
        uploaded = totals[1] or 0
        success_rate = (uploaded / total * 100) if total > 0 else 0

        most_popular = list(by_category.keys())[0] if by_category else 'default'

        return OverallStats(
            total_videos_processed=total,
            total_videos_uploaded=uploaded,
            total_original_views=totals[2] or 0,
            total_original_likes=totals[3] or 0,
            avg_viral_score=totals[4] or 0,
            success_rate=success_rate,
            most_popular_category=most_popular,
            videos_by_platform=by_platform,
            videos_by_category=by_category,
            videos_by_status=by_status,
            processing_trend=trend
        )

    def get_daily_stats(self, days: int = 7) -> List[DailyStats]:
        """Obtiene estadísticas de los últimos N días"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT date, videos_processed, videos_uploaded, total_views, total_likes, avg_viral_score, top_category
            FROM daily_metrics
            ORDER BY date DESC
            LIMIT ?
        ''', (days,))

        results = []
        for row in cursor.fetchall():
            processed = row[1] or 0
            uploaded = row[2] or 0
            success_rate = (uploaded / processed * 100) if processed > 0 else 0

            results.append(DailyStats(
                date=row[0],
                videos_processed=processed,
                videos_uploaded=uploaded,
                total_original_views=row[3] or 0,
                total_original_likes=row[4] or 0,
                avg_viral_score=row[5] or 0,
                top_category=row[6] or 'default',
                success_rate=success_rate
            ))

        conn.close()
        return results

    def get_recent_videos(self, limit: int = 20, category: Optional[str] = None, status: Optional[str] = None) -> List[VideoStats]:
        """Obtiene los videos más recientes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT id, url, platform, title, category, original_views, original_likes,
                   original_comments, viral_score, processed_at, uploaded_at, upload_status, tiktok_url
            FROM processed_videos
            WHERE 1=1
        '''
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)

        if status:
            query += ' AND upload_status = ?'
            params.append(status)

        query += ' ORDER BY processed_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append(VideoStats(
                id=row[0],
                url=row[1],
                platform=row[2],
                title=row[3],
                category=row[4],
                original_views=row[5],
                original_likes=row[6],
                original_comments=row[7],
                viral_score=row[8],
                processed_at=row[9],
                uploaded_at=row[10],
                upload_status=row[11],
                tiktok_url=row[12]
            ))

        conn.close()
        return results

    def get_category_stats(self) -> Dict[str, Dict]:
        """Obtiene estadísticas por categoría"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                category,
                COUNT(*) as total,
                SUM(CASE WHEN upload_status = 'uploaded' THEN 1 ELSE 0 END) as uploaded,
                AVG(viral_score) as avg_score,
                SUM(original_views) as views,
                SUM(original_likes) as likes
            FROM processed_videos
            GROUP BY category
            ORDER BY total DESC
        ''')

        results = {}
        for row in cursor.fetchall():
            total = row[1] or 0
            uploaded = row[2] or 0
            results[row[0]] = {
                "total": total,
                "uploaded": uploaded,
                "success_rate": (uploaded / total * 100) if total > 0 else 0,
                "avg_viral_score": row[3] or 0,
                "total_views": row[4] or 0,
                "total_likes": row[5] or 0
            }

        conn.close()
        return results

    def get_events(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Obtiene eventos/logs recientes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if event_type:
            cursor.execute('''
                SELECT id, event_type, video_id, message, metadata, created_at
                FROM events
                WHERE event_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (event_type, limit))
        else:
            cursor.execute('''
                SELECT id, event_type, video_id, message, metadata, created_at
                FROM events
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "event_type": row[1],
                "video_id": row[2],
                "message": row[3],
                "metadata": json.loads(row[4]) if row[4] else None,
                "created_at": row[5]
            })

        conn.close()
        return results


class AnalyticsManager:
    """Manager principal de analytics"""

    def __init__(self, db_path: str = "analytics.db"):
        self.db = AnalyticsDatabase(db_path)

    def track_video_processed(self, video_data: Dict) -> str:
        """Trackea un video procesado"""
        return self.db.record_processed_video(video_data)

    def track_upload(self, video_id: str, tiktok_url: Optional[str] = None, success: bool = True, error: Optional[str] = None):
        """Trackea una subida"""
        self.db.record_upload(video_id, tiktok_url, success, error)

    def get_dashboard_data(self) -> Dict:
        """Obtiene todos los datos para el dashboard"""
        overall = self.db.get_overall_stats()
        daily = self.db.get_daily_stats(7)
        recent = self.db.get_recent_videos(10)
        by_category = self.db.get_category_stats()
        events = self.db.get_events(limit=20)

        return {
            "overall": overall.to_dict(),
            "daily_stats": [d.to_dict() for d in daily],
            "recent_videos": [v.to_dict() for v in recent],
            "category_stats": by_category,
            "recent_events": events
        }


# Test
if __name__ == "__main__":
    manager = AnalyticsManager("test_analytics.db")

    # Simular algunos videos
    for i in range(5):
        video_id = manager.track_video_processed({
            "id": f"test_{i}",
            "url": f"https://tiktok.com/video/{i}",
            "platform": "tiktok",
            "title": f"Video de prueba {i}",
            "category": ["cats", "dogs", "funny"][i % 3],
            "views": 100000 * (i + 1),
            "likes": 10000 * (i + 1),
            "comments": 500 * (i + 1),
            "viral_score": 50 + i * 10
        })

        if i % 2 == 0:
            manager.track_upload(video_id, f"https://tiktok.com/uploaded/{i}", True)

    # Obtener dashboard
    dashboard = manager.get_dashboard_data()

    print("\n📊 Dashboard Analytics:")
    print(f"Total procesados: {dashboard['overall']['total_videos_processed']}")
    print(f"Total subidos: {dashboard['overall']['total_videos_uploaded']}")
    print(f"Tasa de éxito: {dashboard['overall']['success_rate']:.1f}%")
    print(f"Score viral promedio: {dashboard['overall']['avg_viral_score']:.1f}")
    print(f"\nPor categoría: {dashboard['category_stats']}")

    # Limpiar test
    os.remove("test_analytics.db")
