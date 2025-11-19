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
    # data request
    data = request.get_json()
    print("Incoming data:", data)

    if not data:
        return jsonify(
            {
                "status": "error",
                "message": "The body of the request is empty",
                "payload": None,
            }
        ), 400

    try:
        latitude = data.get("latitude", 0)
        longitude = data.get("longitude", 0)
        preset = data.get("preset")
        geometry = data.get("geometry")
        geometries = data.get("geometries")
        buffer = data.get("buffer", 1000)


        geometries_list = None
        if geometries is not None:
            if not isinstance(geometries, list) or len(geometries) == 0:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "`geometries` must be a non-empty list",
                            "payload": None,
                        }
                    ),
                    400,
                )
            geometries_list = geometries


        elif geometry is not None:
            if isinstance(geometry, list):
                if len(geometry) == 0:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "`geometry` list is empty",
                                "payload": None,
                            }
                        ),
                        400,
                    )
                geometries_list = geometry
            else:
                geometries_list = [geometry]
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameter: geometry or geometries",
                        "payload": None,
                    }
                ),
                400,
            )

        if preset is None:
            def _geom_has_preset(g):
                if not isinstance(g, dict):
                    return False
                if g.get("preset"):
                    return True
                props = g.get("properties")
                if isinstance(props, dict) and props.get("preset"):
                    return True
                return False

            missing_global_preset = any(not _geom_has_preset(g) for g in geometries_list)
            if missing_global_preset:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Missing required parameter: a top-level `preset` or per-geometry `preset` must be provided",
                            "payload": None,
                        }
                    ),
                    400,
                )

        co2 = data.get("co2") or 0
        ch4 = data.get("ch4") or 0
        n2o = data.get("n2o") or 0
        industries_used = data.get("industries_used", [])
        densidad = data.get("densidad") or 0
        trafico = data.get("trafico") or 0
        albedo = data.get("albedo") or 0
        arboles = data.get("arboles") or 0
        pasto = data.get("pasto") or 0
        agua = data.get("agua") or 0
        copa = data.get("copa") or 0

        reported_emissions = 0
        temp_industry = 0
        industry_model = None


        if preset == "industrial" or any(isinstance(g, dict) and g.get("preset") == "industrial" for g in geometries_list):
            local_temp = 0
            local_reported_emissions = 0
            if all(k in data for k in ("co2", "ch4", "n2o", "industries_used")):
                reported_emissions = co2 + (ch4 * GWP_CH4) + (n2o * GWP_N2O)
                industries_vector = [0] * len(industries)
                wind_speeds = get_wind_speed(lat=latitude, lon=longitude)
                if industries_used:
                    for i in industries_used:
                        if i in industries:
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
                industry_model = load_model_cached('industry_model.pkl')
                if industry_model is None:
                    print("Warning: Industry model not found; industrial predictions disabled")
                else:
                    try:
                        pred = industry_model.predict(x)
                        temp_industry = int(pred[0]) if hasattr(pred, '__len__') else int(pred)
                    except Exception as e:
                        print('Warning: failed to predict industry temp:', e)

            if temp_industry is None:
                temp_industry = 0
            if reported_emissions is None:
                reported_emissions = 0


        results = []
        for geom in geometries_list:
            try:
                if isinstance(geom, dict) and geom.get("type") == "Feature" and "geometry" in geom:
                    # Support GeoJSON Feature with properties: copy properties into geom so
                    # downstream code can read per-geometry keys like 'preset', 'densidad', etc.
                    geojson_area = geom["geometry"]
                    props = geom.get("properties", {})
                    if isinstance(props, dict):
                        # Only copy keys that don't already exist in the feature dict
                        for k, v in props.items():
                            if k not in geom:
                                geom[k] = v
                elif isinstance(geom, dict) and "geometry" in geom and isinstance(geom["geometry"], dict):
                    geojson_area = geom["geometry"]
                elif isinstance(geom, dict) and "type" in geom and "coordinates" in geom:
                    geojson_area = geom
                else:
                    raise ValueError("Invalid geometry entry; expected a GeoJSON geometry or Feature with 'geometry'")


                local_preset = None
                if isinstance(geom, dict) and geom.get("preset"):
                    local_preset = geom.get("preset")
                else:
                    local_preset = preset

                if local_preset not in ("industrial", "residential_real", "green_real"):
                    raise ValueError(f"Invalid or missing preset for geometry: {local_preset}")

                if local_preset == "industrial":
                    g_co2 = geom.get("co2", co2)
                    g_ch4 = geom.get("ch4", ch4)
                    g_n2o = geom.get("n2o", n2o)
                    g_industries_used = geom.get("industries_used", industries_used)

                    if any(k not in geom for k in ("co2", "ch4", "n2o", "industries_used")) and reported_emissions is None:
                        raise ValueError("Missing industrial parameters (co2, ch4, n2o, industries_used) for industrial preset")

                    local_reported_emissions = g_co2 + (g_ch4 * GWP_CH4) + (g_n2o * GWP_N2O)

                    local_temp = 0
                    if all(k in geom for k in ("co2", "ch4", "n2o", "industries_used")) and industry_model is not None:

                        local_industries_vector = [0] * len(industries)
                        for i in g_industries_used:
                            if i in industries:
                                local_industries_vector[industries[i]] = 1
                        wind_speeds = get_wind_speed(lat=latitude, lon=longitude)
                        data_to_predict = [
                            latitude,
                            longitude,
                            local_reported_emissions,
                            *local_industries_vector,
                            wind_speeds[0],
                            wind_speeds[1],
                            wind_speeds[2],
                        ]
                        x = np.array([data_to_predict], dtype=float)
                        try:
                            p = industry_model.predict(x)
                            local_temp = int(p[0]) if hasattr(p, '__len__') else int(p)
                        except Exception:
                            local_temp = temp_industry
                    else:
                        local_temp = temp_industry

                    analyzer = GeoAnalytics(
                        latitude=latitude,
                        longitude=longitude,
                        buffer=buffer,
                        temp_industry=local_temp,
                        aq_industry=local_reported_emissions,
                    )
                  
                    report = analyzer.impact_report(
                        geojson_area=geojson_area,
                        preset="industrial",
                        buffer_m=buffer,
                        calibrate=True,
                    )

                elif local_preset == "residential_real":

                    g_densidad = geom.get("densidad") or densidad
                    g_trafico = geom.get("trafico") or trafico
                    g_albedo = geom.get("albedo") or albedo

                    attr_real = {
                        "densidad": {"value": g_densidad, "unit": "buildings_per_km2"},
                        "trafico": {"value": g_trafico, "unit": "veh_day"},
                        "albedo": {"value": g_albedo, "unit": "albedo_0_1"},
                    }
                    analyzer = GeoAnalytics(latitude=latitude, longitude=longitude, buffer=buffer)
                    report = analyzer.impact_report(
                        geojson_area=geojson_area,
                        preset=("residential_real", attr_real),
                        buffer_m=1000,
                        calibrate=False,
                    )

                else: 
                    g_arboles = geom.get("arboles") or arboles
                    g_pasto = geom.get("pasto") or pasto
                    g_agua = geom.get("agua") or agua
                    g_copa = geom.get("copa") or copa

                    attr_green = {
                        "arboles": {"value": g_arboles, "unit": "trees_per_ha"},
                        "pasto": {"value": g_pasto, "unit": "pct"},
                        "agua": g_agua,
                        "copa": {"value": g_copa, "unit": "pct"},
                    }
                    analyzer = GeoAnalytics(latitude=latitude, longitude=longitude, buffer=buffer)
                    report = analyzer.impact_report(
                        geojson_area=geojson_area,
                        preset=("green_real", attr_green),
                        buffer_m=1000,
                        calibrate=False,
                    )

                sim_temp_url = None
                sim_ndvi_url = None
                sim_aq_url = None
                try:
                    if getattr(analyzer, 'sim_temp', None) is not None:
                        sim_temp_url = analyzer.get_tile_url(analyzer.sim_temp, analyzer.temp_vis_params)
                    if getattr(analyzer, 'sim_ndvi', None) is not None:
                        sim_ndvi_url = analyzer.get_tile_url(analyzer.sim_ndvi, analyzer.ndvi_vis_params)
                    if getattr(analyzer, 'sim_aq', None) is not None:
                        sim_aq_url = analyzer.get_tile_url(analyzer.sim_aq, analyzer.aq_vis_params)
                except Exception as e:
                    print('Warning: failed to generate sim tile URLs for a polygon:', e)

                results.append({
                    "report": report,
                    "sim_temp_url": sim_temp_url,
                    "sim_ndvi_url": sim_ndvi_url,
                    "sim_aq_url": sim_aq_url,
                })

            except Exception as e:
                results.append({
                    "report": None,
                    "sim_temp_url": None,
                    "sim_ndvi_url": None,
                    "sim_aq_url": None,
                    "error": str(e),
                })

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Simulation(s) completed successfully",
                    "payload": results,
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






