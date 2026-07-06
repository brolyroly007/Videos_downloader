"""
TikTok Discover Module
Obtiene videos reales de TikTok con thumbnails y metadata usando yt-dlp
Incluye algoritmo de viralidad predictiva basado en:
- Recencia de subida
- Velocidad de crecimiento (engagement/tiempo)
- Tasa de engagement
- Matching de hashtags por categoría
"""

import subprocess
import json
import logging
import asyncio
import os
import shutil
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
import re
import aiohttp
import math

# Find yt-dlp executable
def find_ytdlp():
    """Find yt-dlp executable path"""
    # Try common locations
    paths_to_try = [
        shutil.which('yt-dlp'),
        r'C:\Users\MSI\AppData\Local\Programs\Python\Python313\Scripts\yt-dlp.exe',
        r'D:\proyectojudietha\.venv\Scripts\yt-dlp.exe',
    ]
    for path in paths_to_try:
        if path and os.path.exists(path):
            return path
    return 'yt-dlp'  # Fallback to PATH

YTDLP_PATH = find_ytdlp()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ruta de cookies
COOKIES_FILE = Path(__file__).parent.parent / "cookies" / "tiktok_cookies.txt"


@dataclass
class TikTokVideo:
    """Video de TikTok con toda su metadata y métricas predictivas"""
    id: str
    url: str
    title: str
    author: str
    author_url: str
    thumbnail: str
    duration: int
    views: int
    likes: int
    comments: int
    shares: int
    upload_date: str
    viral_score: float
    category: str
    # Nuevos campos para métricas predictivas
    engagement_rate: float = 0.0  # Tasa de engagement (likes+comments+shares)/views
    growth_velocity: float = 0.0  # Velocidad de crecimiento (views por hora)
    recency_score: float = 0.0    # Puntuación de recencia (más nuevo = más puntos)
    hashtag_match_score: float = 0.0  # Coincidencia con hashtags de categoría
    predicted_viral_potential: float = 0.0  # Potencial viral predictivo
    hashtags: List[str] = field(default_factory=list)  # Hashtags extraídos del video
    description: str = ""  # Descripción completa

    def to_dict(self) -> dict:
        return asdict(self)


