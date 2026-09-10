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

from gee_fetcher import get_coordinates, fetch_optical_multiband, fetch_bitemporal_multiband, fetch_sar_image
from datetime import datetime

import spectral_indices as si

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
    answer_lower = answer.lower() if answer else ""
    if task_type == "change":
        pct = toolkit_output.get("pct_changed", 0) if toolkit_output else 0
        if pct > 5 and any(w in answer_lower for w in ["significant", "substantial", "major", "large", "considerable", "extensive"]):
            return "high"
        elif pct <= 5 and any(w in answer_lower for w in ["minor", "minimal", "slight", "little", "no significant", "negligible"]):
            return "high"
        return "moderate"
    elif task_type == "fusion":
        agreement = toolkit_output.get("agreement_pct", 0) if toolkit_output else 0
        if agreement > 50: return "high"
        return "moderate"
    elif task_type == "grounding":
        parsed = parse_grounding_json(answer)
        if parsed and parsed.get("bbox", [0, 0, 0, 0]) != [0, 0, 0, 0]: return "high"
        return "moderate"
    else:  # vqa
        if len(answer) > 100: return "high"
        return "moderate"


def _load_image(upload: UploadFile) -> Image.Image:
    """Read an UploadFile into a PIL RGB Image."""
    data = upload.file.read()
    return Image.open(BytesIO(data)).convert("RGB")


import os
import uuid
import glob
from fastapi.responses import FileResponse
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import letter

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

