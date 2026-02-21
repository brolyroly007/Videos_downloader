"""
Tests for modules.video_processor.VideoProcessor

Note: These tests only exercise initialization and attribute defaults.
Heavy video-processing logic (which depends on MoviePy / OpenCV) is not
invoked here so the tests stay fast and dependency-light.
"""

import pytest
from pathlib import Path

from modules.video_processor import VideoProcessor


class TestVideoProcessorInit:
    """Initialization tests."""

    def test_init_creates_directories(self, tmp_path: Path):
        """VideoProcessor must create temp and output directories."""
        temp_dir = tmp_path / "tmp_proc"
        out_dir = tmp_path / "out_proc"

        assert not temp_dir.exists()
        assert not out_dir.exists()

        processor = VideoProcessor(
            temp_path=str(temp_dir),
            output_path=str(out_dir),
        )

        assert temp_dir.is_dir()
        assert out_dir.is_dir()
        assert processor.temp_path == temp_dir
        assert processor.output_path == out_dir

    def test_target_dimensions(self, tmp_path: Path):
        """Default target dimensions should be 1080x1920 (9:16 vertical)."""
        processor = VideoProcessor(
            temp_path=str(tmp_path / "tmp"),
            output_path=str(tmp_path / "out"),
        )

        assert processor.target_width == 1080
        assert processor.target_height == 1920
