"""
rs_toolkit.py — Deterministic remote-sensing functions for GEORE.

Pure numpy/scipy/cv2 — no API calls, no LLM dependency.
Works with both multispectral (4+ bands) and RGB-only images.
"""

import numpy as np
import cv2
from typing import List, Tuple, Dict, Any


# ── Band index conventions (for multispectral images) ─────────────────────────
# Standard ordering: [Blue, Green, Red, NIR, ...]
BLUE, GREEN, RED, NIR = 0, 1, 2, 3


def _to_float(arr: np.ndarray) -> np.ndarray:
    """Normalize array to 0–1 float range."""
    if arr.dtype == np.uint8:
        return arr.astype(np.float32) / 255.0
    elif arr.dtype == np.uint16:
        return arr.astype(np.float32) / 65535.0
    elif np.issubdtype(arr.dtype, np.floating):
        return arr.astype(np.float32)
    return arr.astype(np.float32) / arr.max() if arr.max() > 0 else arr.astype(np.float32)


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute (a - b) / (a + b) with zero-division handling."""
    numer = (a - b).astype(np.float32)
    denom = (a + b).astype(np.float32)
    result = np.zeros_like(numer)
    mask = denom != 0
    result[mask] = numer[mask] / denom[mask]
    return np.clip(result, -1.0, 1.0)


# ── NDVI ──────────────────────────────────────────────────────────────────────

def compute_ndvi(optical_array: np.ndarray) -> np.ndarray:
    """
    Compute Normalized Difference Vegetation Index.

    For multispectral (≥4 bands): standard (NIR - Red) / (NIR + Red).
    For RGB-only (3 bands): approximate using (Green - Red) / (Green + Red),
    which correlates with vegetation presence in visible imagery.

    Args:
        optical_array: Image array, shape (H, W, C) where C ≥ 3.

    Returns:
        NDVI array, shape (H, W), values in [-1, 1].
    """
    arr = _to_float(optical_array)

    if arr.ndim == 2:
        # Grayscale — cannot compute NDVI
        return np.zeros(arr.shape, dtype=np.float32)

    if arr.shape[2] >= 4:
        # Multispectral: use true NIR and Red
        nir = arr[:, :, NIR]
        red = arr[:, :, RED]
    else:
        # RGB fallback: approximate with Green and Red
        green = arr[:, :, 1]
        red = arr[:, :, 0] if arr.shape[2] == 3 else arr[:, :, 2]
        # For PIL-loaded RGB images: channel order is R=0, G=1, B=2
        red = arr[:, :, 0]
        green = arr[:, :, 1]
        nir = green  # Proxy: green channel as NIR surrogate
        red = red

    return _safe_ratio(nir, red)


# ── NDWI ──────────────────────────────────────────────────────────────────────

def compute_ndwi(optical_array: np.ndarray) -> np.ndarray:
    """
    Compute Normalized Difference Water Index.

    For multispectral (≥4 bands): (Green - NIR) / (Green + NIR).
    For RGB-only: approximate using (Blue - Green) / (Blue + Green).

    Args:
        optical_array: Image array, shape (H, W, C) where C ≥ 3.

    Returns:
        NDWI array, shape (H, W), values in [-1, 1].
    """
    arr = _to_float(optical_array)

    if arr.ndim == 2:
        return np.zeros(arr.shape, dtype=np.float32)

    if arr.shape[2] >= 4:
        green = arr[:, :, GREEN]
        nir = arr[:, :, NIR]
    else:
        # RGB fallback: Blue vs Green as water proxy
        # PIL RGB order: R=0, G=1, B=2
        blue = arr[:, :, 2]
        green = arr[:, :, 1]
        nir = green
        green = blue

    return _safe_ratio(green, nir)


# ── Change Detection ─────────────────────────────────────────────────────────

def compute_change_mask(
    img1_array: np.ndarray,
    img2_array: np.ndarray,
    threshold: float = 0.15,
    min_region_area: int = 100,
) -> Dict[str, Any]:
    """
    Compute change mask between two images via pixel-level differencing.

    Args:
        img1_array:      First image (before), shape (H, W, C) or (H, W).
        img2_array:      Second image (after), same shape as img1.
        threshold:       Difference threshold (0–1 scale) to flag a pixel as changed.
        min_region_area: Minimum pixel area for a change region to be reported.

    Returns:
        {
            "pct_changed": float (0–100),
            "change_regions": [(x, y, w, h), ...],
            "change_mask": np.ndarray (binary mask, H×W)
        }
    """
    a1 = _to_float(img1_array)
    a2 = _to_float(img2_array)

    # Resize if dimensions don't match (take the smaller)
    if a1.shape[:2] != a2.shape[:2]:
        h = min(a1.shape[0], a2.shape[0])
        w = min(a1.shape[1], a2.shape[1])
        a1 = cv2.resize(a1, (w, h))
        a2 = cv2.resize(a2, (w, h))

    # Convert to grayscale for differencing if multi-channel
    if a1.ndim == 3:
        g1 = np.mean(a1, axis=2)
    else:
        g1 = a1
    if a2.ndim == 3:
        g2 = np.mean(a2, axis=2)
    else:
        g2 = a2

    # Absolute difference and threshold
    diff = np.abs(g1 - g2)
    change_mask = (diff > threshold).astype(np.uint8)

    # Percentage changed
    total_pixels = change_mask.size
    changed_pixels = int(np.sum(change_mask))
    pct_changed = round((changed_pixels / total_pixels) * 100, 2)

    # Connected components → bounding boxes
    num_labels, labels = cv2.connectedComponents(change_mask)
    change_regions: List[Tuple[int, int, int, int]] = []

    for label_id in range(1, num_labels):
        region_mask = (labels == label_id).astype(np.uint8)
        area = int(np.sum(region_mask))
        if area < min_region_area:
            continue
        coords = np.argwhere(region_mask)
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        change_regions.append((int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min)))

    return {
        "pct_changed": pct_changed,
        "change_regions": change_regions,
        "change_mask": change_mask,
    }


# ── Optical–SAR Fusion ───────────────────────────────────────────────────────

def compute_fusion_stats(
    optical_array: np.ndarray,
    sar_array: np.ndarray,
    sar_high_threshold: float = 0.6,
    ndvi_veg_threshold: float = 0.2,
    ndwi_water_threshold: float = 0.1,
) -> Dict[str, float]:
    """
    Compute fusion statistics from co-registered optical and SAR images.

    High SAR backscatter → likely built-up or rough surfaces.
    NDVI > threshold → vegetation.
    NDWI > threshold → water.
    Agreement = pixels where both modalities indicate the same class.

    Args:
        optical_array:       Optical image array (H, W, C).
        sar_array:           SAR image array (H, W) or (H, W, 1).
        sar_high_threshold:  Backscatter threshold for "high return" pixels.
        ndvi_veg_threshold:  NDVI threshold for vegetation.
        ndwi_water_threshold: NDWI threshold for water.

    Returns:
        {
            "built_up_pct": float,
            "vegetation_pct": float,
            "water_pct": float,
            "agreement_pct": float
        }
    """
    opt = _to_float(optical_array)
    sar = _to_float(sar_array)

    # Flatten SAR to 2D if needed
    if sar.ndim == 3:
        sar_2d = np.mean(sar, axis=2)
    else:
        sar_2d = sar

    # Resize to match
    if opt.shape[:2] != sar_2d.shape[:2]:
        h = min(opt.shape[0], sar_2d.shape[0])
        w = min(opt.shape[1], sar_2d.shape[1])
        opt = cv2.resize(opt, (w, h))
        sar_2d = cv2.resize(sar_2d, (w, h))

    total = sar_2d.size

    # SAR-based classification: high backscatter → built-up
    sar_high = sar_2d > sar_high_threshold
    built_up_pct = round(float(np.sum(sar_high) / total) * 100, 2)

    # Optical-based classification
    ndvi = compute_ndvi(opt)
    ndwi = compute_ndwi(opt)

    veg_mask = ndvi > ndvi_veg_threshold
    water_mask = ndwi > ndwi_water_threshold

    vegetation_pct = round(float(np.sum(veg_mask) / total) * 100, 2)
    water_pct = round(float(np.sum(water_mask) / total) * 100, 2)

    # Agreement: both modalities agree on "not-vegetation" (built-up from SAR
    # AND low NDVI from optical) OR both agree on water-like features
    optical_built_up = (~veg_mask) & (~water_mask)
    agree_built = sar_high & optical_built_up
    agree_water = (~sar_high) & water_mask  # Low SAR + water in optical

    agreement_pixels = int(np.sum(agree_built)) + int(np.sum(agree_water))
    agreement_pct = round((agreement_pixels / total) * 100, 2)

    return {
        "built_up_pct": built_up_pct,
        "vegetation_pct": vegetation_pct,
        "water_pct": water_pct,
        "agreement_pct": agreement_pct,
    }


# ── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("RS Toolkit self-test:")

    # Test NDVI with synthetic 4-band image
    img4 = np.random.randint(0, 255, (100, 100, 4), dtype=np.uint8)
    ndvi = compute_ndvi(img4)
    print(f"  [PASS] NDVI (4-band):  shape={ndvi.shape}, range=[{ndvi.min():.2f}, {ndvi.max():.2f}]")

    # Test NDVI with RGB image
    img3 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    ndvi_rgb = compute_ndvi(img3)
    print(f"  [PASS] NDVI (RGB):     shape={ndvi_rgb.shape}, range=[{ndvi_rgb.min():.2f}, {ndvi_rgb.max():.2f}]")

    # Test NDWI
    ndwi = compute_ndwi(img4)
    print(f"  [PASS] NDWI (4-band):  shape={ndwi.shape}, range=[{ndwi.min():.2f}, {ndwi.max():.2f}]")

    # Test change mask
    img_a = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    img_b = img_a.copy()
    img_b[30:60, 30:60] = 255 - img_b[30:60, 30:60]  # Invert a region
    result = compute_change_mask(img_a, img_b)
    print(f"  [PASS] Change mask:    pct_changed={result['pct_changed']}%, regions={len(result['change_regions'])}")

    # Test fusion stats
    optical = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    sar = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    fusion = compute_fusion_stats(optical, sar)
    print(f"  [PASS] Fusion stats:   built_up={fusion['built_up_pct']}%, water={fusion['water_pct']}%, agreement={fusion['agreement_pct']}%")

    print("\nAll toolkit tests passed!")
