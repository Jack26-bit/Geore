"""
router.py — Rule-based query classifier for GEORE.

Deterministic, zero-latency routing. No LLM calls.
Priority order: change > fusion > grounding > vqa (default).
"""

import re

# ── Keyword sets ──────────────────────────────────────────────────────────────

TEMPORAL_KEYWORDS = {
    "change", "changed", "changes", "changing",
    "between", "before", "after", "before/after",
    "compare", "compared", "comparison",
    "differ", "different", "difference", "differences",
    "evolve", "evolved", "evolution",
    "transform", "transformed", "transformation",
    "over time", "temporal", "progress", "progression",
    "develop", "developed", "development",
    "growth", "grown", "expand", "expanded",
    "deforestation", "urbanization", "erosion",
    "flood", "flooded", "flooding",
    "pre-", "post-",
}

GROUNDING_PHRASES = [
    "highlight",
    "locate",
    "where is",
    "where are",
    "show me the",
    "show me where",
    "find the",
    "find all",
    "point out",
    "identify the location",
    "mark the",
    "outline the",
    "bounding box",
    "bbox",
    "detect the",
    "spot the",
    "pinpoint",
]


def classify_query(query: str, num_images: int, has_sar: bool) -> str:
    """
    Classify a user query into one of four task types.

    Args:
        query:      The user's natural-language question.
        num_images: Number of images uploaded (1 or 2).
        has_sar:    Whether the user flagged an image as SAR.

    Returns:
        One of: "change", "fusion", "grounding", "vqa".
    """
    q = query.lower().strip()

    # ── Priority 1: Change detection (2 images + temporal language) ───────
    if num_images == 2:
        for keyword in TEMPORAL_KEYWORDS:
            if keyword in q:
                return "change"

    # ── Priority 2: Fusion (2 images + SAR flag) ─────────────────────────
    if num_images == 2 and has_sar:
        return "fusion"

    # ── Priority 3: Grounding (spatial phrases) ──────────────────────────
    for phrase in GROUNDING_PHRASES:
        if phrase in q:
            return "grounding"

    # ── Priority 4: Default VQA ──────────────────────────────────────────
    return "vqa"


# ── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("What changed between 2020 and 2023?", 2, False, "change"),
        ("Compare these two dates", 2, False, "change"),
        ("Analyze optical and radar data", 2, True, "fusion"),
        ("Highlight the water body", 1, False, "grounding"),
        ("Where is the airport?", 1, False, "grounding"),
        ("Show me the deforested area", 1, False, "grounding"),
        ("What type of land use is shown?", 1, False, "vqa"),
        ("Describe this satellite image", 1, False, "vqa"),
    ]

    print("Router self-test:")
    all_pass = True
    for query, n_img, sar, expected in tests:
        result = classify_query(query, n_img, sar)
        status = "[PASS]" if result == expected else "[FAIL]"
        if result != expected:
            all_pass = False
        print(f"  {status}  classify({query!r}, {n_img}, {sar}) -> {result!r}  (expected {expected!r})")

    print(f"\n{'All tests passed!' if all_pass else 'SOME TESTS FAILED!'}")
