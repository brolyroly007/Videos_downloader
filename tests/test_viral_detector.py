"""
Tests for modules.viral_detector (ViralVideo dataclass and ViralDetector)
"""

import pytest
from datetime import datetime

from modules.viral_detector import ViralVideo, ViralDetector


# ---------------------------------------------------------------------------
# ViralVideo dataclass tests
# ---------------------------------------------------------------------------

class TestViralVideo:
    """Tests for the ViralVideo dataclass."""

    @pytest.fixture
    def sample_video(self) -> ViralVideo:
        return ViralVideo(
            url="https://www.tiktok.com/@user/video/123",
            platform="tiktok",
            video_id="123",
            title="Funny cat video",
            author="cat_lover",
            views=1_000_000,
            likes=100_000,
            comments=5_000,
            shares=20_000,
            duration=30,
            hashtags=["fyp", "cats", "funny"],
            thumbnail="https://example.com/thumb.jpg",
            detected_at=datetime(2025, 1, 15, 12, 0, 0),
            viral_score=85.0,
        )

    def test_viral_video_creation(self, sample_video: ViralVideo):
        """All fields are accessible after creation."""
        assert sample_video.url == "https://www.tiktok.com/@user/video/123"
        assert sample_video.platform == "tiktok"
        assert sample_video.video_id == "123"
        assert sample_video.title == "Funny cat video"
        assert sample_video.author == "cat_lover"
        assert sample_video.views == 1_000_000
        assert sample_video.likes == 100_000
        assert sample_video.comments == 5_000
        assert sample_video.shares == 20_000
        assert sample_video.duration == 30
        assert sample_video.hashtags == ["fyp", "cats", "funny"]
        assert sample_video.thumbnail == "https://example.com/thumb.jpg"
        assert sample_video.viral_score == 85.0

    def test_viral_video_engagement_rate(self, sample_video: ViralVideo):
        """engagement_rate = (likes + comments + shares) / views * 100."""
        expected = (100_000 + 5_000 + 20_000) / 1_000_000 * 100  # 12.5
        assert sample_video.engagement_rate == pytest.approx(expected)

    def test_viral_video_engagement_rate_zero_views(self):
        """engagement_rate is 0 when views are 0 (no ZeroDivisionError)."""
        video = ViralVideo(
            url="https://example.com",
            platform="tiktok",
            video_id="000",
            title="No views",
            author="nobody",
            views=0,
            likes=10,
            comments=2,
            shares=1,
            duration=15,
            hashtags=[],
            thumbnail="",
            detected_at=datetime.now(),
            viral_score=0.0,
        )
        assert video.engagement_rate == 0

    def test_viral_video_to_dict(self, sample_video: ViralVideo):
        """to_dict returns a plain dict with detected_at as ISO string."""
        data = sample_video.to_dict()

        assert isinstance(data, dict)
        assert data["url"] == sample_video.url
        assert data["platform"] == "tiktok"
        assert data["views"] == 1_000_000
        assert data["likes"] == 100_000
        assert data["viral_score"] == 85.0
        # detected_at must be serialised to ISO format string
        assert data["detected_at"] == "2025-01-15T12:00:00"


# ---------------------------------------------------------------------------
# ViralDetector tests
# ---------------------------------------------------------------------------

class TestViralDetector:
    """Tests for ViralDetector initialization and configuration."""

    def test_viral_detector_init(self, tmp_path):
        """ViralDetector creates its cache directory on init."""
        cache_dir = tmp_path / "vd_cache"
        assert not cache_dir.exists()

        detector = ViralDetector(cache_dir=str(cache_dir))

        assert cache_dir.is_dir()
        assert detector.cache_dir == cache_dir

    def test_viral_detector_thresholds(self, tmp_path):
        """Default thresholds dict must contain entries for all key platforms."""
        detector = ViralDetector(cache_dir=str(tmp_path / "cache"))

        assert "tiktok" in detector.viral_thresholds
        assert "instagram" in detector.viral_thresholds
        assert "youtube" in detector.viral_thresholds

        # Each platform entry should have the expected keys
        for platform in ("tiktok", "instagram", "youtube"):
            thresholds = detector.viral_thresholds[platform]
            assert "min_views" in thresholds
            assert "min_likes" in thresholds
            assert "min_engagement_rate" in thresholds
            assert "max_duration" in thresholds
