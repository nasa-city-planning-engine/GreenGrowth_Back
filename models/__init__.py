from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .MessageModel import Message
from .MessageTags import message_tags
from .TagModel import Tag
