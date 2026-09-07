# GEORE MVP — Build Prompt

Paste this whole document into your AI coding assistant (Claude Code, Cursor, etc.) as the task brief. It's scoped for a 2-day solo build using Google Gemini's hosted vision-language model — no local training, no GPU dependency.

---

## Context

Build **GEORE**, an agentic vision-language assistant for remote-sensing image analysis, for a Smart India Hackathon pre-selection demo. The judges need to see a **working, end-to-end system** that proves the architecture is real — not a polished but fake mockup, and not a research-grade accurate system. Scope ruthlessly for a 2-day solo build. Zero-shot correctness on any single query matters far less than the pipeline actually running and the routing logic being visibly real.

## Non-negotiable constraints

- No model training or fine-tuning. All "intelligence" comes from calling Gemini's hosted vision model via API.
- No local GPU dependency — must run on a laptop with just a Python environment and internet access.
- No freeform LLM code-generation/execution sandbox. Use a **fixed toolkit of deterministic Python functions** the router calls directly — this is a hackathon MVP, not a research agent; runtime code-gen is too fragile to debug live.
- Everything must be demoable in under 2 minutes per query for a recorded demo video.
- Note: a Google AI Pro subscription does NOT give elevated free API quota for external apps — the subscription only boosts usage inside the AI Studio web UI. Your app runs on the standard Gemini API free tier (Flash models), separate from the subscription.

## Google Gemini API details

- SDK: `pip install google-genai`
- Auth: API key from Google AI Studio (aistudio.google.com), stored as `GEMINI_API_KEY` env var
- Primary model: `gemini-2.5-flash` — free tier, vision-capable, supports multiple images in a single call (needed for change-detection and fusion queries — pass both images in one request)
- Check the model picker in AI Studio right before building — Google ships new Flash versions frequently and names shift; use whatever the current free-tier Flash alias is if `gemini-2.5-flash` has been superseded
- Fallback provider if Gemini rate-limits or errors during a live demo: NVIDIA's `nvidia/nemotron-nano-12b-v2-vl` via `https://integrate.api.nvidia.com/v1` (OpenAI-compatible), documented in the earlier version of this prompt — keep both wired with automatic failover

```python
from google import genai
from google.genai import types
import PIL.Image

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        "<prompt here>",
        PIL.Image.open("image1.png"),
        PIL.Image.open("image2.png"),  # only include for multi-image tasks
    ]
)
print(response.text)
```

## Architecture

```
Frontend (Streamlit)
    -> Backend router (plain Python function, rule-based)
        -> Deterministic RS toolkit (numpy/rasterio, no LLM)
        -> Gemini vision call (narration/VQA/grounding), falls back to NVIDIA on error
    -> Response object: {answer, overlay_data, confidence, execution_trace}
```

Use **Streamlit**, not a separate frontend+backend split — a single Python file with Streamlit's upload widget, image display, and text input covers the whole UI in far less code than a React+FastAPI split, and is fully sufficient for a hackathon demo.

## File structure to generate

```
geore_mvp/
├── app.py                 # Streamlit UI, wires everything together
├── router.py               # classify_query() -> task type
├── rs_toolkit.py            # deterministic functions, no LLM calls
├── vlm_client.py             # wrapper around Gemini API calls, with NVIDIA fallback
├── prompts.py               # prompt templates for each task type
├── .env.example              # GEMINI_API_KEY=  / NVIDIA_API_KEY=
└── requirements.txt
```

## Component specs

### `router.py` — `classify_query(query: str, num_images: int, has_sar: bool) -> str`
Rule-based, not LLM-based (deterministic, zero latency, zero failure risk):
- If `num_images == 2` and query contains temporal words ("changed", "between", "before/after", "compare dates") → `"change"`
- If `num_images == 2` and `has_sar` is True → `"fusion"`
- If query contains grounding phrases ("highlight", "locate", "where is", "show me the") → `"grounding"`
- Else → `"vqa"`

