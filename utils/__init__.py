
# utils/__init__.py
#
# This module exposes utility classes and functions for use throughout the application.

from .geoprocessor import GeoAnalytics  # Geospatial processing utility class

from .industry import best_model  # Function to determine the best industry model based on input data
from .wind import get_wind_speed  # Function to retrieve wind speed data from Google Earth Engine
