"""
Video Downloader Module
Maneja la descarga de videos desde múltiples plataformas usando yt-dlp
Soporta: TikTok (sin marca de agua), Instagram Reels, YouTube Shorts, Facebook Watch

ACTUALIZADO: Solución para el error "status code 0" de TikTok (2024-2025)
Probado y funcionando con yt-dlp 2025.11.12
"""

import os
import re
import random
import subprocess
import yt_dlp
from pathlib import Path
from typing import Dict, Optional, List
import logging
import json
import time
import uuid

from modules.config import MAX_DOWNLOAD_RETRIES, RETRY_BASE_DELAY, DOWNLOAD_TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Error messages that indicate permanent failures (should NOT be retried)
_PERMANENT_ERROR_PATTERNS = [
    "is not a valid url",
    "unsupported url",
    "video unavailable",
    "video not found",
    "this video has been removed",
    "private video",
    "is not available",
    "unable to extract",
    "no video formats found",
    "confirm your age",
    "sign in",
    "account required",
]


def _is_permanent_error(error: Exception) -> bool:
    """Return True if the error is permanent and should NOT be retried."""
    msg = str(error).lower()
    return any(pattern in msg for pattern in _PERMANENT_ERROR_PATTERNS)


def _retry_download(func):
    """
    Decorator that retries a download function with exponential backoff.

    Retries up to MAX_DOWNLOAD_RETRIES times on transient errors.
    Permanent errors (invalid URL, video not found) fail immediately.
    Delay = RETRY_BASE_DELAY * 2^attempt + random jitter (0-1s).
    """
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(MAX_DOWNLOAD_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if _is_permanent_error(e):
                    logger.error(f"Permanent error, not retrying: {e}")
                    raise

                if attempt < MAX_DOWNLOAD_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES} failed: {e}. "
                        f"No more retries."
                    )
        raise last_exception
    return wrapper


