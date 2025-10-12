# routers/geo_router.py
#
# This module defines the geospatial API endpoints for simulation and data retrieval.

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for server environments

from flask import Blueprint, jsonify, request
import ee
from dotenv import load_dotenv
import os
from utils import GeoAnalytics, best_model, get_wind_speed
import numpy as np

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

            temp = int(best_model.predict(x))

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

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Simulation completed successfully",
                    "payload": report,
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
                        "payload": {"url": url, "layer": layer_name},
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
        sim_images = geoprocessor._create_simulated_images(preset, ee_geometry)

        if sim_images is None:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Simulation images could not be created",
                        "payload": None,
                    }
                ),
                500,
            )

        # Return URLs for simulated environmental layers
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Simulation completed successfully",
                    "payload": {
                        "sim_temp_url": geoprocessor.get_tile_url(
                            sim_images["temp"], geoprocessor.temp_vis_params
                        ),
                        "sim_ndvi_url": geoprocessor.get_tile_url(
                            sim_images["ndvi"], geoprocessor.ndvi_vis_params
                        ),
                        "sim_aq_url": geoprocessor.get_tile_url(
                            sim_images["aq"], geoprocessor.aq_vis_params
                        ),
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
