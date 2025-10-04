from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .MessageModel import Message
from .TagModel import Tag
from .UserModel import User
