"""
Viral Video Detector Module
Detecta y monitorea videos virales en TikTok, Instagram, YouTube Shorts
"""

import asyncio
import aiohttp
import json
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib

# Intentar importar playwright para scraping avanzado
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ViralVideo:
    """Representa un video viral detectado"""
    url: str
    platform: str
    video_id: str
    title: str
    author: str
    views: int
    likes: int
    comments: int
    shares: int
    duration: int  # seconds
    hashtags: List[str]
    thumbnail: str
    detected_at: datetime
    viral_score: float  # 0-100 score calculado

    def to_dict(self) -> dict:
        data = asdict(self)
        data['detected_at'] = self.detected_at.isoformat()
        return data

    @property
    def engagement_rate(self) -> float:
        """Calcula tasa de engagement"""
        if self.views == 0:
            return 0
        return ((self.likes + self.comments + self.shares) / self.views) * 100


class ViralDetector:
    """
    Detector de videos virales multi-plataforma

    Estrategias de detección:
    1. Trending hashtags monitoring
    2. Sound/audio tracking (TikTok)
    3. Engagement rate analysis
    4. Growth velocity (views per hour)
    5. Cross-platform appearance
    """

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.seen_videos: Dict[str, datetime] = {}  # video_id -> first_seen
        self.browser: Optional[Browser] = None

        # Configuración de umbrales de viralidad
        self.viral_thresholds = {
            'tiktok': {
                'min_views': 100000,
                'min_likes': 10000,
                'min_engagement_rate': 5.0,  # 5%
                'max_duration': 180,  # 3 minutos max
            },
            'instagram': {
                'min_views': 50000,
                'min_likes': 5000,
                'min_engagement_rate': 4.0,
                'max_duration': 90,
            },
            'youtube': {
                'min_views': 500000,
                'min_likes': 20000,
                'min_engagement_rate': 3.0,
                'max_duration': 60,  # Shorts
            }
        }

        # Hashtags populares para monitorear por nicho
        self.trending_hashtags = {
            'general': ['fyp', 'viral', 'trending', 'foryou', 'foryoupage'],
            'humor': ['funny', 'comedy', 'memes', 'humor', 'lol'],
            'lifestyle': ['lifestyle', 'dayinmylife', 'routine', 'aesthetic'],
            'fitness': ['fitness', 'workout', 'gym', 'fitnessmotivation'],
            'food': ['food', 'foodtiktok', 'recipe', 'cooking'],
            'beauty': ['beauty', 'makeup', 'skincare', 'beautytips'],
            'tech': ['tech', 'technology', 'gadgets', 'techtok'],
            'finance': ['money', 'investing', 'finance', 'crypto'],
            'education': ['learn', 'education', 'facts', 'didyouknow'],
        }

        # Blacklist de contenido a evitar
        self.blacklist_keywords = [
            'copyright', 'original', 'donotrepost', 'myoriginal',
            'ad', 'sponsored', 'promotion', 'brand'
        ]

    async def init_browser(self):
        """Inicializa Playwright browser para scraping"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available. Install with: pip install playwright && playwright install")
            return False

        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
        return True

    async def close_browser(self):
        """Cierra el browser"""
        if self.browser:
            await self.browser.close()
            self.browser = None

    def calculate_viral_score(self, video: Dict, platform: str) -> float:
        """
        Calcula un score de viralidad de 0-100

        Factores:
        - Views (30%)
        - Engagement rate (30%)
        - Growth velocity (20%)
        - Recency (10%)
        - Duration optimization (10%)
        """
        thresholds = self.viral_thresholds.get(platform, self.viral_thresholds['tiktok'])
        score = 0.0

        # Views score (30 points max)
        views = video.get('views', 0)
        min_views = thresholds['min_views']
        if views >= min_views * 10:
            score += 30
        elif views >= min_views * 5:
            score += 25
        elif views >= min_views * 2:
            score += 20
        elif views >= min_views:
            score += 15
        elif views >= min_views * 0.5:
            score += 10

        # Engagement rate score (30 points max)
        likes = video.get('likes', 0)
        comments = video.get('comments', 0)
        shares = video.get('shares', 0)
        if views > 0:
            engagement = ((likes + comments + shares) / views) * 100
            if engagement >= 10:
                score += 30
            elif engagement >= 7:
                score += 25
            elif engagement >= 5:
                score += 20
            elif engagement >= 3:
                score += 15
            elif engagement >= 1:
                score += 10

        # Duration optimization (10 points max)
        duration = video.get('duration', 0)
        # Videos de 15-60 segundos son óptimos
        if 15 <= duration <= 60:
            score += 10
        elif 10 <= duration <= 90:
            score += 7
        elif duration <= 180:
            score += 5

        # Recency bonus (10 points max)
        # Videos más recientes tienen más potencial
        created = video.get('created_at')
        if created:
            hours_old = (datetime.now() - created).total_seconds() / 3600
            if hours_old <= 6:
                score += 10
            elif hours_old <= 12:
                score += 8
            elif hours_old <= 24:
                score += 6
            elif hours_old <= 48:
                score += 4
            elif hours_old <= 72:
                score += 2

        # Hashtag relevance (10 points max)
        hashtags = video.get('hashtags', [])
        trending_tags = set()
        for tags in self.trending_hashtags.values():
            trending_tags.update(tags)

        matching_tags = len(set(h.lower() for h in hashtags) & trending_tags)
        score += min(matching_tags * 2, 10)

        # Penalty for blacklisted content
        title = video.get('title', '').lower()
        for keyword in self.blacklist_keywords:
            if keyword in title:
                score -= 20
                break

        return max(0, min(100, score))

    async def scrape_tiktok_trending(self, hashtag: str = "fyp", limit: int = 20) -> List[ViralVideo]:
        """
        Scrapea videos trending de TikTok por hashtag

        Nota: TikTok tiene protecciones anti-bot. Para uso en producción,
        considera usar la API oficial o servicios como RapidAPI.
        """
        videos = []

        if not await self.init_browser():
            logger.error("Browser not available for TikTok scraping")
            return videos

        try:
            page = await self.browser.new_page()

            # Configurar user agent móvil para mejor compatibilidad
            await page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
            })

            url = f"https://www.tiktok.com/tag/{hashtag}"
            logger.info(f"Scraping TikTok hashtag: #{hashtag}")

            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)  # Esperar carga dinámica

            # Scroll para cargar más videos
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(1)

            # Extraer datos de videos
            video_elements = await page.query_selector_all('[data-e2e="challenge-item"]')

            for i, element in enumerate(video_elements[:limit]):
                try:
                    # Extraer URL del video
                    link = await element.query_selector('a')
                    if not link:
                        continue

                    video_url = await link.get_attribute('href')
                    if not video_url:
                        continue

                    # Extraer video ID
                    video_id_match = re.search(r'/video/(\d+)', video_url)
                    video_id = video_id_match.group(1) if video_id_match else hashlib.md5(video_url.encode()).hexdigest()[:12]

                    # Verificar si ya lo vimos
                    if video_id in self.seen_videos:
                        continue

                    # Extraer métricas (pueden variar según el layout)
                    stats_text = await element.inner_text()

                    # Parsear views/likes del texto
                    views = self._parse_count(stats_text, ['views', 'plays', 'M', 'K'])
                    likes = self._parse_count(stats_text, ['likes', 'hearts'])

                    video_data = {
                        'url': video_url if video_url.startswith('http') else f"https://www.tiktok.com{video_url}",
                        'video_id': video_id,
                        'views': views,
                        'likes': likes,
                        'comments': 0,
                        'shares': 0,
                        'duration': 30,  # Estimado
                        'hashtags': [hashtag],
                        'title': stats_text[:100] if stats_text else '',
                        'author': '',
                    }

                    # Calcular score
                    viral_score = self.calculate_viral_score(video_data, 'tiktok')

                    if viral_score >= 30:  # Umbral mínimo
                        viral_video = ViralVideo(
                            url=video_data['url'],
                            platform='tiktok',
                            video_id=video_id,
                            title=video_data['title'],
                            author=video_data['author'],
                            views=video_data['views'],
                            likes=video_data['likes'],
                            comments=video_data['comments'],
                            shares=video_data['shares'],
                            duration=video_data['duration'],
                            hashtags=video_data['hashtags'],
                            thumbnail='',
                            detected_at=datetime.now(),
                            viral_score=viral_score
                        )
                        videos.append(viral_video)
                        self.seen_videos[video_id] = datetime.now()

                except Exception as e:
                    logger.debug(f"Error parsing video element: {e}")
                    continue

            await page.close()

        except Exception as e:
            logger.error(f"Error scraping TikTok: {e}")

        logger.info(f"Found {len(videos)} viral videos from #{hashtag}")
        return videos

    async def scrape_tiktok_discover(self, limit: int = 50) -> List[ViralVideo]:
        """
        Scrapea la página de Discover/For You de TikTok
        """
        all_videos = []

        # Scrapear múltiples hashtags trending
        for category, hashtags in self.trending_hashtags.items():
            for hashtag in hashtags[:2]:  # Top 2 de cada categoría
                try:
                    videos = await self.scrape_tiktok_trending(hashtag, limit=10)
                    all_videos.extend(videos)
                    await asyncio.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error with hashtag {hashtag}: {e}")
                    continue

        # Ordenar por viral score
        all_videos.sort(key=lambda v: v.viral_score, reverse=True)

        # Eliminar duplicados
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            if video.video_id not in seen_ids:
                seen_ids.add(video.video_id)
                unique_videos.append(video)

        return unique_videos[:limit]

    async def get_video_details(self, url: str) -> Optional[Dict]:
        """
        Obtiene detalles completos de un video específico
        Usa yt-dlp para extraer metadata
        """
        import subprocess

        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                url
            ]

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    'url': url,
                    'video_id': data.get('id', ''),
                    'title': data.get('title', ''),
                    'author': data.get('uploader', ''),
                    'views': data.get('view_count', 0),
                    'likes': data.get('like_count', 0),
                    'comments': data.get('comment_count', 0),
                    'shares': data.get('repost_count', 0),
                    'duration': data.get('duration', 0),
                    'thumbnail': data.get('thumbnail', ''),
                    'hashtags': self._extract_hashtags(data.get('description', '')),
                    'platform': self._detect_platform(url),
                    'created_at': datetime.now(),  # No siempre disponible
                }
        except Exception as e:
            logger.error(f"Error getting video details: {e}")

        return None

    async def analyze_url(self, url: str) -> Optional[ViralVideo]:
        """
        Analiza una URL específica y determina si es viral
        """
        details = await self.get_video_details(url)
        if not details:
            return None

        platform = details['platform']
        viral_score = self.calculate_viral_score(details, platform)

        return ViralVideo(
            url=url,
            platform=platform,
            video_id=details['video_id'],
            title=details['title'],
            author=details['author'],
            views=details['views'],
            likes=details['likes'],
            comments=details['comments'],
            shares=details['shares'],
            duration=details['duration'],
            hashtags=details['hashtags'],
            thumbnail=details['thumbnail'],
            detected_at=datetime.now(),
            viral_score=viral_score
        )

    async def monitor_hashtags(
        self,
        hashtags: List[str],
        interval_minutes: int = 30,
        callback = None
    ):
        """
        Monitorea hashtags continuamente y notifica nuevos videos virales

        Args:
            hashtags: Lista de hashtags a monitorear
            interval_minutes: Intervalo entre escaneos
            callback: Función async a llamar cuando se detecta video viral
        """
        logger.info(f"Starting hashtag monitoring: {hashtags}")

        while True:
            try:
                for hashtag in hashtags:
                    videos = await self.scrape_tiktok_trending(hashtag, limit=20)

                    for video in videos:
                        if video.viral_score >= 50:  # Solo videos muy virales
                            logger.info(f"🔥 Viral detected: {video.title[:50]}... (score: {video.viral_score})")

                            if callback:
                                await callback(video)

                    await asyncio.sleep(5)  # Pausa entre hashtags

                logger.info(f"Scan complete. Next scan in {interval_minutes} minutes.")
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

    def _parse_count(self, text: str, indicators: List[str]) -> int:
        """Parsea conteos como '1.5M', '500K', etc."""
        text = text.lower()

        # Buscar patrones como "1.5m views" o "500k"
        patterns = [
            r'([\d.]+)\s*m\b',  # Millones
            r'([\d.]+)\s*k\b',  # Miles
            r'([\d,]+)\s*(?:views|plays|likes)',  # Número directo
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1).replace(',', '')
                try:
                    num = float(num_str)
                    if 'm' in pattern:
                        return int(num * 1_000_000)
                    elif 'k' in pattern:
                        return int(num * 1_000)
                    return int(num)
                except:
                    pass

        return 0

    def _extract_hashtags(self, text: str) -> List[str]:
        """Extrae hashtags de un texto"""
        return re.findall(r'#(\w+)', text.lower())

    def _detect_platform(self, url: str) -> str:
        """Detecta la plataforma de una URL"""
        url = url.lower()
        if 'tiktok.com' in url:
            return 'tiktok'
        elif 'instagram.com' in url:
            return 'instagram'
        elif 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'
        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'
        return 'unknown'

    def save_results(self, videos: List[ViralVideo], filename: str = "viral_videos.json"):
        """Guarda resultados en archivo JSON"""
        filepath = self.cache_dir / filename
        data = [v.to_dict() for v in videos]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(videos)} videos to {filepath}")

    def load_results(self, filename: str = "viral_videos.json") -> List[ViralVideo]:
        """Carga resultados de archivo JSON"""
        filepath = self.cache_dir / filename

        if not filepath.exists():
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        videos = []
        for item in data:
            item['detected_at'] = datetime.fromisoformat(item['detected_at'])
            videos.append(ViralVideo(**item))

        return videos


# API alternativa usando servicios externos
class TikTokAPIClient:
    """
    Cliente para APIs externas de TikTok (RapidAPI, etc.)
    Más confiable que scraping directo
    """

    def __init__(self, api_key: str, api_host: str = "tiktok-scraper7.p.rapidapi.com"):
        self.api_key = api_key
        self.api_host = api_host
        self.base_url = f"https://{api_host}"

    async def get_trending_videos(self, region: str = "US", count: int = 20) -> List[Dict]:
        """Obtiene videos trending via API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.api_host
            }

            params = {
                "region": region,
                "count": count
            }

            async with session.get(
                f"{self.base_url}/feed/list",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logger.error(f"API error: {response.status}")
                    return []

    async def search_hashtag(self, hashtag: str, count: int = 20) -> List[Dict]:
        """Busca videos por hashtag via API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.api_host
            }

            params = {
                "keywords": hashtag,
                "count": count,
                "cursor": 0
            }

            async with session.get(
                f"{self.base_url}/challenge/posts",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('videos', [])
                return []


# Ejemplo de uso
async def main():
    detector = ViralDetector()

    # Opción 1: Analizar URL específica
    url = "https://www.tiktok.com/@user/video/123456789"
    video = await detector.analyze_url(url)
    if video:
        print(f"Viral Score: {video.viral_score}")
        print(f"Views: {video.views:,}")
        print(f"Engagement: {video.engagement_rate:.2f}%")

    # Opción 2: Escanear hashtags trending
    videos = await detector.scrape_tiktok_discover(limit=30)
    print(f"\nFound {len(videos)} viral videos:")
    for v in videos[:10]:
        print(f"  - {v.title[:40]}... (score: {v.viral_score:.1f})")

    # Guardar resultados
    detector.save_results(videos)

    await detector.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
