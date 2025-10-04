from . import db
from . import Tag

message_tags = db.Table(
  'message_tags',
  db.Column('message_id', db.Integer, db.ForeignKey('messages.id'), primary_key=True),
  db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class Message(db.Model):
  __tablename__ = "messages"

  id = db.Column(db.Integer, primary_key=True, autoincrement=True)
  content = db.Column(db.String(1000), nullable=False)

  user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

  tags = db.relationship('Tag', secondary=message_tags, lazy='subquery', backref=db.backref('mensaje', lazy=True))
