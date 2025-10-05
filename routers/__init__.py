# routers/__init__.py
#
# This module imports and exposes all API blueprints for easy registration in the main app.

from .message_router import message_bp  # Blueprint for message-related routes
from .user_router import user_bp      # Blueprint for user-related routes
from .geo_router import geo_bp        # Blueprint for geospatial routes
