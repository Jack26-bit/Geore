"""
test_router.py — Unit tests for rule-based query classifier.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router import classify_query


class TestRouter(unittest.TestCase):
    def test_change_detection_classification(self):
        # 2 images with temporal keywords -> change
        self.assertEqual(classify_query("What changed between 2020 and 2024?", num_images=2, has_sar=False), "change")
        self.assertEqual(classify_query("Compare the deforestation over time", num_images=2, has_sar=False), "change")

    def test_fusion_classification(self):
        # 2 images with SAR flag -> fusion
        self.assertEqual(classify_query("Analyze urban density", num_images=2, has_sar=True), "fusion")

    def test_grounding_classification(self):
        # 1 image with grounding phrase -> grounding
        self.assertEqual(classify_query("Highlight the river in the image", num_images=1, has_sar=False), "grounding")
        self.assertEqual(classify_query("Where is the airport?", num_images=1, has_sar=False), "grounding")
        self.assertEqual(classify_query("Show me the buildings", num_images=1, has_sar=False), "grounding")

    def test_vqa_default(self):
        # Generic query -> vqa
        self.assertEqual(classify_query("What kind of terrain is visible?", num_images=1, has_sar=False), "vqa")
        self.assertEqual(classify_query("Describe the landscape in detail", num_images=1, has_sar=False), "vqa")


if __name__ == "__main__":
    unittest.main()
