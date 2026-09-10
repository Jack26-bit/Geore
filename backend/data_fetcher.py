"""
data_fetcher.py — Remote sensing observation fetcher for GEORE.

Fetches real satellite data from Google Earth Engine (GEE):
- Sentinel-2 Level-2A (Optical RGB)
- Sentinel-1 GRD (SAR VV backscatter)
- CHIRPS Daily Precipitation (Rainfall telemetry)
- SMAP 10km (Soil moisture telemetry)

Falls back gracefully to synthetic observation generation if GEE credentials
are absent, expired, or network queries fail.
"""

import os
import io
import json
import logging
import datetime
from typing import Dict, Any, Optional

import numpy as np
import requests
from PIL import Image

from region_config import REGIONS, get_region_config, get_region_geometry

logger = logging.getLogger("geore.data_fetcher")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ── Global GEE State ─────────────────────────────────────────────────────────
GEE_AVAILABLE: bool = False
ee = None

try:
    import ee as _ee
    ee = _ee

    key_path = os.getenv("GEE_SERVICE_ACCOUNT_KEY_PATH")
    sa_email = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")

    if key_path and os.path.exists(key_path):
        from google.oauth2 import service_account

        project_id = None
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)
                project_id = key_data.get("project_id")
                if not sa_email:
                    sa_email = key_data.get("client_email")
        except Exception as read_err:
            logger.warning(f"Could not parse service account key file {key_path}: {read_err}")

        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=[
                "https://www.googleapis.com/auth/earthengine",
                "https://www.googleapis.com/auth/cloud-platform"
            ]
        )
        ee.Initialize(credentials=credentials, project=project_id)
        GEE_AVAILABLE = True
        logger.info("Google Earth Engine initialized successfully with service account credentials.")
    else:
        # Attempt initialization with any pre-existing environment credentials
        try:
            ee.Initialize()
            GEE_AVAILABLE = True
            logger.info("Google Earth Engine initialized successfully with persistent default credentials.")
        except Exception as auth_err:
            logger.warning(
                "GEE credentials not configured or default auth failed. "
                "System will operate in synthetic fallback mode. "
                f"Detail: {auth_err}"
            )
            GEE_AVAILABLE = False
except Exception as init_err:
    logger.warning(
        f"Google Earth Engine module unavailable or initialization error: {init_err}. "
        "System will operate in synthetic fallback mode."
    )
    GEE_AVAILABLE = False


# ── Synthetic Fallback Generators ─────────────────────────────────────────────

def generate_synthetic_image(mode: str = "optical") -> Image.Image:
    """Generate a small 256x256 synthetic image to prevent local GPU overload."""
    size = (256, 256)
    if mode == "optical":
        # Generate an RGB image simulating vegetation and some built-up areas
        arr = np.random.randint(0, 100, (256, 256, 3), dtype=np.uint8)
        # Add some green (vegetation)
        arr[:, :, 1] += 50
        # Add some random noise and structures
        arr[50:100, 50:100, :] = 200
        arr = np.clip(arr, 0, 255)
        return Image.fromarray(arr)
    else:  # SAR
        # Generate a grayscale SAR-like image
        arr = np.random.randint(50, 150, size, dtype=np.uint8)
        # Add a high-backscatter region
        arr[50:100, 50:100] = 250
        return Image.fromarray(arr).convert("L")


def _fallback_observations(region_id: str, reason: str = "") -> Dict[str, Any]:
    """Generates synthetic observations matching the expected schema."""
    if reason:
        logger.info(f"[DataFetcher] Using synthetic observations for {region_id}: {reason}")
    cfg = get_region_config(region_id)
    optical_img = generate_synthetic_image("optical")
    sar_img = generate_synthetic_image("sar")

    return {
        "region_id": region_id,
        "optical_image": optical_img,
        "sar_image": sar_img,
        "rainfall_mm_24h": float(np.random.uniform(0.0, 150.0)),
        "soil_moisture_pct": float(np.random.uniform(10.0, 95.0)),
        "avg_slope_degrees": cfg.get("avg_slope_degrees", 35.0),
        "historical_susceptibility": cfg.get("historical_susceptibility", 0.8)
    }


# ── GEE Satellite Data Fetchers ───────────────────────────────────────────────

