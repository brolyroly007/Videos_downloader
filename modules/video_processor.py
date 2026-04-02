"""
Video Processor Module
Maneja el procesamiento de videos: re-enmarcado, efectos anti-copyright, mirroring, cambios de velocidad
"""

import os
import subprocess
import json
import cv2
import numpy as np
# MoviePy 2.x API
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip, ImageClip, TextClip
from moviepy.video.fx import Resize, MirrorX, MultiplySpeed
from PIL import Image, ImageFilter
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


VALID_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov"}
DEFAULT_MAX_SIZE_MB = 500
DEFAULT_MAX_DURATION_SECONDS = 30 * 60  # 30 minutes


def validate_video(
    file_path: str,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
) -> Dict[str, any]:
    """
    Validate a video file before processing.

    Checks file existence, size, extension, and uses ffprobe to verify
    that a video stream exists and read codec/duration/resolution info.

    Returns:
        Dict with keys: duration, width, height, size_mb, codec

    Raises:
        ValueError: If validation fails for any reason.
    """
    path = Path(file_path)

    # --- File exists and is readable ---
    if not path.is_file():
        raise ValueError(f"Video file not found: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise ValueError(f"Video file is not readable: {file_path}")

    # --- File size ---
    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"Video file too large: {size_mb:.1f} MB (max {max_size_mb} MB)"
        )

    # --- Extension ---
    ext = path.suffix.lower()
    if ext not in VALID_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Invalid video extension '{ext}'. "
            f"Allowed: {', '.join(sorted(VALID_VIDEO_EXTENSIONS))}"
        )

    # --- ffprobe: video stream, duration, codec, resolution ---
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise ValueError(
                f"ffprobe failed for '{file_path}': {result.stderr.strip()}"
            )
        probe = json.loads(result.stdout)
    except FileNotFoundError:
        raise ValueError(
            "ffprobe not found. Please install FFmpeg and ensure it is on PATH."
        )
    except subprocess.TimeoutExpired:
        raise ValueError(f"ffprobe timed out while probing '{file_path}'")

    # Find first video stream
    video_stream = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if video_stream is None:
        raise ValueError(
            f"No video stream found in '{file_path}' (audio-only file?)"
        )

    # Extract info
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    codec = video_stream.get("codec_name", "unknown")

    # Duration: prefer stream duration, fall back to format duration
    duration = float(
        video_stream.get("duration")
        or probe.get("format", {}).get("duration")
        or 0
    )

    if duration <= 0:
        raise ValueError(f"Could not determine duration for '{file_path}'")

    if duration > max_duration_seconds:
        max_min = max_duration_seconds / 60
        dur_min = duration / 60
        raise ValueError(
            f"Video too long: {dur_min:.1f} min (max {max_min:.0f} min)"
        )

    info = {
        "duration": duration,
        "width": width,
        "height": height,
        "size_mb": round(size_mb, 2),
        "codec": codec,
    }

    logger.info(
        f"Video validated: {path.name} | {codec} {width}x{height}, "
        f"{duration:.1f}s, {size_mb:.1f} MB"
    )
    return info


