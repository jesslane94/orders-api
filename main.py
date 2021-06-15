from google.cloud import datastore
from flask import Flask, jsonify, redirect, render_template, session, url_for, request, _request_ctx_stack
import requests
from six.moves.urllib.parse import urlencode
import json
from authlib.integrations.flask_client import OAuth
import items
import orders
import constants

# base code from Module 7 in CS493: Cloud Application Development

app = Flask(__name__)
app.secret_key = 'SUPERSECRETKEY'
app.register_blueprint(items.bp)
app.register_blueprint(orders.bp)
client = datastore.Client()
USERS = 'USERS'
ORDERS = 'ORDERS'
ITEMS = 'ITEMS'

oauth = OAuth(app)
auth0 = oauth.register(
    'auth0',
    client_id=constants.CLIENT_ID,
    client_secret=constants.CLIENT_SECRET,
    api_base_url="https://" + constants.DOMAIN,
    access_token_url="https://" + constants.DOMAIN + "/oauth/token",
    authorize_url="https://" + constants.DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
)


@app.route('/')
def index():
    return render_template("home.html")


# used when testing with Postman and no UI
@app.route('/login', methods=['POST'])
def login_user():
    content = request.get_json()
    username = content["username"]
    password = content["password"]
    body = {'grant_type': 'password', 'username': username,
            'password': password,
            'client_id': constants.CLIENT_ID,
            'client_secret': constants.CLIENT_SECRET
            }
    headers = {'content-type': 'application/json'}
    url = 'https://' + constants.DOMAIN + '/oauth/token'
    r = requests.post(url, json=body, headers=headers)
    return r.text, 200, {'Content-Type': 'application/json'}


# retrieve user info to display on webpage
@app.route('/callback')
def callback_handling():
    user_flag = False
    # Handles response from token endpoint
    id_token = auth0.authorize_access_token()["id_token"]
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    # store user id in datastore for later retrieval
    # check if already in system first
    query = client.query(kind=USERS)
    results = list(query.fetch())
    for r in results:
        if r["user_id"] == userinfo["sub"]:
            user_flag = True
    if not user_flag:
        new_user = datastore.entity.Entity(key=client.key(USERS))
        new_user.update({"user_id": userinfo["sub"], "name": userinfo["name"]})
        client.put(new_user)

    # Store the user information in flask session.
    session['jwt_payload'] = userinfo
    session['profile'] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'picture': userinfo['picture'],
    }
    session['token'] = id_token
    return redirect('/dashboard')


@app.route('/ui_login')
def ui_login():
    return auth0.authorize_redirect(redirect_uri=constants.CALLBACK_URL)


@app.route('/dashboard')
# @requires_auth
def dashboard():
    return render_template('dashboard.html',
                           userinfo=session['profile'],
                           userinfo_pretty=json.dumps(session['jwt_payload'], indent=4),
                           token=session['token'])


@app.route('/logout')
def logout():
    # Clear session stored data
    session.clear()
    # Redirect user to logout endpoint
    params = {'returnTo': url_for('index', _external=True), 'client_id': constants.CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))


# retrieve list of all users
@app.route('/users', methods=['GET'])
def users_get():
    query = client.query(kind=USERS)
    results = list(query.fetch())
    return json.dumps(results), 200


if __name__ == '__main__':
    app.run(host='localhost', port=8080, debug=True)
