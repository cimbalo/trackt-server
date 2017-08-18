from flask_sqlalchemy import SQLAlchemy
from flask.json import JSONEncoder
from core import db

class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        return getattr(obj.__class__, "to_json", JSONEncoder.default)(obj)

import time
import enum
import copy
from functools import reduce

# Create a custom JsonEncodedDict class in a file accessed by your models
import json
from sqlalchemy.ext import mutable
from sqlalchemy.types import TypeDecorator, Text

class JsonEncodedDict(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        else:
            return json.loads(value)

mutable.MutableDict.associate_with(JsonEncodedDict)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    contents = db.relationship('Content', backref='content.id', lazy=True)

    def __init__(self, username):
        self.username = username

    def __repr__(self):
        return '<User %r>' % self.username

class ContentTypeEnum(enum.Enum):
    movie = 1
    show = 2
    episode = 3

class UniqueId(db.Model):
    __table_args__ = (
        db.UniqueConstraint('source', 'value', name='uniqueid_table_source_value'),
    )
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(20))
    value = db.Column(db.Integer)
    content = db.relationship('Content')
    content_id = db.Column(db.Integer, db.ForeignKey('content.id'),
        nullable=False)

    def __init__(self, value, source, content_id=None):
        self.value = value
        self.content_id = content_id
        self.source = source

    def __repr__(self):
        return '<Id %s>' % self.value

    def to_json(self):
        return {self.source: self.value}

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    json = db.Column(JsonEncodedDict)
    contentType = db.Column(db.Enum(ContentTypeEnum))
    update_date = db.Column(db.DateTime)
    watched = db.Column(db.Boolean)
    plays = db.Column(db.Integer)

    uniqueIds = db.relationship('UniqueId', backref='uniqueId', lazy=True)

    show_id = db.Column(db.Integer, db.ForeignKey('content.id'), nullable=True)
    episodes = db.relationship('Content', remote_side=[show_id], lazy='dynamic')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, json, contentType, user_id, watched=False, show=None):
        self.json = json
        self.contentType = contentType
        self.user_id = user_id
        self.watched = watched
        self.plays = 1 if watched else 0
        self.show = show

    def __repr__(self):
        return '<Content %d, type=%s>' % (self.id, self.contentType)

    def to_json(self):
        result = copy.copy(self.json)
        result.update({'ids': dict((uniqueId.source, uniqueId.value) for uniqueId in list(self.uniqueIds))})
        result.update({'show_id': self.show_id})
        result.update({'id': self.id})
        result.update({'watched': self.watched})
        return result
