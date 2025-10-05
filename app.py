# app.py
#
# Main entry point for the Flask application. Configures extensions, blueprints, and CLI commands.

from flask import Flask
from models import db, Tag
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy import event
from sqlite3 import Connection as SQLite3Connection
import os
from flask_cors import CORS
from routers import message_bp, user_bp, geo_bp

# Load environment variables from .env file
load_dotenv()

# Enable foreign key support for SQLite
@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Initialize Flask app and configure extensions
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app, resources={r"/*": {"origins": "*"}})
db.init_app(app)

# Register API blueprints
app.register_blueprint(message_bp)
app.register_blueprint(user_bp)
app.register_blueprint(geo_bp)

# Root endpoint for health check or welcome message
@app.route("/")
def index():
    return "root"

# CLI command to initialize the database and create default tags
@app.cli.command("init-db")
def init_db():
    db.create_all()
    DEFAULT_TAGS = ["Infraestructura", "Seguridad", "Movibilidad", "Servicios Publicos"]

    if not Tag.query.first():
        for tag_name in DEFAULT_TAGS:
            new_tag = Tag(name=tag_name)
            db.session.add(new_tag)
        db.session.commit()
        print("Tags creadas correctamente")

    print(Tag.get_tags())
    print("Base de datos inicializada")
