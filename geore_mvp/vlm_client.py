"""
vlm_client.py — Dual-provider VLM client for GEORE.

Primary:  Google Gemini (gemini-2.5-flash) via google-genai SDK
Fallback: NVIDIA (nemotron-nano-12b-v2-vl) via OpenAI-compatible API

Automatic failover: if Gemini fails (rate limit, timeout, error),
the same request is retried against NVIDIA. If both fail, returns a
graceful error message instead of crashing the app.
"""

import os
import io
import base64
import logging
import time
from typing import List, Tuple, Optional

from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-nano-12b-v2-vl")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _pil_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    """Convert PIL Image to base64 string."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Gemini provider ──────────────────────────────────────────────────────────

def _call_gemini(prompt: str, images: List[Image.Image]) -> str:
    """
    Call Google Gemini via the google-genai SDK.

    Supports multi-image input (pass all images in one request).
    """
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Build contents: prompt text + images
    contents = [prompt]
    for img in images:
        contents.append(img)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    return response.text


# ── NVIDIA provider (OpenAI-compatible) ──────────────────────────────────────

def _call_nvidia(prompt: str, images: List[Image.Image]) -> str:
    """
    Call NVIDIA's vision-language model via OpenAI-compatible API.

    Encodes images as base64 data URIs in the message content.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=NVIDIA_API_KEY,
        base_url=NVIDIA_BASE_URL,
    )

    # Build message content: text + image parts
    content_parts = []

    for img in images:
        b64 = _pil_to_base64(img, fmt="PNG")
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
            },
        })

    content_parts.append({
        "type": "text",
        "text": prompt,
    })

    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {"role": "user", "content": content_parts}
        ],
        max_tokens=1024,
        temperature=0.3,
    )

    return response.choices[0].message.content


# ── Public API ────────────────────────────────────────────────────────────────

def call_vlm(
    prompt: str,
    images: List[Image.Image],
) -> Tuple[str, str]:
    """
    Call a vision-language model with automatic failover.

    Tries Gemini first, falls back to NVIDIA on any error.

    Args:
        prompt: The formatted prompt string.
        images: List of PIL Images to analyze.

    Returns:
        Tuple of (response_text, provider_name).
        provider_name is one of: "Gemini", "NVIDIA", "none".
    """
    errors = []

    # ── Try Gemini first ─────────────────────────────────────────────────
    if GEMINI_API_KEY:
        try:
            logger.info(f"Calling Gemini ({GEMINI_MODEL})...")
            start = time.time()
            result = _call_gemini(prompt, images)
            elapsed = round(time.time() - start, 2)
            logger.info(f"Gemini responded in {elapsed}s")
            return result, "Gemini"
        except Exception as e:
            err_msg = f"Gemini error: {type(e).__name__}: {e}"
            logger.warning(err_msg)
            errors.append(err_msg)
    else:
        errors.append("Gemini: API key not configured")

    # ── Fallback to NVIDIA ───────────────────────────────────────────────
    if NVIDIA_API_KEY:
        try:
            logger.info(f"Falling back to NVIDIA ({NVIDIA_MODEL})...")
            start = time.time()
            result = _call_nvidia(prompt, images)
            elapsed = round(time.time() - start, 2)
            logger.info(f"NVIDIA responded in {elapsed}s")
            return result, "NVIDIA (fallback)"
        except Exception as e:
            err_msg = f"NVIDIA error: {type(e).__name__}: {e}"
            logger.warning(err_msg)
            errors.append(err_msg)
    else:
        errors.append("NVIDIA: API key not configured (fallback unavailable)")

    # ── Both failed ──────────────────────────────────────────────────────
    error_detail = " | ".join(errors)
    logger.error(f"All providers failed: {error_detail}")
    return (
        f"[!] Analysis temporarily unavailable. Both providers failed.\n\n"
        f"**Error details:** {error_detail}\n\n"
        f"Please check your API keys and try again.",
        "none",
    )


# ── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("VLM Client configuration check:")
    print(f"  Gemini API key: {'[OK] configured' if GEMINI_API_KEY else '[MISSING]'}")
    print(f"  Gemini model:   {GEMINI_MODEL}")
    print(f"  NVIDIA API key: {'[OK] configured' if NVIDIA_API_KEY else '[MISSING] (fallback disabled)'}")
    print(f"  NVIDIA model:   {NVIDIA_MODEL}")

    if GEMINI_API_KEY:
        print("\nTesting Gemini with a simple text-only prompt...")
        try:
            # Quick text-only test (no image)
            test_img = Image.new("RGB", (64, 64), color=(100, 150, 50))
            response, provider = call_vlm("Describe this image in one sentence.", [test_img])
            print(f"  [PASS] Provider: {provider}")
            print(f"  [PASS] Response: {response[:120]}...")
        except Exception as e:
            print(f"  [FAIL] Error: {e}")
    else:
        print("\n[WARN] Skipping live test -- no API key configured.")
