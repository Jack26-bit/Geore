"""
main.py — FastAPI backend for GEORE.

Exposes the same agentic pipeline (router → toolkit → prompt → VLM)
that app.py ran inline in Streamlit, but as HTTP endpoints.
"""

import json
import time
import numpy as np
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from router import classify_query
from rs_toolkit import compute_change_mask, compute_fusion_stats
from prompts import build_prompt
from vlm_client import call_vlm

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="GEORE", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers (ported from app.py) ─────────────────────────────────────────────

def parse_grounding_json(text: str) -> dict | None:
    """Extract JSON bbox from grounding model response."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def compute_confidence(task_type: str, toolkit_output: dict, answer: str) -> str:
    """
    Simple confidence heuristic based on toolkit/LLM agreement.

    "high" if toolkit stats and LLM narration direction agree.
    "moderate" otherwise.
    """
    answer_lower = answer.lower() if answer else ""

    if task_type == "change":
        pct = toolkit_output.get("pct_changed", 0) if toolkit_output else 0
        if pct > 5 and any(
            w in answer_lower
            for w in [
                "significant", "substantial", "major",
                "large", "considerable", "extensive",
            ]
        ):
            return "high"
        elif pct <= 5 and any(
            w in answer_lower
            for w in [
                "minor", "minimal", "slight",
                "little", "no significant", "negligible",
            ]
        ):
            return "high"
        return "moderate"

    elif task_type == "fusion":
        agreement = toolkit_output.get("agreement_pct", 0) if toolkit_output else 0
        if agreement > 50:
            return "high"
        return "moderate"

    elif task_type == "grounding":
        parsed = parse_grounding_json(answer)
        if parsed and parsed.get("bbox", [0, 0, 0, 0]) != [0, 0, 0, 0]:
            return "high"
        return "moderate"

    else:  # vqa
        if len(answer) > 100:
            return "high"
        return "moderate"


def _load_image(upload: UploadFile) -> Image.Image:
    """Read an UploadFile into a PIL RGB Image."""
    data = upload.file.read()
    return Image.open(BytesIO(data)).convert("RGB")


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    image1: UploadFile = File(...),
    query: str = Form(...),
    image2: Optional[UploadFile] = File(None),
    has_sar: bool = Form(False),
):
    """
    Run the full GEORE analysis pipeline.

    Multipart form fields:
        image1  — file (required)
        image2  — file (optional)
        query   — str  (required)
        has_sar — bool (optional, default false)
    """

    # ── Load images ──────────────────────────────────────────────────────
    img1 = _load_image(image1)
    images = [img1]
    img2 = None

    if image2 is not None and image2.filename:
        img2 = _load_image(image2)
        images.append(img2)

    num_images = len(images)

    # ── Step 1: Route the query ──────────────────────────────────────────
    task_type = classify_query(query, num_images, has_sar)

    # ── Step 2: Run toolkit (if needed) ──────────────────────────────────
    toolkit_output = None
    tool_called = None

    if task_type == "change" and num_images == 2:
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        toolkit_output = compute_change_mask(arr1, arr2)
        # Remove numpy array — not JSON-serializable
        toolkit_output.pop("change_mask", None)
        tool_called = "compute_change_mask"

    elif task_type == "fusion" and num_images == 2:
        arr_opt = np.array(img1)
        arr_sar = np.array(img2)
        toolkit_output = compute_fusion_stats(arr_opt, arr_sar)
        tool_called = "compute_fusion_stats"

    # ── Step 3: Build prompt and call VLM ────────────────────────────────
    prompt = build_prompt(task_type, query, toolkit_output)
    start_time = time.time()
    answer, provider = call_vlm(prompt, images)
    elapsed = round(time.time() - start_time, 2)

    # ── Step 4: Compute confidence ───────────────────────────────────────
    confidence = compute_confidence(task_type, toolkit_output, answer)

    # ── Step 5: Extract bbox for grounding ───────────────────────────────
    bbox = None
    if task_type == "grounding":
        parsed = parse_grounding_json(answer)
        if parsed and parsed.get("bbox", [0, 0, 0, 0]) != [0, 0, 0, 0]:
            bbox = parsed["bbox"]

    # ── Step 6: Determine model_used label ───────────────────────────────
    if "Gemini" in provider:
        model_used = "gemini-2.5-flash"
    elif "NVIDIA" in provider:
        model_used = "nvidia-fallback"
    else:
        model_used = "none"

    # ── Assemble response ────────────────────────────────────────────────
    return {
        "answer": answer,
        "task": task_type,
        "bbox": bbox,
        "confidence": confidence,
        "execution_trace": {
            "task": task_type,
            "tool_called": tool_called,
            "tool_output": toolkit_output,
            "model_used": model_used,
            "provider": provider,
            "response_time_seconds": elapsed,
        },
    }
