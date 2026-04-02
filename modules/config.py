"""
Configuration settings for the video downloader.
"""

import os

# Retry settings
MAX_DOWNLOAD_RETRIES: int = int(os.environ.get("MAX_DOWNLOAD_RETRIES", "3"))
RETRY_BASE_DELAY: float = float(os.environ.get("RETRY_BASE_DELAY", "2.0"))  # seconds
DOWNLOAD_TIMEOUT: int = int(os.environ.get("DOWNLOAD_TIMEOUT", "300"))  # seconds