def cleanup_sessions(max_sessions=100, max_age_hours=2):
    """
    Delete oldest sessions if there are more than `max_sessions` AND they are older than `max_age_hours`.
    """
    try:
        files = glob.glob(os.path.join(SESSIONS_DIR, "*.json"))
        if len(files) <= max_sessions:
            return
            
        now = time.time()
        # Sort files by modification time (oldest first)
        files.sort(key=os.path.getmtime)
        
        for json_file in files:
            age_hours = (now - os.path.getmtime(json_file)) / 3600.0
            if age_hours > max_age_hours:
                # Delete json
                os.remove(json_file)
                # Delete associated image
                img_file = json_file.replace(".json", ".jpg")
                if os.path.exists(img_file):
                    os.remove(img_file)
                # Check if we are now under the limit
                remaining_files = glob.glob(os.path.join(SESSIONS_DIR, "*.json"))
                if len(remaining_files) <= max_sessions:
                    break
            else:
                # The oldest file is not old enough, so stop deleting
                break
    except Exception as e:
        print("Cleanup error:", e)

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    query: str = Form(...),
    image1: Optional[UploadFile] = File(None),
    image2: Optional[UploadFile] = File(None),
    has_sar: bool = Form(False),
    location: Optional[str] = Form(None)
):
    source_type = "user_upload"
    fetched_coords = None
    fetch_date = None

    images = []
    bands1 = None
    bands2 = None
    bounds = None
    
    if location:
        source_type = "gee_live_fetch"
        lat, lon = get_coordinates(location)
        if lat is None or lon is None:
            return {"error": "Could not geocode location."}
        
        fetched_coords = {"lat": lat, "lon": lon}
        fetch_date = datetime.now().strftime("%Y-%m-%d")
        
        # Determine what to fetch based on simple heuristic or query
        if "change" in query.lower() or "trend" in query.lower() or "deforestation" in query.lower():
            img1_gee, img2_gee, bounds, bands1, bands2 = fetch_bitemporal_multiband(lat, lon)
            if img1_gee and img2_gee:
                images.extend([img1_gee, img2_gee])
        elif has_sar:
            img1_gee, bounds, bands1 = fetch_optical_multiband(lat, lon)
            img2_gee, _ = fetch_sar_image(lat, lon)
            if img1_gee: images.append(img1_gee)
            if img2_gee: images.append(img2_gee)
        else:
            img1_gee, bounds, bands1 = fetch_optical_multiband(lat, lon)
            if img1_gee:
                images.append(img1_gee)
                
        if not images:
            return {"error": "Could not fetch images for the given location."}
        
        img1 = images[0]
        img2 = images[1] if len(images) > 1 else None
    else:
        if image1 is None:
            return {"error": "Must provide either image1 or location."}
        img1 = _load_image(image1)
        images.append(img1)
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
        toolkit_output.pop("change_mask", None)
        tool_called = "compute_change_mask"

    elif task_type == "fusion" and num_images == 2:
        arr_opt = np.array(img1)
        arr_sar = np.array(img2)
        toolkit_output = compute_fusion_stats(arr_opt, arr_sar)
        tool_called = "compute_fusion_stats"

    # ── Feature 2: Explainability Heatmap & Domain Analytics ─────────────
    heatmap_base64 = None
    veg_breakdown = None
    forest_trend = None
    forest_mask = None
    flood_pct = None
    flood_geojson = None

    q_lower = query.lower()
    
    if bands1:
        is_ag = any(w in q_lower for w in ["crop", "vegetation", "agriculture", "farmland", "farm"])
        is_forest = any(w in q_lower for w in ["deforestation", "forest"])
        is_flood = any(w in q_lower for w in ["flood", "waterlogged", "inundation"])
        
        if is_ag:
            ndvi = si.compute_ndvi(bands1)
            heatmap_base64 = si.generate_index_heatmap(ndvi, cmap_name='RdYlGn', vmin=-1, vmax=1)
            veg_breakdown = si.classify_vegetation_proportions(ndvi)
        elif is_forest and bands2 is not None:
            ndvi1 = si.compute_ndvi(bands1)
            ndvi2 = si.compute_ndvi(bands2)
            forest_trend = si.compute_forest_cover_trend(ndvi1, ndvi2)
            forest_mask = si.generate_forest_mask_overlay(ndvi2)
        elif is_flood:
            ndwi = si.compute_ndwi(bands1)
            heatmap_base64 = si.generate_index_heatmap(ndwi, cmap_name='Blues', vmin=-1, vmax=1)
            flood_pct, fmask = si.detect_flood_regions(ndwi)
            if bounds:
                flood_geojson = si.flood_region_to_geojson(fmask, bounds)
        else:
            # Generic Heatmap Overlay (NDVI default)
            ndvi = si.compute_ndvi(bands1)
            heatmap_base64 = si.generate_index_heatmap(ndvi, cmap_name='RdYlGn', vmin=-1, vmax=1)

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
    response = {
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
        "source": source_type
    }
    
    if fetched_coords:
        response["fetched_coordinates"] = fetched_coords
    if fetch_date:
        response["fetch_date"] = fetch_date
    if heatmap_base64:
        response["heatmap_overlay_base64"] = heatmap_base64
    if veg_breakdown:
        response["vegetation_breakdown"] = veg_breakdown
    if forest_trend:
        response["forest_cover_trend"] = forest_trend
    if forest_mask:
        response["forest_highlight_overlay_base64"] = forest_mask
    if flood_pct is not None:
        response["flooded_area_pct"] = flood_pct
    if flood_geojson:
        response["flood_geojson"] = flood_geojson
        
    # Inject query for the report
    response["query"] = query

    # Save session
    session_id = str(uuid.uuid4())
    response["session_id"] = session_id
    
    try:
        # Save JSON
        json_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        with open(json_path, 'w') as f:
            json.dump(response, f)
            
        # Save image 1
        if img1:
            img_path = os.path.join(SESSIONS_DIR, f"{session_id}.jpg")
            img1.convert("RGB").save(img_path, format="JPEG")
    except Exception as e:
        print("Failed to save session:", e)
        
    cleanup_sessions(max_sessions=100, max_age_hours=2)
        
    return response

@app.get('/generate_report/{session_id}')
async def get_report(session_id: str):
    json_path = os.path.join(SESSIONS_DIR, f'{session_id}.json')
    img_path = os.path.join(SESSIONS_DIR, f'{session_id}.jpg')
    if not os.path.exists(json_path) or not os.path.exists(img_path):
        return {'error': 'Session not found or expired'}

    try:
        with open(json_path, 'r') as f:
            result_json = json.load(f)
        from report_generator import generate_report
        pdf_path = os.path.join(SESSIONS_DIR, f'{session_id}.pdf')
        generate_report(result_json, img_path, pdf_path)
        return FileResponse(pdf_path, media_type='application/pdf', filename='SatQuery_Report.pdf')
    except Exception as e:
        print('Report generation error:', e)
        return {'error': 'Failed to generate report'}

