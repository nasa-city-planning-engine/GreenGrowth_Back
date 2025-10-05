
# routers/geo_router.py
#
# This module defines the geospatial API endpoints for simulation and data retrieval.

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend for server environments

from flask import Blueprint, jsonify, request
import ee
from dotenv import load_dotenv
import os
from utils import GeoProcessor

# Load environment variables from .env file
load_dotenv()

# Define the Blueprint for geospatial routes
geo_bp = Blueprint("geo", __name__, url_prefix="/geo")



# Endpoint: /geo/simulate
# Simulates an environmental impact report for a given location and parameters
@geo_bp.get("/simulate")
def get_simulation_report():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "The body of the request is empty",
            "payload": None,
        })

    try:
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        preset = data.get("preset")
        geometry = data.get("geometry")
        buffer = data.get("buffer")

        # Validate required parameters
        if not latitude_str or not longitude_str:
            return (
                jsonify({
                    "status": "error",
                    "message": "Missing required parameters: latitude and longitude",
                    "payload": None,
                }),
                400,
            )

        if not area_type:
            return (
                jsonify({
                    "status": "error",
                    "message": "Missing required parameter: area_type",
                    "payload": None,
                }),
                400,
            )

        # Parse and process parameters
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        buffer = int(data.get("buffer"))

        # Create a GeoProcessor instance for the given location
        geoprocessor = GeoProcessor(
            latitude=latitude,
            longitude=longitude,
            buffer=buffer,
        )

        # Convert geometry string to Earth Engine geometry
        ee_geometry = ee.Geometry(geometry)
        report = geoprocessor.calculate_impact_stats(preset, ee_geometry)

        return (
            jsonify({
                "status": "success",
                "message": "Simulation completed successfully",
                "payload": report,
            }),
            201,
        )
    except Exception as e:
        return (
            jsonify({
                "status": "error",
                "message": str(e),
                "payload": None,
            }),
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
                jsonify({
                    "status": "error",
                    "message": "Missing required parameters: latitude, longitude, and buffer",
                    "payload": None,
                }),
                400,
            )

        # Parse parameters
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        buffer = int(buffer_str)

        # Create a GeoProcessor instance
        analyzer = GeoProcessor(latitude=latitude, longitude=longitude, buffer=buffer)

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
                jsonify({
                    "status": "success",
                    "message": "Initial data retrieved successfully",
                    "payload": {"url": url, "layer": layer_name},
                }),
                201,
            )
        return (
            jsonify({
                "status": "error",
                "message": "Layer not found",
                "payload": None,
            }),
            404,
        )

    except Exception as e:
        return (
            jsonify({
                "status": "error",
                "message": str(e),
                "payload": None,
            }),
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
                jsonify({
                    "status": "error",
                    "message": "Missing required parameters: latitude, longitude, or geometry",
                    "payload": None,
                }),
                400,
            )

        # Parse parameters
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        geometry = float(geometry_str)  # NOTE: This may need to be parsed as geojson or WKT

        # Create a GeoProcessor instance
        geoprocessor = GeoProcessor(
            latitude=latitude,
            longitude=longitude,
            buffer=buffer,
        )

        # Convert geometry string to Earth Engine geometry
        ee_geometry = ee.Geometry(geometry)
        sim_images = geoprocessor._create_simulated_images(preset, ee_geometry)

        if sim_images is None:
            return (
                jsonify({
                    "status": "error",
                    "message": "Simulation images could not be created",
                    "payload": None,
                }),
                500,
            )

        # Return URLs for simulated environmental layers
        return (
            jsonify({
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
            }),
            201,
        )
    except Exception as e:
        return (
            jsonify({
                "status": "error",
                "message": str(e),
                "payload": None,
            }),
            500,
        )
