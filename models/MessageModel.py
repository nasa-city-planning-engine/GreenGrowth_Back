# models/MessageModel.py
#
# Defines the Message model and the association table for the many-to-many relationship
# between messages and tags.

from . import db

# Association table for the many-to-many relationship between Message and Tag
message_tags = db.Table(
    "message_tags",
    db.Column("message_id", db.Integer, db.ForeignKey("messages.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Message(db.Model):
    """
    Message model representing a user message with geolocation and tags.
    """
    __tablename__ = "messages"

    # Primary key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Message content (max 1000 characters)
    content = db.Column(db.String(1000), nullable=False)

    # Location as a string (e.g., address or description)
    location = db.Column(db.String(256), nullable=False)

    # Latitude and longitude for geospatial data
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # Foreign key to the user who created the message
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Many-to-many relationship with Tag
    tags = db.relationship(
        "Tag",
        secondary=message_tags,
        lazy="subquery",
        backref=db.backref("messages", lazy=True),  # Use English for backref
    )
