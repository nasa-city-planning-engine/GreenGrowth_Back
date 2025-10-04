from . import db

message_tags = db.Table(
  'message_tags',
  db.Column('message_id', db.Integer, db.ForeignKey('message.id'), primary_key=True),
  db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)
