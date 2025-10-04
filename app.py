from flask import Flask
from models import db, Tag
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy import event
from sqlite3 import Connection as SQLite3Connection
import os

load_dotenv()

@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route("/")
def index():
    return "root"

@app.cli.command("init-db")
def init_db():
    db.create_all()
    DEFAULT_TAGS = [
      'Infraestructura',
      'Seguridad',
      'Movibilidad',
      'Servicios Publicos'
    ]

    if not Tag.query.first():
      for tag_name in DEFAULT_TAGS:
        new_tag = Tag(name=tag_name)
        db.session.add(new_tag)

      db.session.commit()
      print('Tags creadas correctamente')

    print(Tag.get_tags())
    print("Base de datos inicializada")