class TikTokDiscovery:
    """
    Descubre videos de TikTok usando yt-dlp y APIs públicas
    """

    def __init__(self):
        # Cuentas populares VERIFICADAS por categoría (accesibles sin login)
        self.popular_accounts = {
            "cats": ["@tiktok", "@catpeopleoftiktok", "@meowdemos", "@cats_of_tiktok0"],
            "dogs": ["@tiktok", "@dogsofttiktok", "@goldenretrievers"],
            "funny": ["@tiktok", "@nbcsnl", "@failarmy", "@comedycentral"],
            "music": ["@tiktok", "@spotify", "@billboard", "@mtv"],
            "fitness": ["@tiktok", "@gymshark", "@nike", "@underarmour"],
            "food": ["@tiktok", "@buzzfeedtasty", "@gordonramsayofficial", "@mcdonalds"],
            "beauty": ["@tiktok", "@sephora", "@fentybeauty", "@kyliecosmetics"],
            "gaming": ["@tiktok", "@playstation", "@xbox", "@nintendo"],
            "babies": ["@tiktok", "@pampers", "@target"],
            "cars": ["@tiktok", "@bmw", "@mercedes", "@porsche"],
            "travel": ["@tiktok", "@tripadvisor", "@airbnb", "@expedia"],
            "lifestyle": ["@tiktok", "@netflix", "@amazon", "@apple"],
        }

        # Hashtags por categoría con URLs de búsqueda
        self.categories = {
            "cats": {
                "name": "Gatitos",
                "hashtags": ["catsoftiktok", "cat", "kitten", "gato", "gatosdetiktok"],
                "search_terms": ["funny cat", "cute kitten", "gato gracioso"]
            },
            "dogs": {
                "name": "Perritos",
                "hashtags": ["dogsoftiktok", "dog", "puppy", "perro", "perrosdetiktok"],
                "search_terms": ["funny dog", "cute puppy", "perro gracioso"]
            },
            "funny": {
                "name": "Graciosos",
                "hashtags": ["funny", "comedy", "humor", "memes", "gracioso"],
                "search_terms": ["funny video", "comedy", "memes compilation"]
            },
            "music": {
                "name": "Música",
                "hashtags": ["music", "dance", "song", "musica", "baile"],
                "search_terms": ["dance tiktok", "viral song", "music video"]
            },
            "fitness": {
                "name": "Fitness",
                "hashtags": ["fitness", "gym", "workout", "exercise", "fitnessmotivation"],
                "search_terms": ["workout routine", "gym motivation", "fitness tips"]
            },
            "food": {
                "name": "Comida",
                "hashtags": ["food", "recipe", "cooking", "foodtiktok", "comida"],
                "search_terms": ["easy recipe", "cooking hack", "food asmr"]
            },
            "beauty": {
                "name": "Belleza",
                "hashtags": ["beauty", "makeup", "skincare", "grwm", "beautytips"],
                "search_terms": ["makeup tutorial", "skincare routine", "grwm"]
            },
            "gaming": {
                "name": "Gaming",
                "hashtags": ["gaming", "gamer", "videogames", "gameplay", "esports"],
                "search_terms": ["gaming clips", "funny gaming", "epic gaming"]
            },
            "babies": {
                "name": "Bebés",
                "hashtags": ["baby", "babies", "kids", "cute", "babytiktok"],
                "search_terms": ["cute baby", "funny baby", "baby laughing"]
            },
            "cars": {
                "name": "Autos",
                "hashtags": ["car", "cars", "supercar", "carlifestyle", "automotive"],
                "search_terms": ["supercar", "car review", "car sounds"]
            },
            "travel": {
                "name": "Viajes",
                "hashtags": ["travel", "vacation", "explore", "traveltiktok", "viaje"],
                "search_terms": ["travel vlog", "beautiful places", "travel tips"]
            },
            "lifestyle": {
                "name": "Lifestyle",
                "hashtags": ["lifestyle", "aesthetic", "dayinmylife", "routine", "vlog"],
                "search_terms": ["day in my life", "aesthetic vlog", "morning routine"]
            }
        }

    def _get_cookies_args(self) -> List[str]:
        """Retorna argumentos de cookies si existen"""
        if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 100:
            return ['--cookies', str(COOKIES_FILE)]
        # Sin cookies - algunos endpoints funcionan igual
        return []

    async def search_by_account(self, username: str, limit: int = 5) -> List[TikTokVideo]:
        """
        Busca videos de una cuenta específica (NO requiere autenticación)
        """
        videos = []
        # Limpiar el @
        username = username.lstrip('@')
        url = f"https://www.tiktok.com/@{username}"

        try:
            cmd = [
                YTDLP_PATH,
                '--dump-json',
                '--no-download',
                '--flat-playlist',
                '--playlist-items', f'1:{limit}',
                '--no-warnings',
                '--quiet',
                '--ignore-errors',
                url
            ]

            logger.info(f"Buscando videos de @{username} usando {YTDLP_PATH}")

            # Use subprocess.run in a thread pool for Windows compatibility
            def run_ytdlp():
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    return result.stdout, result.stderr, result.returncode
                except Exception as e:
                    return None, str(e), -1

            try:
                loop = asyncio.get_event_loop()
                stdout, stderr, returncode = await loop.run_in_executor(None, run_ytdlp)
            except Exception as exec_err:
                logger.error(f"Failed to execute yt-dlp: {type(exec_err).__name__}: {exec_err}")
                return videos

            # Log process info for debugging
            logger.info(f"yt-dlp return code: {returncode}, stdout: {len(stdout) if stdout else 0} bytes")

            if stderr and stderr.strip():
                logger.warning(f"yt-dlp stderr: {stderr[:500]}")

            if stdout:
                for line in stdout.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            video = self._parse_video_data(data, username)
                            if video:
                                videos.append(video)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error: {e} for line: {line[:100]}")
                            continue
            else:
                logger.warning(f"No stdout from yt-dlp for @{username}")

            logger.info(f"Encontrados {len(videos)} videos de @{username}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout buscando @{username}")
        except Exception as e:
            import traceback
            logger.error(f"Error buscando @{username}: {type(e).__name__}: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

        return videos

    async def search_by_hashtag(self, hashtag: str, limit: int = 10) -> List[TikTokVideo]:
        """
        Busca videos por hashtag usando yt-dlp
        """
        videos = []
        url = f"https://www.tiktok.com/tag/{hashtag}"

        try:
            cmd = [
                YTDLP_PATH,
                '--dump-json',
                '--no-download',
                '--flat-playlist',
                '--playlist-items', f'1:{limit}',
                '--no-warnings',
                '--quiet',
                '--ignore-errors',
            ] + self._get_cookies_args() + [url]

            logger.info(f"Buscando hashtag: #{hashtag}")

            # Use subprocess.run in a thread pool for Windows compatibility
            def run_ytdlp_hashtag():
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=90,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    return result.stdout, result.stderr, result.returncode
                except Exception as e:
                    return None, str(e), -1

            try:
                loop = asyncio.get_event_loop()
                stdout, stderr, returncode = await loop.run_in_executor(None, run_ytdlp_hashtag)
            except Exception as exec_err:
                logger.error(f"Failed to execute yt-dlp: {type(exec_err).__name__}: {exec_err}")
                return videos

            if stdout:
                for line in stdout.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            video = self._parse_video_data(data, hashtag)
                            if video:
                                videos.append(video)
                        except json.JSONDecodeError:
                            continue

            if not videos and stderr:
                logger.warning(f"No videos found for #{hashtag}: {stderr[:200]}")

        except Exception as e:
            logger.error(f"Error searching hashtag {hashtag}: {e}")

        logger.info(f"Encontrados {len(videos)} videos para #{hashtag}")
        return videos

    async def get_video_details(self, url: str) -> Optional[TikTokVideo]:
        """
        Obtiene detalles completos de un video específico
        """
        try:
            from modules.downloader import validate_media_url
            url = validate_media_url(url)
            cmd = [
                YTDLP_PATH,
                '--dump-json',
                '--no-download',
                '--no-warnings',
            ] + self._get_cookies_args() + ['--', url]

            # Use subprocess.run in a thread pool for Windows compatibility
            def run_ytdlp_details():
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    return result.stdout, result.stderr, result.returncode
                except Exception as e:
                    return None, str(e), -1

            loop = asyncio.get_event_loop()
            stdout, stderr, returncode = await loop.run_in_executor(None, run_ytdlp_details)

            if stdout:
                data = json.loads(stdout)
                return self._parse_video_data(data, "unknown")

        except Exception as e:
            logger.error(f"Error getting video details: {e}")

        return None

    async def discover_category(
        self,
        category_id: str,
        limit: int = 12,
        sort_by: str = "predicted_viral",  # "predicted_viral", "viral_score", "recency", "engagement"
        min_hashtag_match: float = 0.0,  # Filtrar por mínimo match de hashtags (0-100)
        min_engagement: float = 0.0       # Filtrar por engagement mínimo
    ) -> List[TikTokVideo]:
        """
        Descubre videos de una categoría específica con filtrado avanzado

        Args:
            category_id: ID de la categoría
            limit: Número máximo de videos a retornar
            sort_by: Criterio de ordenamiento:
                - "predicted_viral": Potencial viral predictivo (RECOMENDADO)
                - "viral_score": Score viral tradicional
                - "recency": Videos más recientes primero
                - "engagement": Mayor tasa de engagement primero
            min_hashtag_match: Filtrar videos con al menos este % de match con hashtags de categoría
            min_engagement: Filtrar videos con al menos esta tasa de engagement
        """
        if category_id not in self.categories:
            logger.warning(f"Unknown category: {category_id}")
            return []

        all_videos = []

        # Primero: Buscar en cuentas populares (NO requiere auth)
        if category_id in self.popular_accounts:
            accounts = self.popular_accounts[category_id][:3]  # Primeras 3 cuentas
            videos_per_account = max(3, (limit * 2) // len(accounts))  # Buscar más para filtrar

            for account in accounts:
                try:
                    videos = await self.search_by_account(account, limit=videos_per_account)
                    for video in videos:
                        video.category = category_id
                    all_videos.extend(videos)

                    await asyncio.sleep(0.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error with account {account}: {e}")
                    continue

        # Si no hay suficientes, intentar hashtags (requiere auth)
        if len(all_videos) < limit:
            category = self.categories[category_id]
            for hashtag in category["hashtags"][:2]:
                try:
                    videos = await self.search_by_hashtag(hashtag, limit=limit)
                    for video in videos:
                        video.category = category_id
                    all_videos.extend(videos)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error with hashtag {hashtag}: {e}")

        # Eliminar duplicados por ID
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            if video.id not in seen_ids:
                seen_ids.add(video.id)
                unique_videos.append(video)

        # FILTRADO AVANZADO
        filtered_videos = unique_videos

        # Filtrar por match de hashtags si se especifica
        if min_hashtag_match > 0:
            filtered_videos = [
                v for v in filtered_videos
                if v.hashtag_match_score >= min_hashtag_match
            ]
            logger.info(f"Filtrados por hashtag match >= {min_hashtag_match}: {len(filtered_videos)} videos")

        # Filtrar por engagement mínimo
        if min_engagement > 0:
            filtered_videos = [
                v for v in filtered_videos
                if v.engagement_rate >= min_engagement
            ]
            logger.info(f"Filtrados por engagement >= {min_engagement}: {len(filtered_videos)} videos")

        # ORDENAMIENTO según criterio seleccionado
        if sort_by == "predicted_viral":
            # Ordenar por potencial viral predictivo (MEJOR para encontrar contenido emergente)
            filtered_videos.sort(key=lambda v: v.predicted_viral_potential, reverse=True)
        elif sort_by == "recency":
            # Ordenar por recencia (videos más nuevos primero)
            filtered_videos.sort(key=lambda v: v.recency_score, reverse=True)
        elif sort_by == "engagement":
            # Ordenar por tasa de engagement
            filtered_videos.sort(key=lambda v: v.engagement_rate, reverse=True)
        else:  # "viral_score" o default
            # Ordenar por score viral tradicional
            filtered_videos.sort(key=lambda v: v.viral_score, reverse=True)

        logger.info(f"Total videos para {category_id} (ordenados por {sort_by}): {len(filtered_videos)}")

        # Si después de filtrar no hay suficientes, usar los originales
        if len(filtered_videos) < limit // 2 and len(unique_videos) > len(filtered_videos):
            logger.info("Pocos videos tras filtrar, incluyendo algunos sin filtrar")
            # Añadir videos que no pasaron el filtro pero ordenados
            remaining = [v for v in unique_videos if v not in filtered_videos]
            if sort_by == "predicted_viral":
                remaining.sort(key=lambda v: v.predicted_viral_potential, reverse=True)
            filtered_videos.extend(remaining[:limit - len(filtered_videos)])

        return filtered_videos[:limit]

    def _parse_video_data(self, data: dict, category: str) -> Optional[TikTokVideo]:
        """
        Parsea datos de yt-dlp a TikTokVideo con métricas predictivas
        """
        try:
            video_id = data.get('id', '')
            if not video_id:
                return None

            views = data.get('view_count', 0) or 0
            likes = data.get('like_count', 0) or 0
            comments = data.get('comment_count', 0) or 0
            shares = data.get('repost_count', 0) or 0
            duration = data.get('duration', 0) or 0
            upload_date = data.get('upload_date', '')

            # Obtener descripción completa y extraer hashtags
            description = data.get('description', '') or data.get('title', '') or ''
            title = data.get('title', '')[:100] if data.get('title') else description[:100]

            # Extraer hashtags del título y descripción
            video_hashtags = self._extract_hashtags(description + ' ' + title)

            # Calcular todas las métricas de viralidad
            (
                viral_score,
                engagement_rate,
                growth_velocity,
                recency_score,
                hashtag_match_score,
                predicted_viral_potential
            ) = self._calculate_viral_score(
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                duration=duration,
                upload_date=upload_date,
                video_hashtags=video_hashtags,
                category_id=category
            )

            # Obtener mejor thumbnail
            thumbnail = data.get('thumbnail', '')
            thumbnails = data.get('thumbnails', [])
            if thumbnails:
                # Preferir thumbnails de mayor resolución
                for thumb in reversed(thumbnails):
                    if thumb.get('url'):
                        thumbnail = thumb['url']
                        break

            return TikTokVideo(
                id=video_id,
                url=data.get('webpage_url', f"https://www.tiktok.com/@{data.get('uploader', 'user')}/video/{video_id}"),
                title=title if title else 'Sin título',
                author=f"@{data.get('uploader', data.get('creator', 'unknown'))}",
                author_url=data.get('uploader_url', ''),
                thumbnail=thumbnail,
                duration=duration,
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                upload_date=upload_date,
                viral_score=viral_score,
                category=category,
                # Nuevos campos de métricas predictivas
                engagement_rate=round(engagement_rate, 2),
                growth_velocity=round(growth_velocity, 2),
                recency_score=round(recency_score, 2),
                hashtag_match_score=round(hashtag_match_score, 2),
                predicted_viral_potential=round(predicted_viral_potential, 2),
                hashtags=video_hashtags,
                description=description[:500]  # Limitar descripción
            )
        except Exception as e:
            logger.error(f"Error parsing video data: {e}")
            return None

    def _extract_hashtags(self, text: str) -> List[str]:
        """Extrae hashtags del texto (título o descripción)"""
        if not text:
            return []
        # Patrón para hashtags: #palabra
        hashtags = re.findall(r'#(\w+)', text.lower())
        return list(set(hashtags))  # Eliminar duplicados

    def _calculate_hashtag_match(self, video_hashtags: List[str], category_id: str) -> float:
        """
        Calcula qué tan bien coinciden los hashtags del video con la categoría
        Retorna score de 0-100
        """
        if not video_hashtags or category_id not in self.categories:
            return 0.0

        category_hashtags = set(h.lower() for h in self.categories[category_id]["hashtags"])
        video_hashtags_set = set(h.lower() for h in video_hashtags)

        # Contar coincidencias
        matches = len(category_hashtags & video_hashtags_set)

        if matches == 0:
            return 0.0

        # Score basado en % de coincidencias (máximo 100 si coincide 3+)
        score = min(100, (matches / 3) * 100)
        return score

    def _calculate_recency_score(self, upload_date: str) -> float:
        """
        Calcula puntuación de recencia (videos más nuevos = más potencial viral)
        - Video de hoy: 100 puntos
        - Video de ayer: 90 puntos
        - Video de hace 7 días: 50 puntos
        - Video de hace 30 días: 20 puntos
        - Video más viejo: 5 puntos
        """
        if not upload_date:
            return 30.0  # Score por defecto si no hay fecha

        try:
            # Formato yt-dlp: YYYYMMDD
            upload_datetime = datetime.strptime(upload_date, "%Y%m%d")
            now = datetime.now()
            days_old = (now - upload_datetime).days

            if days_old <= 0:
                return 100.0  # Video de hoy
            elif days_old == 1:
                return 90.0
            elif days_old <= 3:
                return 80.0
            elif days_old <= 7:
                return 60.0
            elif days_old <= 14:
                return 40.0
            elif days_old <= 30:
                return 25.0
            elif days_old <= 90:
                return 15.0
            else:
                return 5.0
        except (ValueError, TypeError):
            return 30.0  # Score por defecto

    def _calculate_growth_velocity(self, views: int, likes: int, upload_date: str) -> float:
        """
        Calcula la velocidad de crecimiento (engagement por hora desde subida)
        Un video con muchas views en poco tiempo = alto potencial viral
        """
        if not upload_date or views == 0:
            return 0.0

        try:
            upload_datetime = datetime.strptime(upload_date, "%Y%m%d")
            now = datetime.now()
            hours_since_upload = max(1, (now - upload_datetime).total_seconds() / 3600)

            # Views por hora
            views_per_hour = views / hours_since_upload

            # Normalizar a score 0-100
            # Un video con 10k views/hora es considerado muy viral
            if views_per_hour >= 10000:
                return 100.0
            elif views_per_hour >= 5000:
                return 85.0
            elif views_per_hour >= 1000:
                return 70.0
            elif views_per_hour >= 500:
                return 55.0
            elif views_per_hour >= 100:
                return 40.0
            elif views_per_hour >= 50:
                return 25.0
            elif views_per_hour >= 10:
                return 15.0
            else:
                return 5.0
        except (ValueError, TypeError):
            return 0.0

    def _calculate_engagement_rate(self, views: int, likes: int, comments: int, shares: int) -> float:
        """
        Calcula la tasa de engagement como porcentaje
        Shares valen más porque indican contenido compartible
        """
        if views == 0:
            return 0.0

        # Ponderación: shares x3, comments x2, likes x1
        weighted_engagement = likes + (comments * 2) + (shares * 3)
        rate = (weighted_engagement / views) * 100

        return min(100, rate)  # Cap en 100%

    def _calculate_viral_score(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        duration: int,
        upload_date: str = "",
        video_hashtags: List[str] = None,
        category_id: str = ""
    ) -> Tuple[float, float, float, float, float, float]:
        """
        Calcula múltiples métricas de viralidad incluyendo predicción

        Retorna tupla con:
        - viral_score: Score actual (0-100)
        - engagement_rate: Tasa de engagement
        - growth_velocity: Velocidad de crecimiento
        - recency_score: Puntuación de recencia
        - hashtag_match_score: Match con hashtags de categoría
        - predicted_viral_potential: Potencial viral predictivo (0-100)
        """
        video_hashtags = video_hashtags or []

        # 1. Score de engagement rate
        engagement_rate = self._calculate_engagement_rate(views, likes, comments, shares)

        # 2. Score de recencia
        recency_score = self._calculate_recency_score(upload_date)

        # 3. Velocidad de crecimiento
        growth_velocity = self._calculate_growth_velocity(views, likes, upload_date)

        # 4. Match de hashtags
        hashtag_match = self._calculate_hashtag_match(video_hashtags, category_id)

        # 5. Score tradicional de views (0-30 puntos)
        view_score = 0.0
        if views >= 10_000_000:
            view_score = 30
        elif views >= 5_000_000:
            view_score = 27
        elif views >= 1_000_000:
            view_score = 24
        elif views >= 500_000:
            view_score = 20
        elif views >= 100_000:
            view_score = 16
        elif views >= 50_000:
            view_score = 12
        elif views >= 10_000:
            view_score = 8
        elif views >= 1_000:
            view_score = 4

        # 6. Score de engagement (0-25 puntos)
        engagement_score = 0.0
        if engagement_rate >= 15:
            engagement_score = 25
        elif engagement_rate >= 10:
            engagement_score = 22
        elif engagement_rate >= 7:
            engagement_score = 18
        elif engagement_rate >= 5:
            engagement_score = 14
        elif engagement_rate >= 3:
            engagement_score = 10
        elif engagement_rate >= 1:
            engagement_score = 5

        # 7. Score de duración (0-15 puntos) - TikTok favorece videos cortos
        duration_score = 0.0
        if 15 <= duration <= 30:
            duration_score = 15
        elif 10 <= duration <= 45:
            duration_score = 12
        elif duration <= 60:
            duration_score = 8
        elif duration <= 90:
            duration_score = 5
        elif duration <= 180:
            duration_score = 2

        # Score viral actual (tradicional)
        viral_score = min(100, view_score + engagement_score + duration_score)

        # POTENCIAL VIRAL PREDICTIVO
        # Combina múltiples factores con pesos diferentes:
        # - Engagement alto en poco tiempo = muy prometedor
        # - Videos recientes con buen engagement = alto potencial
        # - Match de hashtags = mejor relevancia

        predicted_viral_potential = min(100, (
            (growth_velocity * 0.30) +       # 30% peso: velocidad de crecimiento
            (recency_score * 0.25) +          # 25% peso: qué tan reciente es
            (engagement_score * 1.2) +        # 30% peso: engagement (scaled)
            (hashtag_match * 0.10) +           # 10% peso: match de hashtags
            (duration_score * 0.33)            # 5% peso: duración óptima
        ))

        # Bonus: Si es muy reciente (< 3 días) y tiene alto engagement, boost extra
        if recency_score >= 80 and engagement_rate >= 5:
            predicted_viral_potential = min(100, predicted_viral_potential * 1.15)

        # Bonus: Velocidad de crecimiento excepcional
        if growth_velocity >= 70:
            predicted_viral_potential = min(100, predicted_viral_potential * 1.1)

        return (
            viral_score,
            engagement_rate,
            growth_velocity,
            recency_score,
            hashtag_match,
            predicted_viral_potential
        )

    def get_categories(self) -> List[dict]:
        """
        Retorna lista de categorías disponibles
        """
        return [
            {"id": cat_id, "name": cat_data["name"], "hashtags": cat_data["hashtags"]}
            for cat_id, cat_data in self.categories.items()
        ]


# Función para usar desde la API
async def discover_videos(
    category: str,
    limit: int = 12,
    sort_by: str = "predicted_viral",
    min_hashtag_match: float = 0.0,
    min_engagement: float = 0.0
) -> List[dict]:
    """
    Función helper para descubrir videos con filtrado avanzado

    Args:
        category: ID de la categoría
        limit: Número máximo de videos
        sort_by: Criterio de ordenamiento ("predicted_viral", "viral_score", "recency", "engagement")
        min_hashtag_match: Filtrar por mínimo match de hashtags (0-100)
        min_engagement: Filtrar por engagement mínimo
    """
    discovery = TikTokDiscovery()
    videos = await discovery.discover_category(
        category_id=category,
        limit=limit,
        sort_by=sort_by,
        min_hashtag_match=min_hashtag_match,
        min_engagement=min_engagement
    )
    return [v.to_dict() for v in videos]


# Test
if __name__ == "__main__":
    async def test():
        discovery = TikTokDiscovery()

        print("Categorías disponibles:")
        for cat in discovery.get_categories():
            print(f"  - {cat['id']}: {cat['name']}")

        print("\nBuscando videos de gatitos...")
        videos = await discovery.discover_category("cats", limit=5)

        for video in videos:
            print(f"\n📹 {video.title[:50]}...")
            print(f"   👤 {video.author}")
            print(f"   👁️ {video.views:,} views | ❤️ {video.likes:,} likes")
            print(f"   🔥 Viral Score: {video.viral_score:.0f}")
            print(f"   🔗 {video.url}")

    asyncio.run(test())
