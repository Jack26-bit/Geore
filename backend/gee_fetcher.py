import os
import ee
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim

# Initialize GEE
def init_gee():
    try:
        ee.Initialize()
    except Exception as e:
        print("GEE default initialization failed:", e)
        project_id = os.environ.get("GEE_PROJECT_ID")
        key_path = os.environ.get("GEE_SERVICE_ACCOUNT_KEY_PATH")
        if project_id and key_path:
            try:
                credentials = ee.ServiceAccountCredentials('', key_path)
                ee.Initialize(credentials, project=project_id)
            except Exception as e2:
                print("Fallback GEE initialization failed:", e2)

init_gee()

def get_coordinates(location_str):
    """Geocodes a location string using Nominatim."""
    geolocator = Nominatim(user_agent="SatQuery_AI_Agent")
    location = geolocator.geocode(location_str)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_default_date_range(days=60):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def create_buffer_region(lat, lon, buffer_meters=2000):
    point = ee.Geometry.Point([lon, lat])
    return point.buffer(buffer_meters).bounds()

def _download_image(ee_image, region, dimensions=512):
    try:
        url = ee_image.getThumbURL({
            'region': region,
            'dimensions': dimensions,
            'format': 'png'
        })
        response = requests.get(url)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        print("Error downloading GEE image:", e)
    return None

def fetch_optical_image(lat, lon, buffer_meters=2000, date_range=None):
    if not date_range:
        date_range = get_default_date_range()
    
    region = create_buffer_region(lat, lon, buffer_meters)
    
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(region)
                  .filterDate(date_range[0], date_range[1])
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                  .sort('CLOUDY_PIXEL_PERCENTAGE'))
    
    if collection.size().getInfo() == 0:
        return None, None

    image = collection.first()
    
    vis_image = image.select(['B4', 'B3', 'B2']).visualize(min=0, max=3000)
    
    pil_image = _download_image(vis_image, region)
    bounds = region.getInfo()['coordinates'][0]
    return pil_image, bounds

def fetch_sar_image(lat, lon, buffer_meters=2000, date_range=None):
    if not date_range:
        date_range = get_default_date_range()
        
    region = create_buffer_region(lat, lon, buffer_meters)
    
    collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                  .filterBounds(region)
                  .filterDate(date_range[0], date_range[1])
                  .filter(ee.Filter.eq('instrumentMode', 'IW'))
                  .sort('system:time_start', False))
                  
    if collection.size().getInfo() == 0:
        return None, None
        
    image = collection.first()
    vis_image = image.select(['VV', 'VH', 'VV']).visualize(min=-25, max=5)
    
    pil_image = _download_image(vis_image, region)
    bounds = region.getInfo()['coordinates'][0]
    return pil_image, bounds

def fetch_bitemporal_pair(lat, lon, date_range_1=None, date_range_2=None, buffer_meters=2000):
    if not date_range_2:
        date_range_2 = get_default_date_range(30)
    if not date_range_1:
        end_date = datetime.strptime(date_range_2[1], '%Y-%m-%d') - timedelta(days=365)
        start_date = end_date - timedelta(days=30)
        date_range_1 = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
    img1, bounds1 = fetch_optical_image(lat, lon, buffer_meters, date_range_1)
    img2, bounds2 = fetch_optical_image(lat, lon, buffer_meters, date_range_2)
    
    return img1, img2, bounds2
def fetch_optical_multiband(lat, lon, buffer_meters=2000, date_range=None):
    if not date_range:
        date_range = get_default_date_range()
    
    region = create_buffer_region(lat, lon, buffer_meters)
    
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(region)
                  .filterDate(date_range[0], date_range[1])
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                  .sort('CLOUDY_PIXEL_PERCENTAGE'))
    
    if collection.size().getInfo() == 0:
        return None, None, None

    image = collection.first()
    bounds = region.getInfo()['coordinates'][0]

    # RGB for visual display
    vis_image = image.select(['B4', 'B3', 'B2']).visualize(min=0, max=3000)
    pil_image = _download_image(vis_image, region)

    # Fetch raw bands B3 (Green), B4 (Red), B8 (NIR)
    try:
        url = image.select(['B3', 'B4', 'B8']).getDownloadURL({
            'region': region,
            'scale': 10,
            'format': 'GEO_TIFF'
        })
        response = requests.get(url)
        if response.status_code == 200:
            import tempfile
            import rasterio
            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                tmp.write(response.content)
                tmp_name = tmp.name
            
            with rasterio.open(tmp_name) as src:
                b3 = src.read(1) # Green
                b4 = src.read(2) # Red
                b8 = src.read(3) # NIR
                
            os.remove(tmp_name)
            
            return pil_image, bounds, {'B3': b3, 'B4': b4, 'B8': b8}
    except Exception as e:
        print("Error downloading multi-band TIFF:", e)
        
    return pil_image, bounds, None

def fetch_bitemporal_multiband(lat, lon, date_range_1=None, date_range_2=None, buffer_meters=2000):
    if not date_range_2:
        date_range_2 = get_default_date_range(30)
    if not date_range_1:
        end_date = datetime.strptime(date_range_2[1], '%Y-%m-%d') - timedelta(days=365)
        start_date = end_date - timedelta(days=30)
        date_range_1 = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
    img1, bounds1, bands1 = fetch_optical_multiband(lat, lon, buffer_meters, date_range_1)
    img2, bounds2, bands2 = fetch_optical_multiband(lat, lon, buffer_meters, date_range_2)
    
    return img1, img2, bounds2, bands1, bands2
