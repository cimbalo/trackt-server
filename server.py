#!/usr/bin/env python3

from flask import Flask, jsonify, request, render_template, redirect
from models import *
from core import db
import config
import pprint
from functools import wraps

app = Flask(__name__)

class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

def required_roles():
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                print(request.headers.get('Authorization'))
                authorization = request.headers.get('Authorization').split(" ")[1]
                user_token = Token.query.filter_by(access_token=authorization).first()
                if not user_token:
                    raise Exception
            except:
                return "", 403
            return f(user_token, *args, **kwargs)
        return wrapped
    return wrapper
@app.route('/register')
def redirect_register():
    return redirect("/static/register.html", code=302)

@app.route('/register', methods=['POST'])
def register():
    user_token = Token.query.filter_by(user_code=request.form['user_code']).first()
    if user_token:
        user_token.user = addUser(username=request.form['username'])
        db.session.add(user_token)
        db.session.commit()
        return "OK"
    else:
        return "Unknown user code"

'''
Start authorization for a device
    Send back mainly a user code and a verification url for user verification
    and a device code for the application

Parameters:
    {'client_id': 'd4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868'}

Response:
    {
        "device_code":"9fe6e70693bd0cd0d170be4bafc155e142110a138ee5dfc7b78682c58aa88a67",
        "user_code":"096B1193",
        "verification_url":"http://127.0.0.1:5000/",
        "expires_in":600,
        "interval":5
    }
'''
@app.route('/oauth/device/code', methods=['POST'])
def code():
    app.logger.debug('Received authorization request')
    token = Token()
    db.session.add(token)
    db.session.commit()
    return jsonify({
        "device_code":token.access_token,
        "user_code": token.user_code,
        "verification_url":"%s/register"%(config.server_url),
        "expires_in":600,
        "interval":5
    })

'''
Check for authorized device
    The device can poll this handler to retrive it's new token if authorization suceeed

Parameters:
    {
        'client_id': 'd4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868',
        'client_secret': 'b5fcd7cb5d9bb963784d11bbf8535bc0d25d46225016191eb48e50792d2155c0',
        'code': '9fe6e70693bd0cd0d170be4bafc155e142110a138ee5dfc7b78682c58aa88a67'
    }
Response:
    Error 400
    or if authentication succeeed:
    {
      "access_token": "dbaf9757982a9e738f05d249b7b5b4a266b3a139049317c4909f2f263572c781",
      "token_type": "bearer",
      "expires_in": 7200,
      "refresh_token": "76ba4c5c75c96f6087f58a4de10be6c00b29ea1ddc3b2022ee2016d1363e3a7c",
      "scope": "public",
      "created_at": 1487889741
    }
'''
@app.route('/oauth/device/token', methods=['POST'])
def device_token():
    app.logger.debug('Received token request')
    token = Token.query.filter_by(access_token=request.json['code']).first()
    if token:
        if token.user:
            token.renew()
            db.session.add(token)
            db.session.commit()
            return jsonify({
              "access_token": token.access_token,
              "token_type": "bearer",
              "expires_in": 7776000,
              "refresh_token": token.refresh_token,
              "scope": "public",
              "created_at": int(token.created_at.timestamp())
            })
        else:
            return jsonify({}), 400
    else:
        return jsonify({}), 404

'''
Refresh token

Parameters:
    {
        'client_id': 'd4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868',
        'client_secret': 'b5fcd7cb5d9bb963784d11bbf8535bc0d25d46225016191eb48e50792d2155c0',
        'grant_type': 'refresh_token',
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        'refresh_token': '76ba4c5c75c96f6087f58a4de10be6c00b29ea1ddc3b2022ee2016d1363e3a7c'
    }

Response:
    {
      "access_token": "dbaf9757982a9e738f05d249b7b5b4a266b3a139049317c4909f2f263572c781",
      "token_type": "bearer",
      "expires_in": 7200,
      "refresh_token": "76ba4c5c75c96f6087f58a4de10be6c00b29ea1ddc3b2022ee2016d1363e3a7c",
      "scope": "public",
      "created_at": 1487889741
    }
'''
@app.route('/oauth/token', methods=['POST'])
@required_roles()
def refresh_token(user_token):
    app.logger.debug('Received refresh token request')
    user_token.renew()
    db.session.add(user_token)
    db.session.commit()
    return jsonify({
      "access_token": user_token.access_token,
      "token_type": "bearer",
      "expires_in": 7776000,
      "refresh_token": user_token.refresh_token,
      "scope": "public",
      "created_at": int(user_token.created_at.timestamp())
    })

'''
Notify scrobbler event

Parameters:
    for a episode:
        {
            'app_date': None,
            'app_version': '2.14.1',
            'episode': {'collected': 1,
                     'ids': {'episodeid': 2, 'tvdb': {'tvdb': '184651'}},
                     'number': 3,
                     'plays': 8,
                     'rating': 0,
                     'season': 3,
                     'title': 'My White Whale',
                     'watched': 0},
            'progress': 81.26749473043007,
            'show': {
                'ids': {
                        'tvdb': '76156'
                        },
                'title': 'Scrubs',
                'year': 2001
                }
        }
    for a movie:
        TODO

Response:
    Send back te request body to confirm notification succeed
'''
@app.route('/scrobble/start', methods=['POST'])
@app.route('/scrobble/pause', methods=['POST'])
@app.route('/scrobble/stop', methods=['POST'])
@required_roles()
def scrobble(user_token):
    app.logger.debug('Received scrobble request')
    if 'episode' in request.json:
        show = addShow(user=user_token.user, json_request=request.json['show'])
        app.logger.debug('Scrobble progress at %f', request.json.get('progress', .0))
        addEpisode(user=user_token.user, json_request=request.json['episode'], show=show, progress=request.json.get('progress', None))
        app.logger.debug('Save progres')
        db.session.commit()
    else:
        app.logger.warn('Scrobble request without episode data')
        raise NotImplemented
    return jsonify(request.json)