### `rs_toolkit.py` — pure functions, no API calls
- `compute_ndvi(optical_array) -> np.ndarray` — standard NDVI band math
- `compute_ndwi(optical_array) -> np.ndarray` — standard NDWI band math
- `compute_change_mask(img1_array, img2_array) -> dict` — pixel-diff + threshold; return `{"pct_changed": float, "change_regions": [(x,y,w,h), ...]}` (rough bounding regions from connected components on the diff mask, using `scipy.ndimage.label` or `cv2.connectedComponents`)
- `compute_fusion_stats(optical_array, sar_array) -> dict` — simple rule: threshold SAR backscatter for "high return" pixels, threshold NDVI/NDWI for optical; return `{"built_up_pct": float, "water_pct": float, "agreement_pct": float}` (where both modalities agree)

These must be independently testable with two sample images before anything else is wired up.

### `prompts.py` — templates
- `VQA_PROMPT` — direct query passthrough with a system framing ("You are a remote-sensing analyst. Answer based only on the image.")
- `GROUNDING_PROMPT` — asks the model to return `{"bbox": [x_min, y_min, x_max, y_max]}` as normalized 0-1 JSON for the referenced object, plus a one-sentence description
- `CHANGE_NARRATION_PROMPT` — takes `{pct_changed, change_regions}` from the toolkit and both images, asks the model to describe what likely changed and where, grounded in the numbers provided
- `FUSION_NARRATION_PROMPT` — takes `{built_up_pct, water_pct, agreement_pct}` and both images, asks the model to jointly interpret optical+SAR evidence

### `vlm_client.py`
- `call_vlm(prompt: str, images: list[PIL.Image]) -> str`:
  1. Try Gemini (`gemini-2.5-flash`) first via `google-genai` SDK
  2. On any exception (rate limit, timeout, error) — catch it, log it, and retry the same request against NVIDIA (`nvidia/nemotron-nano-12b-v2-vl`) as fallback
  3. If both fail, return a clear "analysis temporarily unavailable" message rather than crashing the app
- This dual-provider failover is your single biggest protection against a dead demo during live judging

### `app.py` — Streamlit UI
- File uploader (accepts 1 or 2 images; checkbox for "second image is SAR")
- Text input for the query
- On submit: call `router.classify_query()` → dispatch to the right toolkit function (if needed) → build the right prompt → call `vlm_client.call_vlm()` → display result
- Result display: answer text, image(s) with overlay box drawn (for grounding — use `PIL.ImageDraw` on the returned bbox), a confidence badge, and an expandable JSON panel showing `{task, tool_called, tool_output, model_used}` as the "execution trace" (note which provider actually answered — Gemini or the NVIDIA fallback — in this panel, it's a nice demo detail showing resilience)
- Confidence heuristic: `"high"` if toolkit stats and LLM narration direction agree (e.g., both indicate significant change or no change); `"moderate"` otherwise — simple string logic, no calibration needed

## What NOT to build for this MVP
- No training/fine-tuning pipeline
- No GeoTIFF/CRS/co-registration validation (Tier 1/2 from the full design) — accept whatever images are uploaded, note in the PPT this is a scoped-out item
- No database/persistence — stateless, single-session demo is fine
- No auth/multi-user handling
- No freeform code-generation agent loop
- No reliance on Google AI Pro subscription quota for the app itself — treat the API as standard free-tier

## Definition of done
All four mandatory SIH capabilities demonstrably work end-to-end on at least one real example each:
1. Single-image VQA
2. Grounding (bounding box drawn on image)
3. Change-VQA on a bi-temporal pair (toolkit stats + LLM narration)
4. Optical–SAR fusion (toolkit stats + LLM narration)

Plus: visible routing logic (execution trace panel) satisfying the "agentic orchestration" requirement, dual-provider failover (Gemini primary, NVIDIA fallback) demonstrating engineering robustness, and a recorded demo video as the primary judging artifact (don't rely on live API calls during actual judging).
