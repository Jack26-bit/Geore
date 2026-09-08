"""
prompts.py — Prompt templates for GEORE task types.

Each template frames Gemini as a remote-sensing analyst.
Templates use str.format() for variable interpolation.
"""

# ── System framing (shared) ──────────────────────────────────────────────────

SYSTEM_FRAMING = (
    "You are GEORE, an expert remote-sensing image analyst. "
    "You analyze satellite and aerial imagery with precision. "
    "Base your answers only on what is visible in the provided image(s). "
    "Be specific about spatial locations (top-left, center, etc.) and "
    "provide quantitative observations when possible."
)

# ── VQA: Single-image visual question answering ─────────────────────────────

VQA_PROMPT = """{system}

The user has uploaded a satellite/aerial image and asks the following question:

**User query:** {query}

Provide a clear, detailed answer based solely on what you observe in the image.
Structure your response with:
1. **Direct answer** to the question
2. **Key observations** supporting your answer
3. **Confidence note** — mention if anything is ambiguous or hard to determine from this view
""".strip()

# ── Grounding: Locate and bound objects in the image ─────────────────────────

GROUNDING_PROMPT = """{system}

The user wants you to locate a specific feature in this satellite/aerial image.

**User query:** {query}

You MUST respond in the following JSON format and nothing else:

```json
{{
  "bbox": [x_min, y_min, x_max, y_max],
  "description": "One-sentence description of what was found at this location."
}}
```

Coordinate rules:
- All values are **normalized between 0.0 and 1.0** relative to image dimensions.
- `x_min`, `x_max` are horizontal (left=0, right=1).
- `y_min`, `y_max` are vertical (top=0, bottom=1).
- If the feature is not found, return: `{{"bbox": [0, 0, 0, 0], "description": "Feature not found in the image."}}`
""".strip()

# ── Change Narration: Describe changes between two temporal images ───────────

CHANGE_NARRATION_PROMPT = """{system}

The user has uploaded two satellite/aerial images of the same area taken at different times.
Image 1 is the **earlier/before** image. Image 2 is the **later/after** image.

A pixel-level change analysis has already been computed with the following results:
- **Percentage of area changed:** {pct_changed}%
- **Number of change regions detected:** {num_regions}
- **Change region bounding boxes (x, y, w, h in pixels):** {change_regions}

**User query:** {query}

Using both the computed statistics above AND your visual interpretation of the two images, provide:
1. **Summary** — What is the overall nature and magnitude of the change?
2. **Key changes** — Describe the 2–3 most significant changes you observe, referencing their spatial location (e.g., "in the northeastern quadrant" or "along the river").
3. **Likely cause** — What might have caused these changes? (e.g., urbanization, seasonal variation, flood damage, deforestation)
4. **Agreement check** — Do your visual observations align with the computed {pct_changed}% change statistic? Note any discrepancies.
""".strip()

# ── Fusion Narration: Joint interpretation of optical + SAR ──────────────────

FUSION_NARRATION_PROMPT = """{system}

The user has uploaded two co-registered images of the same area:
- **Image 1:** Optical (visible/multispectral) imagery
- **Image 2:** SAR (Synthetic Aperture Radar) imagery

A cross-modal analysis has already been computed:
- **Built-up area (from SAR high-backscatter):** {built_up_pct}%
- **Vegetation coverage (from optical NDVI):** {vegetation_pct}%
- **Water coverage (from optical NDWI):** {water_pct}%
- **Cross-modal agreement:** {agreement_pct}%

**User query:** {query}

Using both the computed statistics AND your visual interpretation of both images, provide:
1. **Land cover summary** — Characterize the overall land cover composition.
2. **SAR interpretation** — What does the radar imagery reveal about surface roughness, built structures, or moisture?
3. **Optical interpretation** — What does the visible imagery show about vegetation, water, and land use?
4. **Fusion insight** — What additional understanding emerges from combining both data sources that neither alone would provide?
5. **Agreement assessment** — The computed cross-modal agreement is {agreement_pct}%. Explain what this means and whether it's consistent with what you see.
""".strip()


def build_prompt(task_type: str, query: str, toolkit_output: dict = None) -> str:
    """
    Build the final prompt string for a given task type.

    Args:
        task_type:      One of "vqa", "grounding", "change", "fusion".
        query:          The user's natural-language question.
        toolkit_output: Dict of computed stats (for change/fusion tasks).

    Returns:
        Formatted prompt string ready to send to the VLM.
    """
    if task_type == "vqa":
        return VQA_PROMPT.format(system=SYSTEM_FRAMING, query=query)

    elif task_type == "grounding":
        return GROUNDING_PROMPT.format(system=SYSTEM_FRAMING, query=query)

    elif task_type == "change":
        stats = toolkit_output or {}
        return CHANGE_NARRATION_PROMPT.format(
            system=SYSTEM_FRAMING,
            query=query,
            pct_changed=stats.get("pct_changed", "N/A"),
            num_regions=len(stats.get("change_regions", [])),
            change_regions=stats.get("change_regions", []),
        )

    elif task_type == "fusion":
        stats = toolkit_output or {}
        return FUSION_NARRATION_PROMPT.format(
            system=SYSTEM_FRAMING,
            query=query,
            built_up_pct=stats.get("built_up_pct", "N/A"),
            vegetation_pct=stats.get("vegetation_pct", "N/A"),
            water_pct=stats.get("water_pct", "N/A"),
            agreement_pct=stats.get("agreement_pct", "N/A"),
        )

    else:
        # Fallback — treat as VQA
        return VQA_PROMPT.format(system=SYSTEM_FRAMING, query=query)


# ── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Prompts self-test:\n")

    for task in ["vqa", "grounding", "change", "fusion"]:
        dummy_stats = {
            "pct_changed": 12.5,
            "change_regions": [(10, 20, 50, 50)],
            "built_up_pct": 30.0,
            "vegetation_pct": 45.0,
            "water_pct": 10.0,
            "agreement_pct": 72.0,
        }
        prompt = build_prompt(task, "What changed here?", dummy_stats)
        print(f"  [PASS] {task.upper()} prompt: {len(prompt)} chars")
        print(f"    First 80 chars: {prompt[:80]}...\n")

    print("All prompt templates OK!")
