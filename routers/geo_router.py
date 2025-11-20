# routers/geo_router.py
#
# This module defines the geospatial API endpoints for simulation and data retrieval.

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for server environments

from flask import Blueprint, jsonify, request
import ee
from dotenv import load_dotenv
import os
from utils import GeoAnalytics, get_wind_speed
import numpy as np
import math
import pickle
import json
from functools import lru_cache


# Load environment variables from .env file
load_dotenv()

# Define the Blueprint for geospatial routes
geo_bp = Blueprint("geo", __name__, url_prefix="/geo")

GWP_CH4 = 25
GWP_N2O = 298

industries = {
    "Stationary Combustion": 0,
    "Electricity Generation": 1,
    "Adipic Acid Production": 2,
    "Aluminum Production": 3,
    "Ammonia Manufacturing": 4,
    "Cement Production": 5,
    "Electronics Manufacture": 6,
    "Ferroalloy Production": 7,
    "Fluorinated GHG Production": 8,
    "Glass Production": 9,
    "HCFC-22 Production and HFC-23 Destruction": 10,
    "Hydrogen Production": 11,
    "Iron and Steel Production": 12,
    "Lead Production": 13,
    "Lime Production": 14,
    "Magnesium Production": 15,
    "Miscellaneous Use of Carbonates": 16,
    "Nitric Acid Production": 17,
    "Petrochemical Production": 18,
    "Petroleum Refining": 19,
    "Phosphoric Acid Production": 20,
    "Pulp and Paper Manufacturing": 21,
    "Silicon Carbide Production": 22,
    "Soda Ash Manufacturing": 23,
    "SF6 from Electrical Equipment": 24,
    "Titanium Dioxide Production": 25,
    "Underground Coal Mines": 26,
    "Zinc Production": 27,
    "Municipal Landfills": 28,
    "Industrial Wastewater Treatment": 29,
    "Industrial Waste Landfills": 30,
    "Offshore Production": 31,
    "Natural Gas Processing": 32,
    "Natural Gas Transmission/Compression": 33,
    "Underground Natural Gas Storage": 34,
    "Liquified Natural Gas Storage": 35,
    "Liquified Natural Gas Import/Export Equipment": 36,
    "Petroleum Refinery (Producer)": 37,
    "Petroleum Product Importer": 38,
    "Petroleum Product Exporter": 39,
    "Natural Gas Liquids Fractionator": 40,
    "Natural Gas Local Distribution Company (supply)": 41,
    "Non-CO2 Industrial Gas Supply": 42,
    "Carbon Dioxide (CO2) Supply": 43,
    "Import and Export of Equipment Containing Fluorinated GHGs": 44,
    "Injection of Carbon Dioxide": 45,
    "Electric Transmission and Distribution Equipment": 46,
}

# Model loading: use a cached loader and a safe path
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "ML_Models")


@lru_cache(maxsize=4)
def load_model_cached(filename: str):
    path = os.path.join(MODEL_DIR, filename)
    try:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    except Exception:
        return None

