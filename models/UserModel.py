# models/UserModel.py
#
# Defines the User model for application users.

from models import db

class User(db.Model):
    """
    User model representing an application user.
    """
    __tablename__ = "users"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Username (must be unique and not null)
    username = db.Column(db.String(150), unique=True, nullable=False)

    # Email address (must be unique and not null)
    email = db.Column(db.String(150), unique=True, nullable=False)

    # Hashed password (never store plain text passwords)
    password = db.Column(db.String(256), nullable=False)

    # One-to-many relationship: a user can have multiple messages
    messages = db.relationship(
        "Message",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )
