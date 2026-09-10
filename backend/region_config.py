"""
region_config.py — Region definitions and spatial geometries for GEORE.

Maps regional identifiers to geographical coordinates, spatial buffer sizes,
and baseline environmental risk parameters.
"""

from typing import Dict, Any, Optional

# Vulnerable regions configured for monitoring
REGIONS: Dict[str, Dict[str, Any]] = {
    "NP-KTM-01": {
        "name": "Kathmandu Valley, Nepal",
        "lat": 27.7172,
        "lon": 85.3240,
        "buffer_meters": 2500,        # ~2.5 km buffer radius
        "avg_slope_degrees": 35.0,     # Steep mountainous valley terrain
        "historical_susceptibility": 0.8  # High baseline risk for landslides/flooding
    },
    "NP-POK-02": {
        "name": "Pokhara Valley, Nepal",
        "lat": 28.2096,
        "lon": 83.9856,
        "buffer_meters": 3000,
        "avg_slope_degrees": 28.0,
        "historical_susceptibility": 0.65
    }
}


def get_region_config(region_id: str) -> Dict[str, Any]:
    """
    Retrieve region configuration by region_id.
    Falls back to default Kathmandu configuration if region_id is unrecognized.
    """
    if region_id in REGIONS:
        return REGIONS[region_id]
    
    # Fallback to default
    default_config = REGIONS["NP-KTM-01"].copy()
    default_config["name"] = f"Unknown Region ({region_id})"
    return default_config


def get_region_geometry(region_id: str, ee_module=None):
    """
    Generate an Earth Engine geometry object (buffered point) for a region.
    
    Args:
        region_id: Identifier of the region (e.g. 'NP-KTM-01')
        ee_module: The initialized `ee` module. If None, attempts to import ee.
        
    Returns:
        ee.Geometry representing the region of interest.
    """
    if ee_module is None:
        import ee
        ee_module = ee

    cfg = get_region_config(region_id)
    lon, lat = cfg["lon"], cfg["lat"]
    buffer_meters = cfg.get("buffer_meters", 2500)
    
    point = ee_module.Geometry.Point([lon, lat])
    return point.buffer(buffer_meters)
