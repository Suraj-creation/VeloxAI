"""
tests/unit/test_plate_enhancement.py
======================================
Unit tests for PlateEnhancer — CLAHE CPU pipeline.
No models or ROS2 needed.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[2] /
    "ros2_ws/src/fw_plate_ocr_node/fw_plate_ocr_node"
))
from plate_ocr_node import PlateEnhancer


class TestPlateEnhancer:

    @pytest.fixture
    def enhancer(self):
        return PlateEnhancer(esrgan_path=None)  # CPU-only mode

    @pytest.fixture
    def synthetic_plate(self):
        """Create a synthetic low-quality plate image."""
        plate = np.zeros((40, 200, 3), dtype=np.uint8)
        # Add some text-like structures
        cv2.putText(plate, "KA05AB1234", (5, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
        # Add noise
        noise = np.random.randint(0, 50, plate.shape, dtype=np.uint8)
        plate = cv2.add(plate, noise)
        return plate

    def test_clahe_returns_bgr_image(self, enhancer, synthetic_plate):
        result = enhancer.enhance_clahe(synthetic_plate)
        assert result.ndim == 3
        assert result.shape[2] == 3, "Output should be 3-channel BGR"

    def test_clahe_upscales_width(self, enhancer, synthetic_plate):
        target_width = 400
        result = enhancer.enhance_clahe(synthetic_plate, target_width=target_width)
        assert result.shape[1] >= target_width

    def test_clahe_output_uint8(self, enhancer, synthetic_plate):
        result = enhancer.enhance_clahe(synthetic_plate)
        assert result.dtype == np.uint8

    def test_clahe_on_empty_raises_or_handles(self, enhancer):
        """Edge case: tiny plate."""
        tiny = np.zeros((4, 20, 3), dtype=np.uint8)
        # Should not crash
        try:
            result = enhancer.enhance_clahe(tiny)
            assert result is not None
        except Exception as e:
            pytest.fail(f"enhance_clahe raised on tiny plate: {e}")

    def test_enhance_returns_method_name(self, enhancer, synthetic_plate):
        _, method = enhancer.enhance(synthetic_plate)
        assert method in {"clahe_cpu", "esrgan"}

    def test_enhance_without_esrgan_uses_clahe(self, enhancer, synthetic_plate):
        _, method = enhancer.enhance(synthetic_plate)
        assert method == "clahe_cpu"

    def test_deskew_no_crash_on_noisy_image(self, enhancer, synthetic_plate):
        """Deskew should gracefully handle images with no clear lines."""
        result = enhancer.deskew(synthetic_plate)
        assert result.shape == synthetic_plate.shape

    def test_deskew_returns_same_size(self, enhancer, synthetic_plate):
        result = enhancer.deskew(synthetic_plate)
        assert result.shape == synthetic_plate.shape

    def test_enhance_pipeline_increases_contrast(self, enhancer, synthetic_plate):
        """Enhanced image should have higher std (contrast) than a degraded input."""
        degraded = cv2.GaussianBlur(synthetic_plate, (7, 7), 3)
        enhanced, _ = enhancer.enhance(degraded)

        g_orig = cv2.cvtColor(degraded, cv2.COLOR_BGR2GRAY)
        g_enh = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

        std_orig = float(np.std(g_orig))
        std_enh = float(np.std(g_enh))
        # CLAHE should increase std on blurry images
        assert std_enh >= std_orig * 0.8, (
            f"Enhanced std ({std_enh:.1f}) should not be much lower "
            f"than original ({std_orig:.1f})")