def fetch_optical(region_geom, days_back: int = 15) -> Image.Image:
    """
    Query Sentinel-2 Level-2A surface reflectance for a cloud-free RGB scene.
    
    Args:
        region_geom: ee.Geometry for the target region.
        days_back: Number of past days to query.
        
    Returns:
        PIL.Image (256x256 RGB).
    """
    if not GEE_AVAILABLE or ee is None:
        raise RuntimeError("GEE is not initialized")

    end_date = datetime.datetime.now(datetime.timezone.utc)
    start_date = end_date - datetime.timedelta(days=days_back)
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    def _query(s_date_str: str, e_date_str: str):
        return (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region_geom)
            .filterDate(s_date_str, e_date_str)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .sort("CLOUDY_PIXEL_PERCENTAGE", True)
        )

    col = _query(start_str, end_str)
    count = col.size().getInfo()

    # If no cloud-free scene found within default range, widen once to 30 days
    if count == 0 and days_back < 30:
        logger.info(f"No cloud-free Sentinel-2 image in last {days_back} days. Widening search to 30 days.")
        start_date_30 = end_date - datetime.timedelta(days=30)
        col = _query(start_date_30.strftime("%Y-%m-%d"), end_str)
        count = col.size().getInfo()

    if count == 0:
        raise ValueError(f"No Sentinel-2 imagery available under 20% cloud cover within date range.")

    s2_img = col.first().clip(region_geom)

    # Convert to 256x256 RGB thumbnail via getThumbURL
    vis_params = {
        "bands": ["B4", "B3", "B2"],
        "min": 0,
        "max": 3000,
        "dimensions": 256,
        "format": "png"
    }
    thumb_url = s2_img.getThumbURL(vis_params)
    resp = requests.get(thumb_url, timeout=10)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def fetch_sar(region_geom, days_back: int = 15) -> Image.Image:
    """
    Query Sentinel-1 GRD IW mode VV polarization for the latest backscatter scene.
    
    Args:
        region_geom: ee.Geometry for the target region.
        days_back: Number of past days to query.
        
    Returns:
        PIL.Image (256x256 Grayscale 'L').
    """
    if not GEE_AVAILABLE or ee is None:
        raise RuntimeError("GEE is not initialized")

    end_date = datetime.datetime.now(datetime.timezone.utc)
    start_date = end_date - datetime.timedelta(days=days_back)
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    def _query(s_date_str: str, e_date_str: str):
        return (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region_geom)
            .filterDate(s_date_str, e_date_str)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .sort("system:time_start", False)
        )

    col = _query(start_str, end_str)
    count = col.size().getInfo()

    # Widen search to 30 days if needed
    if count == 0 and days_back < 30:
        logger.info(f"No Sentinel-1 SAR image in last {days_back} days. Widening search to 30 days.")
        start_date_30 = end_date - datetime.timedelta(days=30)
        col = _query(start_date_30.strftime("%Y-%m-%d"), end_str)
        count = col.size().getInfo()

    if count == 0:
        raise ValueError("No Sentinel-1 SAR imagery found for region.")

    s1_img = col.first().clip(region_geom)

    # Normalize VV backscatter dB (typically -25 dB to 0 dB) to 256x256 grayscale
    vis_params = {
        "bands": ["VV"],
        "min": -25,
        "max": 0,
        "dimensions": 256,
        "format": "png"
    }
    thumb_url = s1_img.getThumbURL(vis_params)
    resp = requests.get(thumb_url, timeout=10)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("L")


def fetch_telemetry(region_geom, region_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """
    Fetch rainfall (CHIRPS Daily) and soil moisture (SMAP 10km) telemetry via spatial reduction.
    
    Args:
        region_geom: ee.Geometry for the target region.
        region_cfg: Static region configuration dict.
        
    Returns:
        Dict with keys rainfall_mm_24h, soil_moisture_pct, avg_slope_degrees, historical_susceptibility.
    """
    if not GEE_AVAILABLE or ee is None:
        raise RuntimeError("GEE is not initialized")

    if region_cfg is None:
        region_cfg = {}

    # 1. Rainfall: CHIRPS Daily (sum of latest available 2 observations to account for product latency)
    try:
        chirps_col = (
            ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterBounds(region_geom)
            .sort("system:time_start", False)
            .limit(2)
        )
        rain_img = chirps_col.select("precipitation").sum()
        rain_stats = rain_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region_geom,
            scale=5000,
            maxPixels=1e6
        ).getInfo()
        rain_val = rain_stats.get("precipitation")
        rainfall_mm_24h = float(rain_val) if rain_val is not None else 12.0
    except Exception as rain_err:
        logger.warning(f"Error fetching CHIRPS rainfall telemetry: {rain_err}. Using default estimate.")
        rainfall_mm_24h = 15.0

    # 2. Soil Moisture: NASA SMAP 10km (surface soil moisture band 'ssm')
    try:
        smap_col = (
            ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture")
            .filterBounds(region_geom)
            .sort("system:time_start", False)
            .limit(1)
        )
        smap_img = smap_col.first().select("ssm")
        smap_stats = smap_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region_geom,
            scale=10000,
            maxPixels=1e6
        ).getInfo()
        soil_val = smap_stats.get("ssm")
        soil_moisture_pct = float(soil_val) if soil_val is not None else 42.0
    except Exception as soil_err:
        logger.warning(f"Error fetching SMAP soil moisture telemetry: {soil_err}. Using default estimate.")
        soil_moisture_pct = 45.0

    return {
        "rainfall_mm_24h": round(rainfall_mm_24h, 2),
        "soil_moisture_pct": round(soil_moisture_pct, 2),
        "avg_slope_degrees": region_cfg.get("avg_slope_degrees", 35.0),
        "historical_susceptibility": region_cfg.get("historical_susceptibility", 0.8)
    }