# Endpoint: /geo/simulate
# Simulates an environmental impact report for a given location and parameters
@geo_bp.post("/simulate")
def get_simulation_report():
    data = request.get_json()
    print("Incoming data:", data)

    if not data:
        return jsonify(
            {
                "status": "error",
                "message": "The body of the request is empty",
                "payload": None,
            }
        )

    try:
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        preset = data.get("preset")
        geometry = data.get("geometry")
        buffer = data.get("buffer")
        industries_used = data.get("industries_used", [])
        co2 = data.get("co2", 0)
        ch4 = data.get("ch4", 0)
        n2o = data.get("n2o", 0)
        densidad = data.get("densidad", 0)
        trafico = data.get("trafico", 0)
        albedo = data.get("albedo", 0)
        arboles = data.get("arboles", 0)
        pasto = data.get("pasto", 0)
        agua = data.get("agua", False)
        copa = data.get("copa", 0)

        report = None

        if preset == "industrial":
            reported_emissions = co2 + (ch4 * GWP_CH4) + (n2o * GWP_N2O)
            industries_vector = [0] * len(industries)
            wind_speeds = get_wind_speed(lat=latitude, lon=longitude)
            if industries_used:
                for i in industries_used:
                    if i in industries:
                        print(industries[i])
                        industries_vector[industries[i]] = 1
                    else:
                        print(f"Warning: Unknown industry '{i}' ignored.")
            data_to_predict = [
                latitude,
                longitude,
                reported_emissions,
                *industries_vector,
                wind_speeds[0],
                wind_speeds[1],
                wind_speeds[2],
            ]

            x = np.array([data_to_predict], dtype=float)
            

            with open('\ML_Models\industry_model.pkl', 'rb') as file: 
                model = pickle.load(file)
            
            temp = int(model.predict(x))

            geoanalytics = GeoAnalytics(
                latitude=latitude,
                longitude=longitude,
                buffer=buffer,
                temp_industry=temp,
                aq_industry=reported_emissions,
            )
            report = geoanalytics.impact_report(
                geojson_area=geometry,
                preset="industrial",
                buffer_m=buffer,
                calibrate=True,
            )
        elif preset == "green_real":
            attrs_green = {
                "arboles": {"value": arboles, "unit": "trees_per_ha"},
                "pasto": {"value": pasto, "unit": "pct"},
                "agua": agua,
                "copa": {"value": copa, "unit": "pct"},
            }
            geoanalytics = GeoAnalytics(
                latitude=latitude,
                longitude=longitude,
                buffer=buffer,
            )

            report = geoanalytics.impact_report(
                geojson_area=geometry,
                preset=("green_real", attrs_green),
                buffer_m=1000,
                calibrate=False,
            )
        elif preset == "residential_real":
            attrs_real = {
                "densidad": {"value": densidad, "unit": "buildings_per_km2"},
                "trafico": {"value": trafico, "unit": "veh_day"},
                "albedo": {"value": albedo, "unit": "albedo_0_1"},
            }
            geoanalytics = GeoAnalytics(
                latitude=latitude,
                longitude=longitude,
                buffer=buffer,
            )

            report = geoanalytics.impact_report(
                geojson_area=geometry,
                preset=("residential_real", attrs_real),
                buffer_m=1000,
                calibrate=False,
            )

        if not report:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to calculate impact stats",
                        "payload": None,
                    }
                ),
                500,
            )

        # Try to build Earth Engine tile URLs for simulated layers produced by GeoAnalytics
        sim_temp_url = None
        sim_ndvi_url = None
        sim_aq_url = None
        try:
            if 'geoanalytics' in locals() and getattr(geoanalytics, 'sim_temp', None) is not None:
                sim_temp_url = geoanalytics.get_tile_url(geoanalytics.sim_temp, geoanalytics.temp_vis_params)
            if 'geoanalytics' in locals() and getattr(geoanalytics, 'sim_ndvi', None) is not None:
                sim_ndvi_url = geoanalytics.get_tile_url(geoanalytics.sim_ndvi, geoanalytics.ndvi_vis_params)
            if 'geoanalytics' in locals() and getattr(geoanalytics, 'sim_aq', None) is not None:
                sim_aq_url = geoanalytics.get_tile_url(geoanalytics.sim_aq, geoanalytics.aq_vis_params)
        except Exception as e:
            print('Warning: failed to generate sim tile URLs in simulate_polygon:', e)

        payload = {
            'report': report,
            'sim_temp_url': sim_temp_url,
            'sim_ndvi_url': sim_ndvi_url,
            'sim_aq_url': sim_aq_url,
        }

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Simulation completed successfully",
                    "payload": payload,
                }
            ),
            201,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "payload": None,
                }
            ),
            500,
        )


# Endpoint: /geo/get-initial-data/<layer_name>
# Retrieves initial geospatial data for a given layer and location
@geo_bp.get("/get-initial-data/<layer_name>")
def get_initial_data(layer_name):
    data = request.args

    try:
        # Validate required parameters
        latitude_str = data.get("latitude")
        longitude_str = data.get("longitude")
        buffer_str = data.get("buffer")

        if not latitude_str or not longitude_str or not buffer_str:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameters: latitude, longitude, and buffer",
                        "payload": None,
                    }
                ),
                400,
            )

        # Parse parameters
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        buffer = int(buffer_str)

        # Create a GeoAnalytics instance
        analyzer = GeoAnalytics(latitude=latitude, longitude=longitude, buffer=buffer)

        # Map layer names to their corresponding images and visualization parameters
        layer_map = {
            "temp": (analyzer.base_temp, analyzer.temp_vis_params),
            "ndvi": (analyzer.base_ndvi, analyzer.ndvi_vis_params),
            "aq": (analyzer.base_aq, analyzer.aq_vis_params),
        }
     

        if layer_name in layer_map:
            image, params = layer_map[layer_name]
            url = analyzer.get_tile_url(image, params)

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Initial data retrieved successfully",
                        "payload": {"url": url, "layer": layer_name}
                    }
                ),
                201,
            )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Layer not found",
                    "payload": None,
                }
            ),
            404,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "payload": None,
                }
            ),
            500,
        )


