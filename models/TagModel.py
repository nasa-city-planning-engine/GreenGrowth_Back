
# models/TagModel.py
#
# Defines the Tag model for categorizing messages.

from . import db
from .MessageModel import message_tags


class Tag(db.Model):
    """
    Tag model representing a category or label that can be assigned to messages.
    """
    __tablename__ = "tags"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Tag name (must be unique and not null)
    name = db.Column(db.String(50), unique=True, nullable=False)

    @staticmethod
    def get_tags():
        """
        Retrieve all tags from the database.
        """
        return Tag.query.all()
