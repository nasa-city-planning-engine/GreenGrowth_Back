import matplotlib
matplotlib.use('Agg')

from flask import Blueprint, jsonify, request
import ee
import folium
from dotenv import load_dotenv
import os

load_dotenv()

try:
    ee.Initialize(project=os.getenv("GEE_PROJECT"))
except Exception as e:
    print(f"ERROR: No se pudo inicializar Earth Engine. Error: {e}")

geo_bp = Blueprint("geo", __name__, url_prefix="/geo")

# --- Funciones auxiliares ---
def apply_qa_or_passthrough(img, band_name):
    has_qa = img.bandNames().contains('qa_value')
    img_masked = ee.Image(ee.Algorithms.If(has_qa, img.updateMask(img.select('qa_value').gt(0.75)), img))
    return img_masked.select(band_name)

def collection_mean(collection_id, band_name, start_date, end_date):
    ic = (ee.ImageCollection(collection_id)
          .filterDate(start_date, end_date)
          .map(lambda im: apply_qa_or_passthrough(im, band_name)))
    return ic.mean()

def normalize(img, vmin, vmax):
    return (img.subtract(vmin)
            .divide(ee.Number(vmax).subtract(vmin))
            .multiply(100)
            .clamp(0, 100))

def add_ee_layer(folium_map, ee_image_object, vis_params, name, show=True):
    """Add an Earth Engine layer to a folium map."""
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=name,
        overlay=True,
        control=True,
        show=show
    ).add_to(folium_map)

# --- Endpoint corregido ---
@geo_bp.post("/serve-html")
def serve_html():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "The body of the request is empty"}), 400

    # --- VALIDACIÓN DE DATOS ---
    if "latitude" not in data or "longitude" not in data:
        return jsonify({"status": "error", "message": "Fields 'latitude' and 'longitude' are required."}), 400

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return jsonify({"status": "error", "message": "'latitude' and 'longitude' must be valid numbers."}), 400

    try:
        region = ee.Geometry.Point(longitude, latitude).buffer(50000)
        date_range_monthly = ('2024-05-01', '2024-05-31')
        date_range_annual = ('2023-01-01', '2023-12-31')

        # --- Lógica de GEE ---
        temp_image = (ee.ImageCollection('MODIS/061/MOD11A1')
                     .filterDate(date_range_monthly[0], date_range_monthly[1])
                     .median()
                     .select('LST_Day_1km')
                     .multiply(0.02)
                     .subtract(273.15)
                     .clip(region))
        temp_vis_params = {
            'min': -25,
            'max': 50,
            'palette': ['#000080', '#0000FF', '#00FFFF', '#00FF00', '#ADFF2F',
                       '#FFFF00', '#FFA500', '#FF4500', '#FF0000', '#8B0000', '#FFFFFF']
        }

        s2_image = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterDate(date_range_monthly[0], date_range_monthly[1])
                   .filterBounds(region)
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
                   .median())
        ndvi = s2_image.normalizedDifference(['B8', 'B4']).rename('NDVI').clip(region)
        ndvi_vis_params = {'min': 0, 'max': 0.5, 'palette': ['#ff0000', '#ffff00', '#00ff00']}

        no2_mean = collection_mean('COPERNICUS/S5P/NRTI/L3_NO2', 'NO2_column_number_density',
                                  date_range_annual[0], date_range_annual[1])
        so2_mean = collection_mean('COPERNICUS/S5P/NRTI/L3_SO2', 'SO2_column_number_density',
                                  date_range_annual[0], date_range_annual[1])
        o3_mean = collection_mean('COPERNICUS/S5P/NRTI/L3_O3', 'O3_column_number_density',
                                 date_range_annual[0], date_range_annual[1])
        co_mean = collection_mean('COPERNICUS/S5P/NRTI/L3_CO', 'CO_column_number_density',
                                 date_range_annual[0], date_range_annual[1])
        aer_mean = collection_mean('COPERNICUS/S5P/NRTI/L3_AER_AI', 'absorbing_aerosol_index',
                                  date_range_annual[0], date_range_annual[1])

        no2_norm = normalize(no2_mean, 0.0, 2e-4)
        so2_norm = normalize(so2_mean, 0.0, 1e-4)
        o3_norm = normalize(o3_mean, 0.0, 3e-4)
        co_norm = normalize(co_mean, 0.0, 3e-2)
        aer_norm = normalize(aer_mean, -1.0, 2.0)

        aq_index = (no2_norm.add(so2_norm).add(o3_norm).add(co_norm).add(aer_norm)
                   .divide(5)
                   .rename('AQ_Composite_0_100')
                   .clip(region))
        aq_vis_params = {
            'min': 0,
            'max': 100,
            'palette': ['#2DC937', '#E7B416', '#E77D11', '#CC3232', '#6B1A6B']
        }

        # --- CREAR MAPA FOLIUM NATIVO ---
        m = folium.Map(
            location=[latitude, longitude],
            zoom_start=9,
            tiles='OpenStreetMap'
        )

        # --- AÑADIR CAPAS DE EARTH ENGINE ---
        add_ee_layer(m, temp_image, temp_vis_params, 'Temperature (May 2024)', show=True)
        add_ee_layer(m, ndvi, ndvi_vis_params, 'Vegetation (May 2024)', show=False)
        add_ee_layer(m, aq_index, aq_vis_params, 'Air Quality Index (2023)', show=False)

        # Añadir control de capas
        folium.LayerControl().add_to(m)

        # --- OBTENER HTML ---
        html_payload = m._repr_html_()

        return jsonify({
            "status": "success",
            "message": "Map HTML generated successfully",
            "payload": html_payload,
        }), 200

    except Exception as e:
        print(f"ERROR en /serve-html: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e),
            "payload": None,
        }), 500