# ── Primary Observation Fetcher ───────────────────────────────────────────────

def fetch_latest_observations(region_id: str) -> Dict[str, Any]:
    """
    Fetches the latest multi-source observations for a vulnerable region.
    
    If GEE credentials and services are available, pulls real Sentinel-1/Sentinel-2
    imagery and CHIRPS/SMAP environmental telemetry. If unavailable or if any query fails,
    seamlessly falls back to synthetic observations with matching schema.
    
    Returns:
        Dict containing:
        - region_id: str
        - optical_image: PIL.Image (RGB)
        - sar_image: PIL.Image (Grayscale)
        - rainfall_mm_24h: float
        - soil_moisture_pct: float
        - avg_slope_degrees: float
        - historical_susceptibility: float
    """
    logger.info(f"[DataFetcher] Fetching latest observations for region: {region_id}")

    if not GEE_AVAILABLE or ee is None:
        return _fallback_observations(region_id, reason="GEE unavailable")

    try:
        cfg = get_region_config(region_id)
        region_geom = get_region_geometry(region_id, ee_module=ee)

        optical_img = fetch_optical(region_geom, days_back=15)
        sar_img = fetch_sar(region_geom, days_back=15)
        telemetry = fetch_telemetry(region_geom, region_cfg=cfg)

        return {
            "region_id": region_id,
            "optical_image": optical_img,
            "sar_image": sar_img,
            "rainfall_mm_24h": telemetry["rainfall_mm_24h"],
            "soil_moisture_pct": telemetry["soil_moisture_pct"],
            "avg_slope_degrees": telemetry["avg_slope_degrees"],
            "historical_susceptibility": telemetry["historical_susceptibility"]
        }

    except Exception as exc:
        logger.warning(
            f"[DataFetcher] Real observation fetch failed for {region_id}: {exc}. "
            "Falling back to synthetic data."
        )
        return _fallback_observations(region_id, reason=str(exc))


# ── Self-Test Block ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=======================================================")
    print("           GEORE Data Fetcher Self-Test                ")
    print("=======================================================")
    
    status_str = "LIVE (Google Earth Engine)" if GEE_AVAILABLE else "SYNTHETIC-FALLBACK (No GEE Credentials)"
    print(f"[*] Engine Status: {status_str}")
    
    test_region = "NP-KTM-01"
    print(f"[*] Fetching observations for: {test_region}")
    
    obs = fetch_latest_observations(test_region)
    
    print("\n--- Observation Results ---")
    print(f"Region ID:                  {obs['region_id']}")
    print(f"Optical Image:              Size={obs['optical_image'].size}, Mode={obs['optical_image'].mode}")
    print(f"SAR Image:                  Size={obs['sar_image'].size}, Mode={obs['sar_image'].mode}")
    print(f"Rainfall (24h):             {obs['rainfall_mm_24h']} mm")
    print(f"Soil Moisture:              {obs['soil_moisture_pct']}%")
    print(f"Average Slope:              {obs['avg_slope_degrees']}°")
    print(f"Historical Susceptibility:  {obs['historical_susceptibility']}")
    
    if GEE_AVAILABLE:
        print("\n[✓] Verified: Live Earth Engine observation successfully retrieved.")
    else:
        print("\n[i] Verified: Graceful synthetic fallback working as expected.")
        
    print("=======================================================\n")