#Valid layer names are "heat", "NDVI", "AQ" respectively for avg_heat, avg_NVDI and avg_AQ. 
@geo_bp.get("/get-kpis/<layer_name>")
def getKpis(layer_name):
    #Currently gets avg-heat
    data = request.args
    try: 
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        buffer = data.get("buffer")
        if not latitude or not longitude or not buffer: 
            return jsonify({"status": "error", "message": "Missing params"}), 400      

        analyzer = GeoAnalytics(
            latitude=float(latitude), 
            longitude=float(longitude), 
            buffer=int(buffer)
        )

        kpis = analyzer.get_initial_kpis(layer_name)
        if kpis is None:
            return jsonify({"status": "error", "message": "Failed to calculate KPIs"}), 500
        
        return jsonify({
            "status": "success",
            "message": "KPIs calculated successfully",
            "payload": kpis
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500 

# Endpoint: /geo/simulate-tiles
# Simulates and returns tile URLs for different environmental layers
@geo_bp.post("/simulate-tiles")
def get_simulation_tiles():
    data = request.args

    try:
        latitude_str = data.get("latitude")
        longitude_str = data.get("longitude")
        buffer = int(data.get("buffer"))
        geometry_str = data.get("geometry")
        preset = data.get("preset")

        # Validate required parameters
        if not latitude_str or not longitude_str or not geometry_str:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameters: latitude, longitude, or geometry",
                        "payload": None,
                    }
                ),
                400,
            )

        # Parse parameters
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        geometry = float(
            geometry_str
        )  # NOTE: This may need to be parsed as geojson or WKT

        # Create a GeoAnalytics instance
        geoprocessor = GeoAnalytics(
            latitude=latitude,
            longitude=longitude,
            buffer=buffer,
        )

        # Convert geometry string to Earth Engine geometry
        ee_geometry = ee.Geometry(geometry)
        # Run a combined impact_report over the multipolygon to populate sim_* images
        try:
            geojson_multi = {"type": "MultiPolygon", "coordinates": geometry}
            geoprocessor.impact_report(geojson_area=geojson_multi, preset=preset or "residential", buffer_m=buffer, calibrate=False)
        except Exception:
            pass

        # Use sim_* images produced by impact_report
        temp_url = None
        ndvi_url = None
        aq_url = None
        if getattr(geoprocessor, "sim_temp", None) is not None:
            temp_url = geoprocessor.get_tile_url(geoprocessor.sim_temp, geoprocessor.temp_vis_params)
        if getattr(geoprocessor, "sim_ndvi", None) is not None:
            ndvi_url = geoprocessor.get_tile_url(geoprocessor.sim_ndvi, geoprocessor.ndvi_vis_params)
        if getattr(geoprocessor, "sim_aq", None) is not None:
            aq_url = geoprocessor.get_tile_url(geoprocessor.sim_aq, geoprocessor.aq_vis_params)
        # Return URLs for simulated environmental layers (may be None if generation failed)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Simulation completed successfully",
                    "payload": {
                        "sim_temp_url": temp_url,
                        "sim_ndvi_url": ndvi_url,
                        "sim_aq_url": aq_url,
                    },
                }
            ),
            201,
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "payload": None,
                }
            ),
            500,
        )
    

