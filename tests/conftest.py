"""
Shared fixtures for the test suite.

The top-level shimming block patches moviepy so that modules written for the
moviepy 2.x import style (``from moviepy import VideoFileClip``) can be
imported even when only moviepy 1.x is installed.  This is executed once at
collection time, before any test module touches ``modules.video_processor``
or ``app``.
"""

import sys
import types
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# MoviePy 1.x -> 2.x compatibility shim
# ---------------------------------------------------------------------------
# moviepy 2.x exposes classes directly from the ``moviepy`` namespace while
# 1.x hides them behind ``moviepy.editor``.  If we detect the old version we
# inject the missing names so that ``from moviepy import VideoFileClip`` works.

try:
    from moviepy import VideoFileClip  # moviepy 2.x style
except ImportError:
    try:
        import moviepy.editor as _editor

        # Inject 2.x names into the top-level moviepy package
        import moviepy as _moviepy_pkg

        for _name in (
            "VideoFileClip",
            "CompositeVideoClip",
            "ColorClip",
            "ImageClip",
            "TextClip",
        ):
            if not hasattr(_moviepy_pkg, _name):
                setattr(_moviepy_pkg, _name, getattr(_editor, _name, MagicMock()))
    except Exception:
        # moviepy not installed at all -- stub everything
        _moviepy_pkg = types.ModuleType("moviepy")
        for _name in (
            "VideoFileClip",
            "CompositeVideoClip",
            "ColorClip",
            "ImageClip",
            "TextClip",
        ):
            setattr(_moviepy_pkg, _name, MagicMock())
        sys.modules["moviepy"] = _moviepy_pkg

# Also ensure the moviepy.video.fx sub-names used by video_processor exist
try:
    from moviepy.video.fx import Resize  # noqa: F401
except (ImportError, AttributeError):
    _fx_mod = sys.modules.get("moviepy.video.fx") or types.ModuleType("moviepy.video.fx")
    for _name in ("Resize", "MirrorX", "MultiplySpeed"):
        if not hasattr(_fx_mod, _name):
            setattr(_fx_mod, _name, MagicMock())
    sys.modules.setdefault("moviepy.video.fx", _fx_mod)
    sys.modules.setdefault("moviepy.video", types.ModuleType("moviepy.video"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_download_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory for downloads."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


@pytest.fixture
def tmp_processed_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory for processed files."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    return processed_dir


@pytest.fixture
def client():
    """
    Provides a factory that yields an httpx AsyncClient wired to the FastAPI app.

    Usage inside an async test::

        async with client() as c:
            resp = await c.get("/")
    """
    from httpx import AsyncClient, ASGITransport
    from app import app

    def _make_client():
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    return _make_client


@pytest.fixture
def sample_urls() -> dict:
    """Returns sample URLs for each supported platform."""
    return {
        "tiktok": "https://www.tiktok.com/@user/video/7123456789012345678",
        "instagram": "https://www.instagram.com/reel/ABC123/",
        "youtube": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    }
