"""
Configuración centralizada con pydantic-settings.

Todas las variables de entorno que el código realmente usa se declaran aquí,
en un único lugar, con sus valores por defecto. Se expone un singleton
`settings` y, por compatibilidad hacia atrás, las constantes que otros módulos
ya importaban (MAX_DOWNLOAD_RETRIES, RETRY_BASE_DELAY, DOWNLOAD_TIMEOUT).
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"

    # Datos / persistencia
    data_dir: str = "."

    # Autenticación
    auth_enabled: bool = False

    # Whisper (subtítulos)
    whisper_model_size: str = "base"

    # TikTok / upload
    tiktok_headless: bool = False

    # Descargas
    max_download_retries: int = 3
    retry_base_delay: float = 2.0  # segundos
    download_timeout: int = 300  # segundos
    ytdlp_insecure_ssl: bool = False
    ytdlp_path: Optional[str] = None

    # Subsistemas opcionales
    enable_queue_workers: bool = False
    enable_scheduled_backups: bool = False

    # Servicios externos (opcionales)
    openai_api_key: Optional[str] = None
    redis_url: Optional[str] = None


settings = Settings()

# --- Compatibilidad hacia atrás (constantes ya importadas por otros módulos) ---
MAX_DOWNLOAD_RETRIES: int = settings.max_download_retries
RETRY_BASE_DELAY: float = settings.retry_base_delay
DOWNLOAD_TIMEOUT: int = settings.download_timeout