# Endpoint: /geo/simulate-polygon
# Simulates environmental impact for a given polygon area
@geo_bp.post("/simulate-polygons")
def simulate_polygons():
    data = request.get_json()
    print("Incoming data:", data)

    if not data:
        return jsonify({"status": "error", "message": "Request body empty"}), 400

    try:
        # --- 1. Extracción de Datos Generales ---
        latitude = data.get("latitude", 0)
        longitude = data.get("longitude", 0)
        buffer = data.get("buffer", 5000) 
        
        geometries = data.get("geometries") or ([data.get("geometry")] if data.get("geometry") else [])
        
        if not geometries:
            return jsonify({"status": "error", "message": "No geometries provided"}), 400

        # Datos globales (fallback)
        global_preset = data.get("preset")
        global_co2 = data.get("co2", 0)
        global_ch4 = data.get("ch4", 0)
        global_n2o = data.get("n2o", 0)
        global_industries = data.get("industries_used", [])
        
        # Diccionario de atributos globales aplanado
        global_vals = {
            "densidad": data.get("densidad", 0),
            "trafico": data.get("trafico", 0),
            "albedo": data.get("albedo", 0),
            "arboles": data.get("arboles", 0),
            "pasto": data.get("pasto", 0),
            "agua": data.get("agua", False),
            "copa": data.get("copa", 0)
        }

        # --- 2. Inicializar Analizador GLOBAL ---
        global_analyzer = GeoAnalytics(latitude=latitude, longitude=longitude, buffer=buffer)
        
        individual_reports = []
        batch_visualization_data = []
        
        industry_model = load_model_cached('industry_model.pkl')

        # --- 3. Bucle de Cálculo ---
        for geom in geometries:
            # Normalización GeoJSON/Feature
            geojson_geom = geom.get("geometry") if geom.get("type") == "Feature" else geom
            props = geom.get("properties", {}) if geom.get("type") == "Feature" else geom
            
            local_preset = props.get("preset", global_preset)
            if not local_preset:
                continue 

            local_temp_delta = 0
            local_aq_delta = 0
            target_ndvi_val = 0.1 

            # A) INDUSTRIAL
            if local_preset == "industrial":
                l_co2 = props.get("co2", global_co2)
                l_ch4 = props.get("ch4", global_ch4)
                l_n2o = props.get("n2o", global_n2o)
                l_inds = props.get("industries_used", global_industries)
                
                local_emissions = l_co2 + (l_ch4 * GWP_CH4) + (l_n2o * GWP_N2O)
                local_aq_delta = local_emissions 

                if industry_model:
                    inds_vec = [0] * len(industries)
                    for i in l_inds:
                        if i in industries: inds_vec[industries[i]] = 1
                    wind = get_wind_speed(latitude, longitude)
                    x_input = [latitude, longitude, local_emissions] + inds_vec + list(wind)
                    try:
                        pred = industry_model.predict(np.array([x_input], dtype=float))
                        local_temp_delta = int(pred[0]) if hasattr(pred, '__len__') else int(pred)
                    except Exception as e:
                        print(f"ML Error: {e}")
                
                target_ndvi_val = 0.15

            # B) RESIDENCIAL
            elif local_preset == "residential_real":
                local_temp_delta = 2 
                target_ndvi_val = 0.3 

            # C) VERDE
            elif local_preset == "green_real":
                local_temp_delta = -2 
                target_ndvi_val = 0.65 

            
            # --- Preparación del Argumento Preset (CORREGIDO: Unidades Explícitas) ---
            local_analyzer = GeoAnalytics(latitude=latitude, longitude=longitude, buffer=1000)
            
            preset_arg = local_preset
            
            if local_preset == "residential_real":
                # Mapeo explícito de unidades requeridas por _GA_CFG
                attrs = {
                    "densidad": {"value": props.get("densidad", global_vals["densidad"]), "unit": "buildings_per_km2"},
                    "trafico":  {"value": props.get("trafico", global_vals["trafico"]),   "unit": "veh_day"},
                    "albedo":   {"value": props.get("albedo", global_vals["albedo"]),     "unit": "albedo_0_1"}
                }
                preset_arg = (local_preset, attrs)
                
            elif local_preset == "green_real":
                # Mapeo explícito de unidades requeridas por _GA_CFG
                attrs = {
                    "arboles": {"value": props.get("arboles", global_vals["arboles"]), "unit": "trees_per_ha"},
                    "pasto":   {"value": props.get("pasto", global_vals["pasto"]),     "unit": "pct"},
                    "copa":    {"value": props.get("copa", global_vals["copa"]),       "unit": "pct"},
                    "agua":    props.get("agua", global_vals["agua"]) # Agua es booleano directo, no dict
                }
                preset_arg = (local_preset, attrs)

            # Calculamos reporte
            report = local_analyzer.impact_report(geojson_geom, preset=preset_arg, calibrate=False)
            
            individual_reports.append({
                "geometry_index": geometries.index(geom),
                "report": report
            })

            batch_visualization_data.append({
                "geometry": global_analyzer._geojson_to_ee_geom(geojson_geom),
                "lst_extra": local_temp_delta,
                "aq_extra": local_aq_delta,
                "ndvi_target": target_ndvi_val
            })

        # --- 4. Generación de Mapa Unificado ---
        print("🗺️ Generating unified batch visualization...")
        global_analyzer.sim_batch_visualization(batch_visualization_data)

        map_urls = {
            "sim_temp_url": None, "sim_ndvi_url": None, "sim_aq_url": None
        }
        try:
            if getattr(global_analyzer, 'sim_temp', None):
                map_urls["sim_temp_url"] = global_analyzer.get_tile_url(global_analyzer.sim_temp, global_analyzer.temp_vis_params)
            if getattr(global_analyzer, 'sim_ndvi', None):
                map_urls["sim_ndvi_url"] = global_analyzer.get_tile_url(global_analyzer.sim_ndvi, global_analyzer.ndvi_vis_params)
            if getattr(global_analyzer, 'sim_aq', None):
                map_urls["sim_aq_url"] = global_analyzer.get_tile_url(global_analyzer.sim_aq, global_analyzer.aq_vis_params)
        except Exception as e:
            print(f"Tile Generation Error: {e}")

        return jsonify({
            "status": "success",
            "message": "Batch simulation completed",
            "payload": {
                "individual_reports": individual_reports,
                "map_urls": map_urls
            }
        }), 201

    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500