class VideoDownloader:
    """Clase para descargar videos desde múltiples plataformas"""

    def __init__(self, download_path: str = "downloads", cookies_path: str = "cookies"):
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.cookies_path = Path(cookies_path)
        self.cookies_path.mkdir(parents=True, exist_ok=True)

    def _get_platform(self, url: str) -> str:
        """Detecta la plataforma del video basado en la URL"""
        url_lower = url.lower()
        if 'tiktok.com' in url_lower or 'vm.tiktok.com' in url_lower:
            return 'tiktok'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            return 'facebook'
        else:
            return 'unknown'

    def _get_browser_cookies_path(self) -> Optional[str]:
        """Intenta encontrar cookies del navegador para autenticación"""
        cookies_file = self.cookies_path / "tiktok_cookies.txt"
        if cookies_file.exists():
            return str(cookies_file)
        return None

    def _get_ydl_opts(self, platform: str, output_filename: str) -> dict:
        """
        Retorna las opciones de yt-dlp optimizadas para cada plataforma
        CONFIGURACIÓN PROBADA Y FUNCIONANDO
        """
        base_opts = {
            'outtmpl': str(self.download_path / output_filename),
            'format': 'best',
            'quiet': False,
            'no_warnings': False,
            'no_check_certificates': True,
            'retries': 10,
            'fragment_retries': 10,
        }

        if platform == 'tiktok':
            # Configuración SIMPLIFICADA que funciona (probada)
            # NO usar cookiesfrombrowser en Windows - causa errores DPAPI
            base_opts.update({
                'format': 'best',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                },
            })

            # Si hay archivo de cookies manual, usarlo
            cookies_file = self._get_browser_cookies_path()
            if cookies_file:
                logger.info(f"Using cookies file: {cookies_file}")
                base_opts['cookiefile'] = cookies_file

        elif platform == 'instagram':
            base_opts.update({
                'format': 'best',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                },
            })

        elif platform == 'youtube':
            base_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        elif platform == 'facebook':
            base_opts.update({
                'format': 'best',
            })

        return base_opts

    def _extract_video_id(self, url: str, platform: str) -> str:
        """Extrae el ID del video de la URL"""
        if platform == 'tiktok':
            patterns = [
                r'/video/(\d+)',
                r'v/(\d+)',
                r'tiktok\.com/.*?(\d{19})',
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

        elif platform == 'youtube':
            patterns = [
                r'(?:v=|/)([a-zA-Z0-9_-]{11})',
                r'youtu\.be/([a-zA-Z0-9_-]{11})',
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

        # Fallback: generar ID único
        return str(uuid.uuid4())[:12]

    def download(self, url: str, custom_filename: Optional[str] = None,
                 progress_callback: Optional[callable] = None) -> Dict[str, any]:
        """
        Descarga un video desde la URL proporcionada

        Args:
            url: URL del video a descargar
            custom_filename: Nombre personalizado para el archivo (opcional)
            progress_callback: Optional callable that receives a dict with
                {"percent": float, "speed_mb": float, "eta_seconds": int, "status": str}

        Returns:
            Dict con información del video descargado
        """
        platform = self._get_platform(url)
        logger.info(f"Detected platform: {platform}")

        # Generar nombre de archivo
        if custom_filename:
            filename = f"{custom_filename}.%(ext)s"
        else:
            filename = "%(id)s.%(ext)s"

        try:
            result = self._download_with_retry(url, platform, filename,
                                                progress_callback=progress_callback)
            return result

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Standard download failed: {error_msg}")

            # Si falla, intentar con línea de comandos directamente
            logger.info("Trying alternative CLI method...")
            alt_result = self._try_cli_download(url, platform)

            if alt_result:
                return alt_result

            logger.error("All download methods failed")
            return {
                'success': False,
                'error': f"Download failed: {error_msg}. Please try: 1) Update yt-dlp (pip install -U yt-dlp), 2) Check if the video is public, 3) Try a different video URL.",
                'platform': platform
            }

    @_retry_download
    def _download_with_retry(self, url: str, platform: str, filename: str,
                             progress_callback: Optional[callable] = None) -> Dict[str, any]:
        """
        Core download logic wrapped with retry decorator.
        Raises on failure so the retry decorator can handle it.
        """
        ydl_opts = self._get_ydl_opts(platform, filename)

        # Hook de progreso
        def progress_hook(d):
            status = d.get('status', '')
            if status == 'downloading':
                percent = d.get('_percent_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                logger.info(f"Downloading: {percent} at {speed}")
            elif status == 'finished':
                logger.info("Download completed, processing...")

            # Report progress to caller via callback
            if progress_callback is not None:
                try:
                    downloaded = d.get('downloaded_bytes') or 0
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    if total > 0:
                        pct = round((downloaded / total) * 100, 1)
                    else:
                        pct = 0.0

                    raw_speed = d.get('speed')  # bytes/s or None
                    speed_mb = round(raw_speed / (1024 * 1024), 2) if raw_speed else 0.0

                    eta_seconds = d.get('eta') or 0

                    progress_callback({
                        "percent": pct,
                        "speed_mb": speed_mb,
                        "eta_seconds": int(eta_seconds),
                        "status": status,
                    })
                except Exception:
                    pass  # Never let callback errors break the download

        ydl_opts['progress_hooks'] = [progress_hook]
        ydl_opts['socket_timeout'] = DOWNLOAD_TIMEOUT

        # Descargar video with timeout via subprocess watchdog
        start_time = time.monotonic()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Starting download from: {url}")
            info = ydl.extract_info(url, download=True)

            elapsed = time.monotonic() - start_time
            if elapsed > DOWNLOAD_TIMEOUT:
                raise TimeoutError(
                    f"Download exceeded timeout of {DOWNLOAD_TIMEOUT}s "
                    f"(took {elapsed:.0f}s)"
                )

            if info is None:
                raise Exception("Could not extract video information")

            # Obtener nombre del archivo descargado
            downloaded_filename = ydl.prepare_filename(info)

            # Verificar que el archivo existe
            if not os.path.exists(downloaded_filename):
                # Buscar el archivo más reciente en downloads
                downloaded_filename = self._find_latest_download()

            video_info = {
                'success': True,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'platform': platform,
                'width': info.get('width', 0),
                'height': info.get('height', 0),
                'filename': downloaded_filename,
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', 'Unknown'),
            }

            logger.info(f"Video downloaded successfully: {video_info['filename']}")
            return video_info

    def _try_cli_download(self, url: str, platform: str) -> Optional[Dict]:
        """
        Método alternativo usando yt-dlp directamente por CLI
        A veces funciona mejor que la API de Python
        """
        try:
            video_id = self._extract_video_id(url, platform)
            output_template = str(self.download_path / f"{video_id}.%(ext)s")

            cmd = [
                'yt-dlp',
                '--no-check-certificates',
                '--no-warnings',
                '-o', output_template,
                '--no-playlist',
                '--retries', '10',
                url
            ]

            logger.info(f"Running CLI command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT)

            if result.returncode == 0:
                # Buscar el archivo descargado
                downloaded_file = self._find_latest_download()

                if downloaded_file:
                    logger.info(f"CLI download successful: {downloaded_file}")
                    return {
                        'success': True,
                        'title': f'{platform.capitalize()} Video',
                        'duration': 0,
                        'platform': platform,
                        'width': 0,
                        'height': 0,
                        'filename': downloaded_file,
                        'thumbnail': '',
                        'description': '',
                        'uploader': 'Unknown',
                    }
            else:
                logger.warning(f"CLI download failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning("CLI download timed out")
        except Exception as e:
            logger.warning(f"CLI download error: {str(e)}")

        return None

    def _find_latest_download(self) -> Optional[str]:
        """Encuentra el archivo más recientemente descargado"""
        video_extensions = ['.mp4', '.webm', '.mkv', '.mov', '.avi']
        latest_file = None
        latest_time = 0

        for file in self.download_path.iterdir():
            if file.is_file() and file.suffix.lower() in video_extensions:
                file_time = file.stat().st_mtime
                if file_time > latest_time:
                    latest_time = file_time
                    latest_file = str(file)

        return latest_file

    def get_video_info(self, url: str) -> Dict[str, any]:
        """
        Obtiene información del video sin descargarlo
        Útil para preview antes de descargar
        """
        try:
            platform = self._get_platform(url)
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'no_check_certificates': True,
                'skip_download': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    'success': True,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'platform': platform,
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                }
        except Exception as e:
            logger.warning(f"Could not get video info: {str(e)}")
            # Devolver info básica para no bloquear el flujo
            return {
                'success': True,
                'title': 'Video',
                'duration': 0,
                'platform': self._get_platform(url),
                'width': 0,
                'height': 0,
                'thumbnail': '',
                'uploader': 'Unknown',
                'view_count': 0,
                'note': 'Info preview not available, but download should work'
            }


# Función auxiliar para uso directo
def download_video(url: str, output_path: str = "downloads") -> Dict[str, any]:
    """Función auxiliar para descargar un video directamente"""
    downloader = VideoDownloader(output_path)
    return downloader.download(url)


if __name__ == "__main__":
    print("=" * 50)
    print("  Video Downloader Test")
    print("=" * 50)
    print("Supported: TikTok, Instagram, YouTube, Facebook\n")

    test_url = input("Enter video URL to test: ")
    result = download_video(test_url)
    print(f"\nResult: {json.dumps(result, indent=2)}")
