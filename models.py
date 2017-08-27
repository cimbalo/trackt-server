from flask_sqlalchemy import SQLAlchemy
from flask.json import JSONEncoder
from core import db
from sqlalchemy_enum34 import EnumType

class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        return getattr(obj.__class__, "to_json", JSONEncoder.default)(obj)

import time
import enum
import copy
from functools import reduce
import uuid
from datetime import datetime

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

class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(36), unique=True)
    refresh_token = db.Column(db.String(36), unique=True)
    user_code = db.Column(db.String(6), unique=True)
    created_at = db.Column(db.DateTime)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', lazy=True)

    def __init__(self):
        self.access_token = self.generate_token()
        self.refresh_token = self.generate_token()
        self.user_code = self.generate_user_code()
        self.created_at = datetime.utcnow()

    def __repr__(self):
        return '<Token %s>' % self.access_token

    def renew(self):
        self.access_token = self.refresh_token
        self.refresh_token = self.generate_token()
        self.created_at = datetime.utcnow()

    def generate_token(self):
        while True:
            result = str(uuid.uuid4())
            if not Token.query.filter((Token.access_token==result) | (Token.refresh_token==result)).first():
                break
        return result

    def generate_user_code(self):
        while True:
            result = str(uuid.uuid4())[0:6]
            if not Token.query.filter(Token.user_code==result).first():
                break
        return result

class ContentTypeEnum(enum.Enum):
    movie = "movie"
    show = "show"
    episode = "episode"

uniqueid_to_content = db.Table('uniqueid_to_content',
    db.Column('uniqueid_id', db.Integer, db.ForeignKey('unique_id.id')),
    db.Column('content_id', db.Integer, db.ForeignKey('content.id'))
)

class UniqueId(db.Model):
    __table_args__ = (
        db.UniqueConstraint('source', 'value', name='uniqueid_table_source_value'),
    )
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(20))
    value = db.Column(db.Integer)
    content = db.relationship('Content', secondary=uniqueid_to_content, backref='content', lazy='dynamic')


    def __init__(self, source, value, content_id=None):
        self.source = source
        self.value = value
        self.content_id = content_id

    def __repr__(self):
        return '<Id %s>' % self.value

    def to_json(self):
        return {self.source: self.value}

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    json = db.Column(JsonEncodedDict)
    contentType = db.Column(EnumType(ContentTypeEnum))
    update_date = db.Column(db.DateTime)
    watched = db.Column(db.Boolean)
    plays = db.Column(db.Integer)

    uniqueIds = db.relationship('UniqueId', secondary=uniqueid_to_content, backref='uniqueId', lazy=True)

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

def addUser(username):
    user = User.query.filter_by(username=username).all()
    if user:
        return user[0]
    result = User(username=username)
    db.session.add(result)
    db.session.flush()
    return result

def addUniqueId(user, value, source):
    id = UniqueId.query.filter_by(source=source, value=int(value)).join(uniqueid_to_content).join(Content).filter_by(user_id=user.id).all()
    if id:
        return id[0]
    result = UniqueId(source=source, value=int(value))
    db.session.add(result)
    db.session.flush()
    return result

def addShow(user, json_request):
    ids = []
    show = None
    for source, value in json_request['ids'].items():
        ids.append(addUniqueId(user=user, value=value, source=source))
        if ids[-1].content:
            contents = ids[-1].content.filter_by(user_id=user.id).all()
            if contents:
                show = contents[0]
    if show:
        show.json = {i:json_request[i] for i in json_request if i!='ids'}
    else:
        show = Content(json={i:json_request[i] for i in json_request if i!='ids'}, contentType=ContentTypeEnum.show, watched=True, user_id=user.id)
    for id in ids:
        show.uniqueIds.append(id)
    db.session.add(show)
    db.session.flush()
    return show

def addEpisode(user, json_request, show, progress=None):
    if progress > 99.9:
        progress = None
    if progress:
        json_request.update({'progress':progress})
    ids = []
    episode = None
    for source, value in json_request['ids'].items():
        if type(value) == dict:
            for source, value in value.items():
                ids.append(addUniqueId(user=user, value=value, source=source))
                if ids[-1].content:
                    contents = ids[-1].content.filter_by(user_id=user.id).all()
                    if contents:
                        episode = contents[0]
    if episode:
        episode.json = {i:json_request[i] for i in json_request if i!='ids'}
        episode.watched = not progress
    else:
        episode = Content(json={i:json_request[i] for i in json_request if i!='ids'}, contentType=ContentTypeEnum.episode, watched=not progress, user_id=user.id, show=show)
        episode.show_id = show.id
    for id in ids:
        episode.uniqueIds.append(id)
    db.session.add(episode)
    db.session.flush()
    return episode
