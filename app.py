# app.py

from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlite3 import Connection as SQLite3Connection
import os

from models import db, Tag

# Load environment variables
load_dotenv()


# Enable foreign key support for SQLite (from old app)
@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app():
    app = Flask(__name__)

    # Database config
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Allow CORS (same as old version)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Initialize SQLAlchemy without creating DB yet
    db.init_app(app)

    # Register blueprints inside context (best practice)
    with app.app_context():
        from routers import message_bp, user_bp, geo_bp

        app.register_blueprint(message_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(geo_bp)  # Was active in old version

        # Root endpoint
        @app.route("/")
        def index():
            return "root"

        # CLI command: init-db
        @app.cli.command("init-db")
        def init_db():
            db.create_all()

            DEFAULT_TAGS = [
                "Infraestructura",
                "Seguridad",
                "Movibilidad",
                "Servicios Publicos",
            ]

            if not Tag.query.first():
                for tag_name in DEFAULT_TAGS:
                    db.session.add(Tag(name=tag_name))
                db.session.commit()
                print("Tags creadas correctamente")

            print(Tag.get_tags())
            print("Base de datos inicializada")

    return app


# Gunicorn entry point
app = create_app()
