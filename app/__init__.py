import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from flask import Flask
from flask.ext.openid import OpenID
from config import basedir
from itsdangerous import URLSafeSerializer
from flask.ext.mail import Mail
import hyperdex.client
import hyperdex.admin
from bitcoin.core import COIN, b2lx
import bitcoin.wallet
import bitcoin.rpc

import dogecoin.wallet
import dogecoin.rpc

# OAuth
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic

from config import SERVER_DB_ADDRESS, NAME, ADMIN_EMAIL

app = Flask(__name__)
app.config.from_object('config')
url_safe_serializer = URLSafeSerializer(app.config['SECRET_KEY'])

#HyperDex Client
c = hyperdex.client.Client(SERVER_DB_ADDRESS, 1982)

#Flask-Mail
mail = Mail(app)

#Bitcoin
bitcoin.SelectParams(NAME)
rpc = bitcoin.rpc.Proxy()

# OpenAuth
authomatic = Authomatic(app.config['OPEN_AUTH_CONFIG'], app.config['SECRET_KEY'], report_errors=False)

#Dogecoin
dogecoin.SelectParams(NAME)
dogecoin_rpc = dogecoin.rpc.Proxy()

from app import views