class VideoProcessor:
    """Clase para procesar y editar videos con efectos anti-copyright"""

    def __init__(self, temp_path: str = "temp", output_path: str = "processed"):
        self.temp_path = Path(temp_path)
        self.output_path = Path(output_path)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Dimensiones para formato vertical (9:16)
        self.target_width = 1080
        self.target_height = 1920

    def get_video_info(self, video_path: str) -> Dict[str, any]:
        """Obtiene información básica del video"""
        try:
            clip = VideoFileClip(video_path)
            info = {
                'width': clip.w,
                'height': clip.h,
                'duration': clip.duration,
                'fps': clip.fps,
                'aspect_ratio': clip.w / clip.h
            }
            clip.close()
            return info
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            return {}

    def create_blur_background(self, video_path: str, output_path: str) -> str:
        """
        Crea un fondo desenfocado del video para rellenar el formato 9:16
        """
        try:
            logger.info("Creating blur background...")
            clip = VideoFileClip(video_path)

            # Crear fondo desenfocado escalado y estirado
            background = clip.resized(height=self.target_height)
            background = background.crop(
                x_center=background.w / 2,
                width=self.target_width,
                height=self.target_height
            )

            # Aplicar desenfoque usando un filtro
            def blur_frame(get_frame, t):
                frame = get_frame(t)
                pil_image = Image.fromarray(frame)
                blurred = pil_image.filter(ImageFilter.GaussianBlur(radius=30))
                return np.array(blurred)

            background = background.fl(blur_frame)

            # Redimensionar el video original para que quepa en el centro
            if clip.w / clip.h > self.target_width / self.target_height:
                # Video más ancho, ajustar por ancho
                main_video = clip.resized(width=self.target_width)
            else:
                # Video más alto, ajustar por alto
                main_video = clip.resized(height=self.target_height)

            # Centrar el video sobre el fondo
            final_video = CompositeVideoClip([
                background,
                main_video.with_position("center")
            ], size=(self.target_width, self.target_height))

            # Exportar
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio.m4a'),
                remove_temp=True,
                fps=clip.fps
            )

            clip.close()
            final_video.close()
            logger.info(f"Blur background created: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error creating blur background: {str(e)}")
            raise

    def create_solid_background(self, video_path: str, output_path: str, color: Tuple[int, int, int] = (0, 0, 0)) -> str:
        """
        Coloca el video sobre un fondo de color sólido para formato 9:16
        """
        try:
            logger.info(f"Creating solid background with color {color}...")
            clip = VideoFileClip(video_path)

            # Crear fondo de color sólido
            background = ColorClip(
                size=(self.target_width, self.target_height),
                color=color,
                duration=clip.duration
            )

            # Redimensionar el video original
            if clip.w / clip.h > self.target_width / self.target_height:
                main_video = clip.resized(width=self.target_width)
            else:
                main_video = clip.resized(height=self.target_height)

            # Centrar el video sobre el fondo
            final_video = CompositeVideoClip([
                background,
                main_video.with_position("center")
            ], size=(self.target_width, self.target_height))

            # Exportar
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio.m4a'),
                remove_temp=True,
                fps=clip.fps
            )

            clip.close()
            final_video.close()
            logger.info(f"Solid background created: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error creating solid background: {str(e)}")
            raise

    def apply_mirror_effect(self, video_path: str, output_path: str) -> str:
        """
        Aplica efecto espejo horizontal (mirror) para evadir detección de copyright
        """
        try:
            logger.info("Applying mirror effect...")
            clip = VideoFileClip(video_path)
            mirrored_clip = clip.with_effects([MirrorX()])

            mirrored_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio.m4a'),
                remove_temp=True,
                fps=clip.fps
            )

            clip.close()
            mirrored_clip.close()
            logger.info(f"Mirror effect applied: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error applying mirror effect: {str(e)}")
            raise

    def apply_speed_change(self, video_path: str, output_path: str, speed_factor: float = 1.02) -> str:
        """
        Aplica un cambio imperceptible de velocidad (ej. 1.02x) para evadir copyright
        """
        try:
            logger.info(f"Applying speed change: {speed_factor}x...")
            clip = VideoFileClip(video_path)
            speed_clip = clip.with_effects([MultiplySpeed(speed_factor)])

            speed_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio.m4a'),
                remove_temp=True,
                fps=clip.fps
            )

            clip.close()
            speed_clip.close()
            logger.info(f"Speed change applied: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error applying speed change: {str(e)}")
            raise

    def adjust_color_tone(self, video_path: str, output_path: str, adjustment: float = 1.05) -> str:
        """
        Ajusta el tono de color ligeramente para evadir detección
        """
        try:
            logger.info("Adjusting color tone...")
            clip = VideoFileClip(video_path)

            def color_adjust(get_frame, t):
                frame = get_frame(t)
                # Ajustar brillo ligeramente
                adjusted = np.clip(frame * adjustment, 0, 255).astype(np.uint8)
                return adjusted

            adjusted_clip = clip.fl(color_adjust)

            adjusted_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio.m4a'),
                remove_temp=True,
                fps=clip.fps
            )

            clip.close()
            adjusted_clip.close()
            logger.info(f"Color tone adjusted: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error adjusting color tone: {str(e)}")
            raise

    def process_video(
        self,
        video_path: str,
        output_filename: str,
        reframe: bool = True,
        background_type: str = "blur",  # "blur" o "solid"
        background_color: Tuple[int, int, int] = (0, 0, 0),
        apply_mirror: bool = True,
        apply_speed: bool = True,
        speed_factor: float = 1.02,
        apply_color_adjust: bool = True
    ) -> str:
        """
        Procesa un video aplicando todos los efectos seleccionados

        Args:
            video_path: Ruta del video original
            output_filename: Nombre del archivo de salida
            reframe: Si debe re-enmarcar a 9:16
            background_type: Tipo de fondo ("blur" o "solid")
            background_color: Color del fondo si es sólido (R, G, B)
            apply_mirror: Si debe aplicar efecto espejo
            apply_speed: Si debe cambiar la velocidad
            speed_factor: Factor de velocidad (1.02 = 2% más rápido)
            apply_color_adjust: Si debe ajustar el tono de color

        Returns:
            Ruta del video procesado
        """
        try:
            # Validate the input video before any processing
            video_info = validate_video(video_path)
            logger.info(
                f"Starting processing for: {video_path} "
                f"({video_info['codec']} {video_info['width']}x{video_info['height']})"
            )

            current_video = video_path
            output_path = str(self.output_path / output_filename)

            # 1. Re-enmarcar si es necesario
            if reframe:
                info = self.get_video_info(current_video)
                aspect_ratio = info.get('aspect_ratio', 1)

                # Solo re-enmarcar si no es 9:16
                if not (0.55 <= aspect_ratio <= 0.58):  # ~9:16 = 0.5625
                    temp_output = str(self.temp_path / f"reframed_{output_filename}")

                    if background_type == "blur":
                        current_video = self.create_blur_background(current_video, temp_output)
                    else:
                        current_video = self.create_solid_background(current_video, temp_output, background_color)

            # 2. Aplicar efectos anti-copyright
            if apply_mirror:
                temp_output = str(self.temp_path / f"mirrored_{output_filename}")
                current_video = self.apply_mirror_effect(current_video, temp_output)

            if apply_speed:
                temp_output = str(self.temp_path / f"speed_{output_filename}")
                current_video = self.apply_speed_change(current_video, temp_output, speed_factor)

            if apply_color_adjust:
                temp_output = str(self.temp_path / f"color_{output_filename}")
                current_video = self.adjust_color_tone(current_video, temp_output)

            # 3. Mover archivo final a la carpeta de salida
            if current_video != output_path:
                import shutil
                shutil.move(current_video, output_path)

            logger.info(f"Video processing completed: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise


if __name__ == "__main__":
    # Test
    processor = VideoProcessor()
    test_video = input("Enter video path to test: ")
    result = processor.process_video(
        test_video,
        "test_output.mp4",
        reframe=True,
        background_type="blur",
        apply_mirror=True,
        apply_speed=True
    )
    print(f"\nProcessed video: {result}")
