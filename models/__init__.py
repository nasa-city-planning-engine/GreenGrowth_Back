# models/__init__.py
#
# This module initializes the SQLAlchemy database instance and imports all models
# so they are available for use throughout the application.

from flask_sqlalchemy import SQLAlchemy

# Create the SQLAlchemy database instance
db = SQLAlchemy()

# Import all models to make them accessible via the 'models' package
from .MessageModel import Message, message_tags
from .TagModel import Tag
from .UserModel import User