'''
Return the watched episodes

Response:
    [ {
       "plays": 1,
       "last_watched_at": "2017-08-16T13:04:11.000Z",
       "show": {
         "title": "Scrubs",
         "year": 2001,
         "ids": {
           "trakt": 1,
           "tvdb": 76156,
         }
       },
       "seasons": [
         {
           "number": 3,
           "episodes": [
             {
               "ids": {
                   "tvdb": 184651,
               },
               "number": 3,
               "plays": 8,
               "last_watched_at": "2017-08-16T13:04:11.000Z"
             },
           ]
         },
       ]
     }
     ]
    ]
'''
@app.route('/sync/watched/shows')
@required_roles()
def watched_shows(user_token):
    app.logger.debug('Received sync requeste')
    episodes = db.aliased(Content)
    shows = Content.query.filter_by(contentType=ContentTypeEnum.show).join(episodes, episodes.show_id == Content.id).filter_by(contentType=ContentTypeEnum.episode).filter(episodes.watched.is_(True)).filter(episodes.user_id==user_token.user.id).all()
    result=[]
    for show in shows:
        seasons = []
        for episode in show.episodes.filter_by(contentType=ContentTypeEnum.episode, watched=True):
            seasonNumber = episode.json['season']
            season = list(filter(lambda d: d['number'] == seasonNumber, seasons))
            if not season:
                season = [{'number': seasonNumber, 'episodes': []}]
                seasons.append(season[0])
            season[0]['episodes'].append(episode)

        result.append({'show': show, 'seasons': seasons})

    return jsonify(result)

'''
Return in progress episodes

Response:
    [
  {
    "progress": 75.2,
    "paused_at": "2015-01-25T22:01:32.000Z",
    "id": 37,
    "type": "episode",
    "episode": {
      "season": 3,
      "number": 7,
      "title": "My Fifteen Seconds",
      "ids": {
        "tvdb": 184655,
      }
    },
    "show": {
      "title": "Scrubs",
      "year": 2001,
      "ids": {
        "tvdb": 76156,
      }
    }
  }
  ]
'''
@app.route('/sync/playback/episodes')
@required_roles()
def sync_episodes_progress(user_token):
    app.logger.debug('Received episode sync request')
    episodes = db.aliased(Content)
    shows = Content.query.filter_by(contentType=ContentTypeEnum.show).join(episodes, episodes.show_id == Content.id).filter_by(contentType=ContentTypeEnum.episode).filter(episodes.watched.is_(False)).filter(episodes.user_id==user_token.user.id)
    result=[]
    for show in shows.all():
        for episode in show.episodes:
            result.append({'show': show, 'episode': episode, 'type': 'episode', 'progress': episode.json['progress']})
    return jsonify(result)


'''
Return in progress movies

Response:
    TODO
'''
@app.route('/sync/playback/movies')
@required_roles()
def sync_movies_progress(user_token):
    app.logger.debug('Received sync movie request')
    contents = Content.query.filter_by(watched=False, contentType=ContentTypeEnum.movie).filter(episodes.user_id==user_token.user.id).all()
    return jsonify(contents)

'''
Retrieve user settings

Response:
    {}
'''
@app.route('/users/settings')
@required_roles()
def settings(user_token):

    app.logger.debug('Received settings sync request')
    return jsonify({
                      "user": {
                        "username": "justin",
                        }
                    })

'''
Receive collection to sync

Parameters:
    a list of dictionary containg 'shows' and 'movies' keys
    TODO

Response:
    Send back te request body to confirm sync succeed
'''
@app.route('/sync/collection', methods=['POST'])
@app.route('/sync/history', methods=['POST'])
@required_roles()
def sync(user_token):
    app.logger.debug('Received sync data')
    return jsonify(request.json)

'''
Unimplemented, but for these routes we don't want to generate errors
'''
@app.route('/sync/ratings/movies')
@app.route('/sync/ratings/shows')
@app.route('/sync/ratings/episodes')
@app.route('/sync/collection/movies')
@app.route('/sync/collection/shows')
@app.route('/sync/watched/movies')
@required_roles()
def empty(user_token):
    app.logger.debug('Received sync request')
    return jsonify([])

'''
Catcha all other routes for debug purpose
'''
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    app.logger.info('Unimplemented: %s', path)
    app.logger.debug(request.json)

if __name__ == '__main__':
    app.config['SQLALCHEMY_DATABASE_URI'] = config.db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.wsgi_app = ReverseProxied(app.wsgi_app)
    app.json_encoder = CustomJSONEncoder
    db.init_app(app)
    with app.app_context():
        # db.drop_all()
        db.create_all()
        app.run(debug=config.debug)
