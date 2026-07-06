"""
Subtitle Generator Module
Usa OpenAI Whisper para transcribir audio a texto y generar subtítulos
Puede "quemar" los subtítulos en el video con estilo personalizado
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

# Optional imports - whisper may not be installed
try:
    import whisper
    import torch
    WHISPER_AVAILABLE = True
except ImportError:
    whisper = None
    torch = None
    WHISPER_AVAILABLE = False
    logging.warning("Whisper not available - subtitle generation disabled")

# MoviePy 2.x API
try:
    from moviepy import VideoFileClip, TextClip, CompositeVideoClip
    from moviepy.video.tools.subtitles import SubtitlesClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    VideoFileClip = None
    TextClip = None
    CompositeVideoClip = None
    SubtitlesClip = None
    MOVIEPY_AVAILABLE = False
    logging.warning("MoviePy not available - video processing disabled")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Clase para generar y quemar subtítulos en videos usando Whisper AI"""

    def __init__(self, model_size: str = "base", temp_path: str = "temp"):
        """
        Args:
            model_size: Tamaño del modelo Whisper (tiny, base, small, medium, large)
                       - tiny: Más rápido, menos preciso
                       - base: Balance entre velocidad y precisión (RECOMENDADO)
                       - small: Más preciso, más lento
                       - medium/large: Muy preciso, requiere GPU potente
        """
        self.temp_path = Path(temp_path)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.device = "cpu"

        if not WHISPER_AVAILABLE:
            logger.warning("Whisper not installed - subtitle generation will be disabled")
            return

        # Detectar si hay GPU disponible
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        # Cargar modelo Whisper
        try:
            logger.info(f"Loading Whisper model: {model_size}")
            self.model = whisper.load_model(model_size, device=self.device)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model = None

    def extract_audio(self, video_path: str) -> str:
        """Extrae el audio del video a un archivo WAV temporal"""
        try:
            logger.info("Extracting audio from video...")
            audio_path = str(self.temp_path / "temp_audio.wav")

            clip = VideoFileClip(video_path)
            clip.audio.write_audiofile(audio_path, codec='pcm_s16le', logger=None)
            clip.close()

            logger.info(f"Audio extracted: {audio_path}")
            return audio_path

        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            raise

    def transcribe_audio(self, audio_path: str, language: Optional[str] = None) -> Dict:
        """
        Transcribe el audio usando Whisper

        Args:
            audio_path: Ruta al archivo de audio
            language: Código de idioma (ej. 'es', 'en') o None para detección automática

        Returns:
            Diccionario con la transcripción completa y segmentos
        """
        try:
            logger.info("Transcribing audio with Whisper...")

            # Opciones de transcripción
            options = {
                'task': 'transcribe',
                'verbose': False,
            }

            if language:
                options['language'] = language

            # Transcribir
            result = self.model.transcribe(audio_path, **options)

            logger.info(f"Transcription completed. Language detected: {result.get('language', 'unknown')}")
            logger.info(f"Number of segments: {len(result['segments'])}")

            return result

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    def generate_srt(self, transcription: Dict, output_path: str) -> str:
        """
        Genera un archivo .srt desde la transcripción

        Args:
            transcription: Resultado de la transcripción de Whisper
            output_path: Ruta donde guardar el archivo .srt

        Returns:
            Ruta del archivo .srt generado
        """
        try:
            logger.info("Generating SRT file...")

            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(transcription['segments'], start=1):
                    # Formato SRT:
                    # 1
                    # 00:00:00,000 --> 00:00:02,000
                    # Texto del subtítulo

                    start_time = self._format_timestamp(segment['start'])
                    end_time = self._format_timestamp(segment['end'])
                    text = segment['text'].strip()

                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")

            logger.info(f"SRT file generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error generating SRT: {str(e)}")
            raise

    def _format_timestamp(self, seconds: float) -> str:
        """Convierte segundos a formato SRT (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def burn_subtitles(
        self,
        video_path: str,
        srt_path: str,
        output_path: str,
        font: str = "Arial-Bold",
        font_size: int = 60,
        font_color: str = "white",
        stroke_color: str = "black",
        stroke_width: int = 3,
        position: Tuple[str, str] = ("center", "bottom"),
        margin: int = 100
    ) -> str:
        """
        Quema los subtítulos en el video (hardcode)

        Args:
            video_path: Ruta del video original
            srt_path: Ruta del archivo .srt
            output_path: Ruta del video con subtítulos quemados
            font: Fuente del texto
            font_size: Tamaño de la fuente
            font_color: Color del texto
            stroke_color: Color del borde del texto
            stroke_width: Grosor del borde
            position: Posición de los subtítulos (horizontal, vertical)
            margin: Margen desde el borde en píxeles

        Returns:
            Ruta del video con subtítulos quemados
        """
        try:
            logger.info("Burning subtitles into video...")

            # Cargar video
            video = VideoFileClip(video_path)

            # Función generadora de TextClip para cada subtítulo
            def make_textclip(txt):
                return TextClip(
                    text=txt,
                    font=font,
                    font_size=font_size,
                    color=font_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    method='caption',
                    size=(video.w - 100, None)  # Margen lateral
                )

            # Cargar subtítulos
            subtitles = SubtitlesClip(srt_path, make_textclip)

            # Calcular posición
            if position[1] == "bottom":
                y_pos = video.h - margin
            elif position[1] == "top":
                y_pos = margin
            else:  # center
                y_pos = 'center'

            # Posicionar subtítulos
            subtitles = subtitles.with_position((position[0], y_pos))

            # Componer video con subtítulos
            result = CompositeVideoClip([video, subtitles])

            # Exportar
            result.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp-audio-subs.m4a'),
                remove_temp=True,
                fps=video.fps
            )

            video.close()
            result.close()

            logger.info(f"Subtitles burned successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error burning subtitles: {str(e)}")
            raise

    def process_video_with_subtitles(
        self,
        video_path: str,
        output_video_path: str,
        output_srt_path: Optional[str] = None,
        language: Optional[str] = None,
        burn_subs: bool = True,
        **subtitle_style
    ) -> Dict[str, str]:
        """
        Proceso completo: extrae audio, transcribe, genera SRT y opcionalmente quema subtítulos

        Args:
            video_path: Ruta del video original
            output_video_path: Ruta del video con subtítulos (si burn_subs=True)
            output_srt_path: Ruta donde guardar el .srt (opcional)
            language: Código de idioma ('es', 'en', etc.) o None para auto-detección
            burn_subs: Si debe quemar los subtítulos en el video
            **subtitle_style: Argumentos de estilo para burn_subtitles()

        Returns:
            Dict con las rutas del video procesado y el archivo SRT
        """
        try:
            # 1. Extraer audio
            audio_path = self.extract_audio(video_path)

            # 2. Transcribir
            transcription = self.transcribe_audio(audio_path, language)

            # 3. Generar SRT
            if not output_srt_path:
                output_srt_path = str(self.temp_path / "subtitles.srt")

            srt_path = self.generate_srt(transcription, output_srt_path)

            # 4. Quemar subtítulos (opcional)
            final_video_path = video_path
            if burn_subs:
                final_video_path = self.burn_subtitles(
                    video_path,
                    srt_path,
                    output_video_path,
                    **subtitle_style
                )

            # 5. Limpiar audio temporal
            if os.path.exists(audio_path):
                os.remove(audio_path)

            return {
                'video_path': final_video_path,
                'srt_path': srt_path,
                'transcription': transcription['text'],
                'language': transcription.get('language', 'unknown'),
                'segments': transcription['segments']
            }

        except Exception as e:
            logger.error(f"Error in complete subtitle process: {str(e)}")
            raise

    def edit_srt_text(self, srt_path: str, edits: Dict[int, str]) -> str:
        """
        Edita el texto de líneas específicas del SRT

        Args:
            srt_path: Ruta del archivo .srt
            edits: Diccionario {número_de_línea: nuevo_texto}

        Returns:
            Ruta del archivo .srt editado
        """
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Editar líneas específicas
            current_subtitle = 0
            i = 0
            while i < len(lines):
                if lines[i].strip().isdigit():
                    current_subtitle = int(lines[i].strip())
                    if current_subtitle in edits:
                        # Saltar número y timestamp
                        i += 2
                        # Reemplazar texto
                        lines[i] = edits[current_subtitle] + '\n'
                i += 1

            # Guardar cambios
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            logger.info(f"SRT file edited successfully: {srt_path}")
            return srt_path

        except Exception as e:
            logger.error(f"Error editing SRT: {str(e)}")
            raise


if __name__ == "__main__":
    # Test
    generator = SubtitleGenerator(model_size="base")
    test_video = input("Enter video path to test: ")

    result = generator.process_video_with_subtitles(
        test_video,
        "output_with_subs.mp4",
        "subtitles.srt",
        language='es',
        burn_subs=True,
        font_size=70,
        font_color='yellow',
        stroke_color='black',
        stroke_width=4
    )

    print(f"\nResult: {result}")
    print(f"\nTranscription: {result['transcription']}")
