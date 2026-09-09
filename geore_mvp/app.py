"""
app.py — GEORE MVP Streamlit Application

Agentic vision-language assistant for remote-sensing image analysis.
Demonstrates: VQA, Grounding, Change Detection, Optical–SAR Fusion.
"""

import json
import time
import numpy as np
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from router import classify_query
from rs_toolkit import compute_change_mask, compute_fusion_stats
from prompts import build_prompt
from vlm_client import call_vlm


# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GEORE — Remote Sensing AI",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Global font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Header styling */
    .geore-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 2rem 2rem 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .geore-header h1 {
        color: #ffffff;
        font-size: 2.4rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
        letter-spacing: 2px;
    }
    .geore-header .subtitle {
        color: rgba(255, 255, 255, 0.7);
        font-size: 1rem;
        font-weight: 300;
        margin: 0;
    }
    .geore-header .accent {
        color: #7c83ff;
        font-weight: 500;
    }

    /* Task badge */
    .task-badge {
        display: inline-block;
        padding: 0.3rem 0.9rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .badge-vqa { background: rgba(99, 102, 241, 0.2); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }
    .badge-grounding { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-change { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-fusion { background: rgba(236, 72, 153, 0.2); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }

    /* Confidence badge */
    .confidence-high {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .confidence-moderate {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Provider badge */
    .provider-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 500;
        background: rgba(124, 131, 255, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(124, 131, 255, 0.25);
    }

    /* Result card */
    .result-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }

    /* Reduce default padding */
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="geore-header">
    <h1>🛰️ GEORE</h1>
    <p class="subtitle">
        <span class="accent">Agentic Vision-Language Assistant</span> for Remote Sensing Image Analysis
    </p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar: Inputs ──────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📤 Upload Images")
    st.caption("Upload 1 image for VQA/Grounding, or 2 images for Change Detection / Fusion.")

    uploaded_file_1 = st.file_uploader(
        "Image 1",
        type=["png", "jpg", "jpeg", "tif", "tiff"],
        key="img1",
        help="Primary satellite/aerial image",
    )

    uploaded_file_2 = st.file_uploader(
        "Image 2 (optional)",
        type=["png", "jpg", "jpeg", "tif", "tiff"],
        key="img2",
        help="Second image for change detection or fusion",
    )

    has_sar = False
    if uploaded_file_2:
        has_sar = st.checkbox(
            "🔘 Image 2 is SAR data",
            help="Check this if the second image is Synthetic Aperture Radar (SAR) data, for optical–SAR fusion analysis.",
        )

    st.markdown("---")
    st.markdown("### 💬 Your Query")

    query = st.text_area(
        "Ask about the image(s)",
        placeholder="e.g., What type of land use is shown?\n"
                    "e.g., Highlight the water body\n"
                    "e.g., What changed between these images?",
        height=120,
        key="query_input",
    )

    analyze_btn = st.button(
        "🔍 Analyze",
        type="primary",
        use_container_width=True,
        disabled=not (uploaded_file_1 and query),
    )

    st.markdown("---")
    st.markdown("### 📖 Supported Tasks")
    st.markdown("""
    | Task | Input |
    |------|-------|
    | **VQA** | 1 image + question |
    | **Grounding** | 1 image + "highlight/locate" query |
    | **Change Detection** | 2 images + temporal query |
    | **Optical–SAR Fusion** | 2 images (SAR checked) |
    """)


# ── Helper functions ─────────────────────────────────────────────────────────

def draw_bbox_overlay(image: Image.Image, bbox: list) -> Image.Image:
    """Draw a bounding box on the image from normalized [x_min, y_min, x_max, y_max]."""
    overlay = image.copy().convert("RGBA")
    w, h = overlay.size
    draw = ImageDraw.Draw(overlay)

    x_min = int(bbox[0] * w)
    y_min = int(bbox[1] * h)
    x_max = int(bbox[2] * w)
    y_max = int(bbox[3] * h)

    # Semi-transparent fill
    fill_layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    fill_draw = ImageDraw.Draw(fill_layer)
    fill_draw.rectangle([x_min, y_min, x_max, y_max], fill=(255, 100, 100, 50))
    overlay = Image.alpha_composite(overlay, fill_layer)

    # Bright border
    draw = ImageDraw.Draw(overlay)
    for i in range(3):
        draw.rectangle(
            [x_min - i, y_min - i, x_max + i, y_max + i],
            outline=(255, 80, 80, 255),
        )

    return overlay.convert("RGB")


def parse_grounding_json(text: str) -> dict:
    """Extract JSON bbox from grounding model response."""
    try:
        # Try to find JSON block in the response
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
        # High change in toolkit + LLM describes significant change → agree
        if pct > 5 and any(w in answer_lower for w in ["significant", "substantial", "major", "large", "considerable", "extensive"]):
            return "high"
        elif pct <= 5 and any(w in answer_lower for w in ["minor", "minimal", "slight", "little", "no significant", "negligible"]):
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
        # VQA: "high" if the response is substantive
        if len(answer) > 100:
            return "high"
        return "moderate"


def render_task_badge(task_type: str):
    """Render a styled task badge."""
    labels = {
        "vqa": ("Visual Q&A", "vqa"),
        "grounding": ("Grounding", "grounding"),
        "change": ("Change Detection", "change"),
        "fusion": ("Optical–SAR Fusion", "fusion"),
    }
    label, css_class = labels.get(task_type, ("Unknown", "vqa"))
    return f'<span class="task-badge badge-{css_class}">{label}</span>'


def render_confidence_badge(level: str):
    """Render a styled confidence badge."""
    return f'<span class="confidence-{level}">Confidence: {level.upper()}</span>'


def render_provider_badge(provider: str):
    """Render a styled provider badge."""
    return f'<span class="provider-badge">🤖 {provider}</span>'


# ── Main analysis pipeline ───────────────────────────────────────────────────

if analyze_btn and uploaded_file_1 and query:
    # Load images
    img1 = Image.open(uploaded_file_1).convert("RGB")
    images = [img1]
    img2 = None

    if uploaded_file_2:
        img2 = Image.open(uploaded_file_2).convert("RGB")
        images.append(img2)

    num_images = len(images)

    # ── Step 1: Route the query ──────────────────────────────────────────
    with st.spinner("🧭 Routing query..."):
        task_type = classify_query(query, num_images, has_sar)

    # ── Display images ───────────────────────────────────────────────────
    if num_images == 1:
        col_img, col_result = st.columns([1, 1])
        with col_img:
            st.markdown("#### 📷 Uploaded Image")
            st.image(img1, use_container_width=True)
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 📷 Image 1 (Before / Optical)")
            st.image(img1, use_container_width=True)
        with col_b:
            label = "Image 2 (SAR)" if has_sar else "Image 2 (After)"
            st.markdown(f"#### 📷 {label}")
            st.image(img2, use_container_width=True)

    # ── Step 2: Run toolkit (if needed) ──────────────────────────────────
    toolkit_output = None
    tool_called = "none"

    if task_type == "change" and num_images == 2:
        with st.spinner("⚙️ Computing change mask..."):
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            toolkit_output = compute_change_mask(arr1, arr2)
            # Remove numpy array from output for JSON serialization
            change_mask = toolkit_output.pop("change_mask", None)
            tool_called = "compute_change_mask"

    elif task_type == "fusion" and num_images == 2:
        with st.spinner("⚙️ Computing fusion statistics..."):
            arr_opt = np.array(img1)
            arr_sar = np.array(img2)
            toolkit_output = compute_fusion_stats(arr_opt, arr_sar)
            tool_called = "compute_fusion_stats"

    # ── Step 3: Build prompt and call VLM ────────────────────────────────
    with st.spinner("🧠 Analyzing with AI model..."):
        prompt = build_prompt(task_type, query, toolkit_output)
        start_time = time.time()
        answer, provider = call_vlm(prompt, images)
        elapsed = round(time.time() - start_time, 2)

    # ── Step 4: Compute confidence ───────────────────────────────────────
    confidence = compute_confidence(task_type, toolkit_output, answer)

    # ── Step 5: Display results ──────────────────────────────────────────
    st.markdown("---")

    # Header with badges
    badge_html = (
        f"{render_task_badge(task_type)} &nbsp; "
        f"{render_confidence_badge(confidence)} &nbsp; "
        f"{render_provider_badge(provider)} &nbsp; "
        f'<span style="color: rgba(255,255,255,0.4); font-size: 0.75rem;">⏱ {elapsed}s</span>'
    )
    st.markdown(badge_html, unsafe_allow_html=True)

    # ── Grounding overlay ────────────────────────────────────────────────
    if task_type == "grounding":
        parsed = parse_grounding_json(answer)
        if parsed and parsed.get("bbox"):
            bbox = parsed["bbox"]
            if bbox != [0, 0, 0, 0]:
                overlay_img = draw_bbox_overlay(img1, bbox)
                if num_images == 1:
                    with col_img:
                        st.markdown("#### 🎯 Detected Region")
                        st.image(overlay_img, use_container_width=True)
                else:
                    st.markdown("#### 🎯 Detected Region")
                    st.image(overlay_img, use_container_width=True)

                if parsed.get("description"):
                    st.info(f"📍 **Location:** {parsed['description']}")

    # ── Answer ───────────────────────────────────────────────────────────
    st.markdown("#### 📝 Analysis Result")
    st.markdown(f'<div class="result-card">', unsafe_allow_html=True)

    if task_type == "grounding":
        parsed = parse_grounding_json(answer)
        if parsed:
            st.markdown(f"**Bounding Box (normalized):** `{parsed.get('bbox', 'N/A')}`")
            st.markdown(f"**Description:** {parsed.get('description', 'N/A')}")
        else:
            st.markdown(answer)
    else:
        st.markdown(answer)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Toolkit stats (for change/fusion) ────────────────────────────────
    if toolkit_output:
        st.markdown("#### 📊 Toolkit Computed Statistics")
        stat_cols = st.columns(len(toolkit_output))
        for i, (key, val) in enumerate(toolkit_output.items()):
            with stat_cols[i]:
                if isinstance(val, float):
                    st.metric(key.replace("_", " ").title(), f"{val}%")
                elif isinstance(val, list):
                    st.metric(key.replace("_", " ").title(), f"{len(val)} regions")
                else:
                    st.metric(key.replace("_", " ").title(), str(val))

    # ── Execution trace ──────────────────────────────────────────────────
    with st.expander("🔧 Execution Trace (Agentic Pipeline)", expanded=False):
        trace = {
            "task": task_type,
            "router": "classify_query() → rule-based",
            "tool_called": tool_called,
            "tool_output": toolkit_output if toolkit_output else "N/A (direct VLM query)",
            "model_used": provider,
            "model_id": (
                "gemini-3.6-flash" if "Gemini" in provider
                else "nvidia/nemotron-nano-12b-v2-vl" if "NVIDIA" in provider
                else "none"
            ),
            "response_time_seconds": elapsed,
            "confidence": confidence,
            "num_images": num_images,
            "has_sar": has_sar,
            "prompt_length_chars": len(prompt),
        }
        st.json(trace)

        st.caption(
            "This trace shows the agentic routing pipeline: the query was classified by a "
            "deterministic router, dispatched to the appropriate toolkit function (if applicable), "
            "and narrated by the vision-language model. The provider field shows which model "
            "actually answered — demonstrating dual-provider resilience."
        )

# ── Empty state ───────────────────────────────────────────────────────────────

elif not uploaded_file_1:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; color: rgba(255,255,255,0.4);">
        <p style="font-size: 3rem; margin-bottom: 0.5rem;">🛰️</p>
        <p style="font-size: 1.2rem; font-weight: 300;">Upload a satellite image to get started</p>
        <p style="font-size: 0.85rem;">Supports PNG, JPEG, and GeoTIFF formats</p>
    </div>
    """, unsafe_allow_html=True)

    # Demo capabilities
    st.markdown("---")
    demo_cols = st.columns(4)

    capabilities = [
        ("🔍", "Visual Q&A", "Ask any question about a satellite image"),
        ("🎯", "Grounding", "Locate and highlight specific features"),
        ("🔄", "Change Detection", "Compare two temporal images"),
        ("🔗", "Fusion Analysis", "Combine optical and SAR data"),
    ]

    for col, (icon, title, desc) in zip(demo_cols, capabilities):
        with col:
            st.markdown(f"""
            <div style="text-align: center; padding: 1.5rem 1rem;
                        background: rgba(255,255,255,0.03);
                        border: 1px solid rgba(255,255,255,0.08);
                        border-radius: 12px;">
                <p style="font-size: 2rem; margin: 0;">{icon}</p>
                <p style="font-weight: 600; margin: 0.5rem 0 0.3rem 0;">{title}</p>
                <p style="font-size: 0.8rem; color: rgba(255,255,255,0.5); margin: 0;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)
