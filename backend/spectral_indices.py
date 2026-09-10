import numpy as np
import base64
from io import BytesIO
import matplotlib.pyplot as plt
from PIL import Image

def compute_ndvi(bands):
    """NDVI = (NIR - Red) / (NIR + Red)"""
    red = bands['B4'].astype(float)
    nir = bands['B8'].astype(float)
    # Ignore division by zero
    np.seterr(divide='ignore', invalid='ignore')
    ndvi = (nir - red) / (nir + red)
    ndvi = np.nan_to_num(ndvi, nan=-1.0)
    return ndvi

def compute_ndwi(bands):
    """NDWI = (Green - NIR) / (Green + NIR)"""
    green = bands['B3'].astype(float)
    nir = bands['B8'].astype(float)
    np.seterr(divide='ignore', invalid='ignore')
    ndwi = (green - nir) / (green + nir)
    ndwi = np.nan_to_num(ndwi, nan=-1.0)
    return ndwi

def generate_index_heatmap(index_array, cmap_name='RdYlGn', vmin=-1, vmax=1):
    plt.figure(figsize=(6, 6))
    plt.imshow(index_array, cmap=cmap_name, vmin=vmin, vmax=vmax)
    plt.axis('off')
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
    buf.seek(0)
    plt.close()
    
    return base64.b64encode(buf.read()).decode('utf-8')

def classify_vegetation_proportions(ndvi_array):
    total_pixels = ndvi_array.size
    bare = np.sum(ndvi_array < 0.1)
    sparse = np.sum((ndvi_array >= 0.1) & (ndvi_array < 0.3))
    moderate = np.sum((ndvi_array >= 0.3) & (ndvi_array < 0.6))
    dense = np.sum(ndvi_array >= 0.6)
    
    return [
        {"name": "Bare soil", "value": float(bare / total_pixels * 100)},
        {"name": "Sparse vegetation", "value": float(sparse / total_pixels * 100)},
        {"name": "Moderate vegetation", "value": float(moderate / total_pixels * 100)},
        {"name": "Dense vegetation", "value": float(dense / total_pixels * 100)}
    ]

def compute_forest_cover_trend(ndvi_t1, ndvi_t2, threshold=0.5):
    total = ndvi_t1.size
    forest_t1 = float(np.sum(ndvi_t1 >= threshold) / total * 100)
    forest_t2 = float(np.sum(ndvi_t2 >= threshold) / total * 100)
    
    return [
        {"name": "Previous", "value": forest_t1},
        {"name": "Current", "value": forest_t2}
    ]

def generate_forest_mask_overlay(ndvi_array, threshold=0.5):
    mask = ndvi_array >= threshold
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[mask] = [0, 255, 0, 128]  # Semi-transparent green
    
    img = Image.fromarray(rgba)
    buf = BytesIO()
    img.save(buf, format='png')
    buf.seek(0)
    
    return base64.b64encode(buf.read()).decode('utf-8')

def detect_flood_regions(ndwi_array, threshold=0.3):
    total = ndwi_array.size
    flood_mask = ndwi_array >= threshold
    pct = float(np.sum(flood_mask) / total * 100)
    return pct, flood_mask

def flood_region_to_geojson(flood_mask, bounds):
    from shapely.geometry import shape, mapping
    import rasterio.features
    from rasterio.transform import from_bounds

    if not bounds:
        return None
        
    try:
        lons = [p[0] for p in bounds]
        lats = [p[1] for p in bounds]
        lon_min, lon_max = min(lons), max(lons)
        lat_min, lat_max = min(lats), max(lats)
        
        height, width = flood_mask.shape
        transform = from_bounds(lon_min, lat_min, lon_max, lat_max, width, height)
        
        shapes = rasterio.features.shapes(flood_mask.astype(np.uint8), mask=flood_mask, transform=transform)
        
        polygons = []
        for geom, val in shapes:
            polygons.append({
                "type": "Feature",
                "properties": {},
                "geometry": geom
            })
            
        if not polygons:
            return None
            
        return {
            "type": "FeatureCollection",
            "features": polygons
        }
    except Exception as e:
        print("GeoJSON generation error:", e)
        return None
