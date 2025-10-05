
# utils/geoprocessor.py
#
# This module defines the GeoProcessor class for geospatial data processing using Google Earth Engine.

import ee
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables and initialize Earth Engine
load_dotenv()
credentials = ee.ServiceAccountCredentials(
    email=None,
    key_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
)
ee.Initialize(credentials=credentials, project=os.getenv("GEE_PROJECT"))



class GeoProcessor:
    """
    Handles all Google Earth Engine logic for fetching, processing, and simulating geospatial data.
    This class is designed to be stateless for use in a Flask API.
    """

    def __init__(self, latitude, longitude, buffer=50000):
        """
        Initialize the GeoProcessor with a location and buffer (meters).
        Pre-calculates base layers for temperature, NDVI, and air quality.
        """
        self.latitude = latitude
        self.longitude = longitude
        self.buffer = buffer
        # The overall region of interest for clipping results
        self.region = ee.Geometry.Point(self.longitude, self.latitude).buffer(self.buffer)

        # Pre-calculate base layers on startup for performance
        self._initialize_vis_params()
        self._calculate_base_layers()
        print("🌍 Base layers (Temp, NDVI, AQ) calculated and ready.")

    def _initialize_vis_params(self):
        """
        Sets the visualization parameters for map tiles (temperature, NDVI, air quality).
        """
        self.temp_vis_params = {
            "min": -5,
            "max": 45,
            "palette": [
                "#000080", "#0000FF", "#00FFFF", "#00FF00", "#ADFF2F",
                "#FFFF00", "#FFA500", "#FF4500", "#FF0000",
            ],
        }
        self.ndvi_vis_params = {
            "min": 0,
            "max": 0.7,
            "palette": ["#ff0000", "#ffff00", "#00ff00", "#004d00"],
        }
        self.aq_vis_params = {
            "min": 0,
            "max": 100,
            "palette": ["#2DC937", "#E7B416", "#E77D11", "#CC3232", "#6B1A6B"],
        }
        print("🎨 Visualization parameters initialized.")

    def _calculate_base_layers(self):
        """
        Calculates all base data layers from Earth Engine.
        This is run once on initialization to ensure API endpoints are responsive.
        Layers: Temperature, NDVI (vegetation), Air Quality (composite index).
        """
        # Static date ranges for consistent results
        date_range_monthly = ("2024-05-01", "2024-05-31")
        date_range_annual = ("2023-01-01", "2023-12-31")

        # 1. Temperature Layer
        self.base_temp = (
            ee.ImageCollection("MODIS/061/MOD11A1")
            .filterBounds(self.region)
            .filterDate(*date_range_monthly)
            .median()
            .select("LST_Day_1km")
            .multiply(0.02)
            .subtract(273.15)
        )

        # 2. NDVI (Vegetation) Layer
        s2_image = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.region)
            .filterDate(*date_range_monthly)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10))
            .median()
        )
        self.base_ndvi = s2_image.normalizedDifference(["B8", "B4"]).rename("NDVI")

        # 3. Comprehensive Air Quality Index Layer (5-component model)
        aq_components = [
            self._get_normalized_gas(
                "COPERNICUS/S5P/NRTI/L3_NO2", "NO2_column_number_density", 0.0, 2e-4, date_range_annual
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/NRTI/L3_SO2", "SO2_column_number_density", 0.0, 1e-4, date_range_annual
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/NRTI/L3_O3", "O3_column_number_density", 0.0, 3e-4, date_range_annual
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/NRTI/L3_CO", "CO_column_number_density", 0.0, 3e-2, date_range_annual
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/NRTI/L3_AER_AI", "absorbing_aerosol_index", -1.0, 2.0, date_range_annual
            ),
        ]
        self.base_aq = (
            ee.ImageCollection(aq_components).mean().rename("AQ_Composite_0_100")
        )

    def _get_normalized_gas(self, coll_id, band, vmin, vmax, date_range):
        """
        Helper to fetch, process, and normalize a single gas component for the AQ index.
        Returns a normalized image (0-100 scale).
        """
        def apply_qa(img):
            has_qa = img.bandNames().contains("qa_value")
            # Selects the main band and applies a quality mask if available
            main_band_img = img.select(band)
            qa_mask = img.select("qa_value").gt(0.75)
            return ee.Image(
                ee.Algorithms.If(
                    has_qa, main_band_img.updateMask(qa_mask), main_band_img
                )
            )

        collection = (
            ee.ImageCollection(coll_id)
            .filterBounds(self.region)
            .filterDate(*date_range)
            .map(apply_qa)
            .mean()
        )

        normalized = (
            collection.subtract(vmin)
            .divide(ee.Number(vmax).subtract(vmin))
            .multiply(100)
            .clamp(0, 100)
        )
        return normalized.rename("v")

    def get_tile_url(self, image, vis_params):
        """
        Generates a tile URL for a given Earth Engine image and visualization parameters.
        """
        map_id = image.clip(self.region).getMapId(vis_params)
        return map_id["tile_fetcher"].url_format

    def _create_simulated_images(self, preset, ee_geometry):
        """
        Applies a simulation preset to the base layers within a given geometry.
        Returns simulated images for temperature, NDVI, and air quality.
        """
        presets = {
            "green_area": {
                "temp_op": "subtract", "temp_val": 5, "ndvi_val": 0.7, "aq_op": "subtract", "aq_val": 10,
            },
            "industrial": {
                "temp_op": "add", "temp_val": 8, "ndvi_val": 0.05, "aq_op": "add", "aq_val": 40,
            },
            "residential": {
                "temp_op": "add", "temp_val": 4, "ndvi_val": 0.15, "aq_op": "add", "aq_val": 20,
            },
        }
        config = presets.get(preset)
        if not config:
            return None

        # Create a binary mask from the user's geometry
        mask = ee.Image(0).paint(ee_geometry, 1)

        # Apply changes only where the mask is 1
        sim_temp_op = (
            self.base_temp.add(config["temp_val"])
            if config["temp_op"] == "add"
            else self.base_temp.subtract(config["temp_val"])
        )
        sim_temp = self.base_temp.where(mask, sim_temp_op)

        sim_ndvi = self.base_ndvi.where(mask, ee.Image.constant(config["ndvi_val"]))

        sim_aq_op = (
            self.base_aq.add(config["aq_val"])
            if config["aq_op"] == "add"
            else self.base_aq.subtract(config["aq_val"])
        )
        sim_aq = self.base_aq.where(mask, sim_aq_op).clamp(0, 100)

        return {"temp": sim_temp, "ndvi": sim_ndvi, "aq": sim_aq}

    def calculate_impact_stats(self, preset, ee_geometry):
        """
        Calculates baseline and post-simulation stats for a given geometry and preset.
        Returns a report with baseline, post-simulation, and delta values.
        """
        def mean_in_roi(img, band_name, scale):
            """
            Helper to compute the mean value of an image within the geometry.
            Returns a float or None.
            """
            stat = (
                img.select(band_name)
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geometry,
                    scale=scale,
                    maxPixels=1e12,
                    bestEffort=True,
                )
                .get(band_name)
            )
            return ee.Number(stat).getInfo()

        # 1. Calculate Baseline Stats
        baseline_stats = {
            "temp_c_mean": mean_in_roi(self.base_temp, "LST_Day_1km", 1000),
            "ndvi_mean": mean_in_roi(self.base_ndvi, "NDVI", 30),
            "aq_mean_0_100": mean_in_roi(self.base_aq, "AQ_Composite_0_100", 1000),
        }

        # 2. Get Simulated Images
        sim_images = self._create_simulated_images(preset, ee_geometry)
        if sim_images is None:
            return None

        # 3. Calculate Post-Simulation Stats
        post_stats = {
            "temp_c_mean": mean_in_roi(sim_images["temp"], "LST_Day_1km", 1000),
            "ndvi_mean": mean_in_roi(sim_images["ndvi"], "NDVI", 30),
            "aq_mean_0_100": mean_in_roi(sim_images["aq"], "AQ_Composite_0_100", 1000),
        }

        # 4. Calculate Deltas and assemble the final report
        delta_stats = {
            key: (
                (post_stats[key] - baseline_stats[key])
                if post_stats.get(key) is not None and baseline_stats.get(key) is not None
                else None
            )
            for key in baseline_stats
        }

        return {
            "preset": preset,
            "baseline": baseline_stats,
            "post_simulation": post_stats,
            "delta": delta_stats,
        }
