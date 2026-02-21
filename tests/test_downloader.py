"""
Tests for modules.downloader.VideoDownloader
"""

import pytest
from pathlib import Path

from modules.downloader import VideoDownloader


class TestVideoDownloaderInit:
    """Initialization tests."""

    def test_init_creates_directories(self, tmp_path: Path):
        """VideoDownloader.__init__ must create download and cookies dirs."""
        dl_dir = tmp_path / "dl"
        ck_dir = tmp_path / "ck"

        # Neither directory exists yet
        assert not dl_dir.exists()
        assert not ck_dir.exists()

        downloader = VideoDownloader(
            download_path=str(dl_dir),
            cookies_path=str(ck_dir),
        )

        assert dl_dir.is_dir()
        assert ck_dir.is_dir()
        assert downloader.download_path == dl_dir
        assert downloader.cookies_path == ck_dir


class TestGetPlatform:
    """Tests for _get_platform URL detection."""

    @pytest.fixture(autouse=True)
    def _setup_downloader(self, tmp_path: Path):
        self.downloader = VideoDownloader(
            download_path=str(tmp_path / "dl"),
            cookies_path=str(tmp_path / "ck"),
        )

    def test_get_platform_tiktok(self):
        """Standard and short TikTok URLs are detected."""
        assert self.downloader._get_platform("https://www.tiktok.com/@user/video/123") == "tiktok"
        assert self.downloader._get_platform("https://vm.tiktok.com/ZMxxxxxx/") == "tiktok"

    def test_get_platform_instagram(self):
        """Instagram reel/post URLs are detected."""
        assert self.downloader._get_platform("https://www.instagram.com/reel/ABC123/") == "instagram"
        assert self.downloader._get_platform("https://instagram.com/p/XYZ789/") == "instagram"

    def test_get_platform_youtube(self):
        """YouTube (long and short) URLs are detected."""
        assert self.downloader._get_platform("https://www.youtube.com/watch?v=abc123") == "youtube"
        assert self.downloader._get_platform("https://youtu.be/abc123") == "youtube"
        assert self.downloader._get_platform("https://www.youtube.com/shorts/abc123") == "youtube"

    def test_get_platform_facebook(self):
        """Facebook and fb.watch URLs are detected."""
        assert self.downloader._get_platform("https://www.facebook.com/watch?v=123") == "facebook"
        assert self.downloader._get_platform("https://fb.watch/abc123/") == "facebook"

    def test_get_platform_unknown(self):
        """Unrecognised URLs return 'unknown'."""
        assert self.downloader._get_platform("https://example.com/video.mp4") == "unknown"
        assert self.downloader._get_platform("https://vimeo.com/123456") == "unknown"


class TestGetBrowserCookiesPath:
    """Tests for _get_browser_cookies_path."""

    def test_get_browser_cookies_path_no_cookies(self, tmp_path: Path):
        """Returns None when the cookies file does not exist."""
        downloader = VideoDownloader(
            download_path=str(tmp_path / "dl"),
            cookies_path=str(tmp_path / "ck"),
        )
        assert downloader._get_browser_cookies_path() is None

    def test_get_browser_cookies_path_with_cookies(self, tmp_path: Path):
        """Returns the path string when the cookies file exists."""
        ck_dir = tmp_path / "ck"
        downloader = VideoDownloader(
            download_path=str(tmp_path / "dl"),
            cookies_path=str(ck_dir),
        )

        # Create the expected cookies file
        cookies_file = ck_dir / "tiktok_cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        result = downloader._get_browser_cookies_path()
        assert result is not None
        assert result == str(cookies_file)
