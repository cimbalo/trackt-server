#!/usr/bin/env python3

from flask import Flask, jsonify, request
from models import *
from core import db
import pprint

app = Flask(__name__)

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
    pprint.pprint(request.json)
    return jsonify({
        "device_code":"9fe6e70693bd0cd0d170be4bafc155e142110a138ee5dfc7b78682c58aa88a67",
        "user_code":"096B1193",
        "verification_url":"http://127.0.0.1:5000/",
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
    pprint.pprint(request.json)
    # return jsonify({}), 400
    return jsonify({
      "access_token": "dbaf9757982a9e738f05d249b7b5b4a266b3a139049317c4909f2f263572c781",
      "token_type": "bearer",
      "expires_in": 7200,
      "refresh_token": "76ba4c5c75c96f6087f58a4de10be6c00b29ea1ddc3b2022ee2016d1363e3a7c",
      "scope": "public",
      "created_at": int(time.time())
    })

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
def refresh_token():
    pprint.pprint(request.json)
    return jsonify({
      "access_token": "dbaf9757982a9e738f05d249b7b5b4a266b3a139049317c4909f2f263572c781",
      "token_type": "bearer",
      "expires_in": 7200,
      "refresh_token": "76ba4c5c75c96f6087f58a4de10be6c00b29ea1ddc3b2022ee2016d1363e3a7c",
      "scope": "public",
      "created_at": int(time.time())
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
def scrobble():
    if 'episode' in request.json:
        show = addShow(request.json['show'])
        print(request.json['progress'])
        addEpisode(json_request=request.json['episode'], show=show, progress=request.json.get('progress', None))
        db.session.commit()
    else:
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
def watched_shows():
    episodes = db.aliased(Content)
    shows = Content.query.filter_by(contentType=ContentTypeEnum.show).join(episodes, episodes.show_id == Content.id).filter_by(contentType=ContentTypeEnum.episode).filter(episodes.watched.is_(True)).join(User).filter_by(username='kaos').all()
    result=[]
    for show in shows:
        seasons = []
        for episode in show.episodes.filter_by(contentType=ContentTypeEnum.episode, watched=True):
            print(episode.watched)
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
def sync_episodes_progress():
    episodes = db.aliased(Content)
    shows = Content.query.filter_by(contentType=ContentTypeEnum.show).join(episodes, episodes.show_id == Content.id).filter_by(contentType=ContentTypeEnum.episode).filter(episodes.watched.is_(False)).join(User).filter_by(username='kaos')
    result=[]
    for show in shows.all():
        for episode in show.episodes:
            result.append({'show': show, 'episode': episode, 'type': 'episode', 'progress': episode.json['progress']})
    pprint.pprint(result)
    return jsonify(result)


'''
Return in progress movies

Response:
    TODO
'''
@app.route('/sync/playback/movies')
def sync_movies_progress():
    contents = Content.query.filter_by(watched=False, contentType=ContentTypeEnum.movie).join(User).filter_by(username='kaos').all()
    return jsonify(contents)

'''
Retrieve user settings

Response:
    {}
'''
@app.route('/users/settings')
def settings():
    return jsonify({}), 403

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
def sync():
    pprint.pprint(request.json)
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
def empty():
    return jsonify([])

'''
Catcha all other routes for debug purpose
'''
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    print("Unimplemented")
    pprint.pprint(request.json)
    raise NotImplemented

if __name__ == '__main__':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
    app.json_encoder = CustomJSONEncoder
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User('kaos')
        db.session.add(user)
        db.session.flush()

        def addUniqueId(value, source):
            id = UniqueId.query.filter_by(source=source, value=int(value)).first()
            if id:
                return id
            result = UniqueId(value=value, source=source)
            db.session.flush()
            return result

        def addShow(json_request):
            ids = []
            show = None
            for source, value in json_request['ids'].items():
                ids.append(addUniqueId(value=value, source=source))
                if ids[-1].content:
                    show = ids[-1].content
            if show:
                show.json = {i:json_request[i] for i in json_request if i!='ids'}
            else:
                show = Content(json={i:json_request[i] for i in json_request if i!='ids'}, contentType=ContentTypeEnum.show, watched=True, user_id=user.id)
            for id in ids:
                show.uniqueIds.append(id)
            db.session.add(show)
            db.session.flush()
            return show

        def addEpisode(json_request, show, progress=None):
            if progress > 99.9:
                progress = None
            if progress:
                json_request.update({'progress':progress})
            ids = []
            episode = None
            for source, value in json_request['ids'].items():
                if type(value) == dict:
                    for source, value in value.items():
                        ids.append(addUniqueId(value=value, source=source))
                        if ids[-1].content:
                            episode = ids[-1].content
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

        db.session.commit()
        app.run(debug=True)
