"""
test_rs_toolkit.py — Unit tests for remote-sensing deterministic toolkit.
"""

import unittest
import numpy as np
import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rs_toolkit import (
    _to_float,
    _safe_ratio,
    compute_ndvi,
    compute_ndwi,
    compute_change_mask,
    compute_fusion_stats,
    get_toolkit_info,
)


class TestRSToolkit(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_to_float_uint8(self):
        arr = np.array([0, 128, 255], dtype=np.uint8)
        norm = _to_float(arr)
        self.assertEqual(norm.dtype, np.float32)
        self.assertAlmostEqual(float(norm[0]), 0.0)
        self.assertAlmostEqual(float(norm[2]), 1.0)

    def test_safe_ratio_zero_denominator(self):
        a = np.zeros((5, 5), dtype=np.float32)
        b = np.zeros((5, 5), dtype=np.float32)
        ratio = _safe_ratio(a, b)
        self.assertTrue(np.all(ratio == 0.0))

    def test_safe_ratio_valid(self):
        a = np.full((3, 3), 3.0, dtype=np.float32)
        b = np.full((3, 3), 1.0, dtype=np.float32)
        ratio = _safe_ratio(a, b)
        # (3 - 1) / (3 + 1) = 2/4 = 0.5
        self.assertTrue(np.allclose(ratio, 0.5))

    def test_compute_ndvi_rgb(self):
        rgb_image = np.zeros((50, 50, 3), dtype=np.uint8)
        # Green channel high, Red low -> high green/NIR proxy
        rgb_image[:, :, 1] = 200
        rgb_image[:, :, 0] = 50
        ndvi = compute_ndvi(rgb_image)
        self.assertEqual(ndvi.shape, (50, 50))
        self.assertTrue(np.all(ndvi >= -1.0) and np.all(ndvi <= 1.0))

    def test_compute_ndvi_multispectral(self):
        ms_image = np.zeros((50, 50, 4), dtype=np.uint8)
        # NIR channel index 3 = 220, Red channel index 2 = 40
        ms_image[:, :, 3] = 220
        ms_image[:, :, 2] = 40
        ndvi = compute_ndvi(ms_image)
        self.assertEqual(ndvi.shape, (50, 50))
        self.assertTrue(np.all(ndvi > 0))

    def test_compute_ndvi_grayscale_fallback(self):
        gray = np.full((30, 30), 128, dtype=np.uint8)
        ndvi = compute_ndvi(gray)
        self.assertEqual(ndvi.shape, (30, 30))
        self.assertTrue(np.all(ndvi == 0.0))

    def test_compute_ndwi(self):
        rgb_image = np.zeros((50, 50, 3), dtype=np.uint8)
        rgb_image[:, :, 2] = 200  # Blue
        rgb_image[:, :, 1] = 80   # Green
        ndwi = compute_ndwi(rgb_image)
        self.assertEqual(ndwi.shape, (50, 50))
        self.assertTrue(np.all(ndwi >= -1.0) and np.all(ndwi <= 1.0))

    def test_compute_change_mask_identical(self):
        img = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        result = compute_change_mask(img, img, threshold=0.1)
        self.assertEqual(result["pct_changed"], 0.0)
        self.assertEqual(len(result["change_regions"]), 0)

    def test_compute_change_mask_different(self):
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.full((100, 100, 3), 255, dtype=np.uint8)
        result = compute_change_mask(img1, img2, threshold=0.1)
        self.assertGreater(result["pct_changed"], 90.0)

    def test_compute_fusion_stats(self):
        optical = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
        sar = np.random.randint(0, 255, (80, 80), dtype=np.uint8)
        stats = compute_fusion_stats(optical, sar)
        self.assertIn("built_up_pct", stats)
        self.assertIn("vegetation_pct", stats)
        self.assertIn("water_pct", stats)
        self.assertIn("agreement_pct", stats)

    def test_get_toolkit_info(self):
        info = get_toolkit_info()
        self.assertEqual(info["version"], "1.1.0")
        self.assertIn("NDVI", info["supported_indices"])
        self.assertIn("default_thresholds", info)


if __name__ == "__main__":
    unittest.main()
