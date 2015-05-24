from flask import render_template, flash, redirect, session, url_for, request, g, make_response

from datetime import datetime
from functools import wraps
import unicodedata
import httplib2
import uuid
import json

import order_book
from app import app, c, url_safe_serializer, mail, rpc, authomatic, dogecoin_rpc, ADMIN_EMAIL
from .forms import *
#from currency_utils import *
from flask.ext.mail import Message

from bitcoin.core import COIN, b2lx
import bitcoin.wallet
import bitcoin.rpc
try:
    from bitcoin.case58 import CBitcoinAddress
except:
    from bitcoin.wallet import CBitcoinAddress

import dogecoin.wallet
import dogecoin.rpc
try:
    from dogecoin.case58 import CDogecoinAddress
except:
    from dogecoin.wallet import CDogecoinAddress    

# OAuth
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic

import requests

EMAIL = ADMIN_EMAIL

#########################################################################
# A decorator used to restrict a view to logged in users
# 1. Check is a user is already logged in.
#       If not redirect the user to the login page
#########################################################################
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1.
        if g.user_email is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

#########################################################################
# A decorator used to restrict a view to logged in admins
#########################################################################
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1.
        if g.user_email is None:
            return redirect(url_for('login', next=request.url))
        elif g.user_email != EMAIL:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


###############################################################################
###############################################################################
# The actual views
###############################################################################
###############################################################################

#########################################################################
# The main page.
#   This page is the index page for the logged in user.
#########################################################################
@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html', username=g.username)

#########################################################################
# The home page.
#   This returns the html showing the users account balances
#########################################################################
@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    user_funds = c.get('users', g.user_email)
    funds_details  = {}
    for currency in currency_dict:
        funds_details[currency[1]] = str(user_funds[currency[1]])
    welcome_message = '' if g.username in ['None', None] else g.username
    welcome_message = 'Welcome ' + welcome_message if welcome_message is not '' else ''

    pending_orders_search = c.search('orders', {'user_email' : g.user_email, 'is_complete' : 0})
    pending_orders = [dict(row) for row in pending_orders_search]
    return render_template('home.html', funds_details=funds_details, \
             funds=str(user_funds['funds']), welcome_message=welcome_message, pending_orders=pending_orders)

#########################################################################
# The trade page.
#   This returns the html showing the form to perform trades
#   1. Validate the form.
#   2. Insert the order into the orders table
#   3. Call exchange on that order
#########################################################################
@app.route('/trade', methods=['GET', 'POST'])
@login_required
def trade():
    form = TransactionForm()
    if request.method == 'POST':
    # 1.
        if not form.validate_on_submit():
            flash(u'Invalid input in form')
            return render_template('trade.html', form=form)# User I/P not valid
        # 2.
        order_id   = str(uuid.uuid4())
        action     = action_dict[int(request.form['action'])][1]
        currency   = currency_dict[int(request.form['currency'])][1]
        quantity   = float(request.form['quantity'])
        order_type = order_type_dict[int(request.form['order_type'])][1]
        expiry     = order_expiry_dict[int(request.form['expiry'])][1]
        rate = 0.0

        if order_type == "For Price":
            rate = float(request.form['rate'])

        # Sanity check to see if input is invalid
        if quantity <= 0.0 or ( rate <= 0.0 and order_type == 'For Price'):
            flash(u'Invalid input in form')
            return render_template('trade.html', form=form)# User I/P not valid

        if expiry == 'Good Until Canceled':
            expiry = 0
        elif expiry == 'Fill or Kill':
            expiry = 1
        elif expiry == 'Day Only':
            expiry = int(datetime.now().strftime("%s")) + 86400
       
        try:
            c.put('orders', order_id, {'action' : action, 'currency' : currency, 
                                       'quantity_outstanding' : quantity, 'quantity_fulfilled' : 0.0,
                                       'order_type' : order_type, 'rate' : rate, 'expiry' : expiry, 'is_complete' : 0, 
                                       'user_email' : g.user_email})
            # 3.
            x = c.begin_transaction()
            order_book.process_order(order_id, x)
            x.commit()
            flash(u'Successfully placed order')
        except:
            c.put('orders', order_id, {'is_complete' : 3})
            flash(u'Order Killed')
        
        return redirect(url_for('trade'))

    # This is a new request. Not a POST or validation
    return render_template('trade.html', form=form)

#########################################################################
# The txn log page.
#   This returns html showing completed trades
#########################################################################
@app.route('/log', methods=['GET', 'POST'])
@login_required
def log():
    buy_transactions  = c.search('txns', {'buy_user_email' : g.user_email})
    sell_transactions = c.search('txns', {'sell_user_email' : g.user_email})
    buy_entries  = [dict(row) for row in buy_transactions]
    sell_entries = [dict(row) for row in sell_transactions]
    return render_template('log.html', buy_entries=buy_entries, sell_entries=sell_entries)

#########################################################################
# The order book page.
#   This returns html showing all the users orders
#########################################################################
@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    orders = c.search('orders', {'user_email' : g.user_email})
    entries = [dict(row) for row in orders]
    for entry in entries:
        entry['order_id'] = url_safe_serializer.dumps(entry['order_id'])
    return render_template('book.html', entries=entries)

#########################################################################
# If the user decides to modify a specific order from the order book.
#   This returns html showing html to modify the users order
#########################################################################
@app.route('/delete_or_modify_order', methods=['POST'])
@login_required
def delete_or_modify_order():
    form = ModifyTransactionForm()

    if request.form.has_key('order_id_to_modify'):
        # This is a mew modification request from the View Orders Page
        # 1.1 Initialize the form values
        order_id_to_modify  = url_safe_serializer.loads(request.form['order_id_to_modify'])
        order_to_modify = c.get('orders', order_id_to_modify)
        form = ModifyTransactionForm(order_id = request.form['order_id_to_modify'], action = get_action_id(order_to_modify['action']),
               currency = get_currency_id(order_to_modify['currency']), order_type = get_order_type_id(order_to_modify['order_type']), 
               quantity = order_to_modify['quantity_outstanding'], rate = order_to_modify['rate'], expiry=get_expiry_id(order_to_modify['expiry']))
        form.order_id.data = request.form['order_id_to_modify']
    elif not request.form.has_key('modify_or_delete'):
        flash(u'Order Modification Unsuccessful. Please Try again')
        return redirect(url_for('book'))
    elif request.form['modify_or_delete'] not in ('Modify', 'Delete'):
        flash(u'Order Modification Unsuccessful. Please Try again')
        return redirect(url_for('book'))
    elif request.form['modify_or_delete'] == "Delete":
        order_id_to_delete = url_safe_serializer.loads(request.form['order_id'])
        order_to_delete = c.get('orders', order_id_to_delete)
        if order_to_delete == None:
            flash(u'Order Deletion Unsuccessful. Please Try again')
        else:
            c.put('orders', order_id_to_delete, {'is_complete' : 2})
            flash(u'Order Deletion Successful')
        return redirect(url_for('book'))
    elif request.form.has_key('order_id'):
        order_id_to_modify = url_safe_serializer.loads(request.form['order_id'])
        order_to_modify = c.get('orders', order_id_to_modify)
        # This is a request to modify the order.
        # 2.1 Validate the form.
        if order_to_modify == None:
            flash(u'Order Modification Unsuccessful. Please Try again')
            return redirect(url_for('book'))
        if not form.validate_on_submit():
            flash(u'Invalid input in form')
            return render_template('modify_order.html', form=form)# User I/P not valid
        # 2.2 Its a valid form redirect make the modification if possible

        order_id   = order_id_to_modify
        quantity   = float(request.form['quantity'])
        order_type = order_type_dict[int(request.form['order_type'])][1]
        expiry     = order_expiry_dict[int(request.form['expiry'])][1]
        rate = 0.0

        if order_type == "For price":
            rate = float(request.form['rate'])

        # Sanity check to see if input is invalid
        if quantity <= 0.0 or ( rate <= 0.0 and order_type == 'For Price'):
            flash(u'Invalid input in form')
            return render_template('modify_order.html', form=form)# User I/P not valid

        if expiry == 'Good Until Canceled':
            expiry = 0
        elif expiry == 'Fill or Kill':
            expiry = 1
        elif expiry == 'Day Only':
            expiry = int(datetime.now().strftime("%s")) + 86400
        
        try:
            c.put('orders', order_id_to_modify, {'quantity_outstanding' : quantity, 'rate' : rate, 'order_type' : order_type, 'expiry' : expiry})
            x = c.begin_transaction()
            order_book.process_order(order_id, x)
            x.commit()
            flash(u'Successfully modified order')
        except:
            c.put('orders', order_id_to_modify, {'is_complete' : 3})
            flash(u'Order Killed')
        
        return redirect(url_for('book'))
    else:
        # This should not happen. A request to this method must always have a valid order_id.
        # This request may be malicious. Redirect to Home page
        return redirect(url_for('index'))

    return render_template('modify_order.html', form=form)

#########################################################################
# The manage funds page.
#   This returns html form that can add/withdrw funds from the users account
#   TODO : Actually perform this transation using bitcoins
#########################################################################
@app.route('/funds', methods=['GET', 'POST'])
@login_required
def funds():
    form = AddFundsForm()
    if request.method == 'POST':
        # 1.
        if not form.validate_on_submit():
            flash(u'Invalid input')
            return render_template('add_funds.html', form=form)
        # form is validated now process add funds
        
        added_funds = float(request.form['funds'])
        bitcoins    = float(request.form['Bitcoin'])
        dogecoins   = float(request.form['Dogecoin'])
        c.atomic_add('users', g.user_email, {'Bitcoin' : bitcoins, 'Dogecoin' : dogecoins, 'funds' : added_funds})
        # 3.
        # When a user adds funds we need to reprocess his orders as there may
        # be some orders he has placed that were not executed due to
        # insufficient resources.

        # No transaction support for the search() function yet :(
        pending_orders = c.search('orders', {'user_email' : g.user_email, 'is_complete' : 0})
        x = c.begin_transaction()
        for order in pending_orders:
            order_book.process_order(order['order_id'], x)

        x.commit()
        # 4.
        flash(u'Added funds successfully')
        return redirect(url_for('funds'))
    # 5.
    return render_template('add_funds.html', form=form)

###########################################################
# Manage bitcoin
# On page load check if the user has a public bitcoin address,
# If not fetch one from HyperDex and assign it to the user.
# If HyperDex has no more public addresses, report to user and admin
#
# Display the current balance and unconfirmed balance, 
# a QR code and address to receive bitcoins
# A form to send money that accepts an address and amount to send
###########################################################
@app.route('/bitcoin', methods=['POST', 'GET']) 
@login_required
def manage_bitcoin():
    x = c.begin_transaction()
    user_data = x.get('users', g.user_email)
    pub_key = user_data['bitcoin_address']

    form = SendBitcoinForm()

    if request.method == 'POST':
        if not form.validate_on_submit():
            flash(u'Invalid Input')
        else:
            input_address = str(request.form['address']).strip()
            try:
                addr = CBitcoinAddress(input_address)
                amount = float(request.form['amount'])
                if amount == 0.0: raise
                user_balance = x.get('users', g.user_email)['Bitcoin']
                if amount > user_balance:
                    flash('Insufficient Funds')
                else:
                    x.put('bitcoin_txns', datetime.now(), {'pub_key': input_address, 'amount': amount, 'txid': '', 'email': g.user_email})
                    #x.put('users', g.user_email, {'Bitcoin': (user_balance - amount)})
                    x.atomic_sub('users', g.user_email, {'Bitcoin': amount})
                    flash(u'Your transaction for %s to %s is pending' % (amount, input_address))
            except Exception as inst:
                print inst
                error_string = "Couldn't process send. "
                if type(inst) == bitcoin.base58.Base58ChecksumError:
                    error_string += "Invalid Address!"
                elif type(inst) == bitcoin.rpc.JSONRPCException:
                    error_string += "Insufficient Funds!"
                flash(u'%s' % (error_string))

    if user_data['bitcoin_address'] == '': 
        return "<div class='code'>We are still assigning you an address.<br/> Contact support@f13xchange.com if you continue to see this.</div>"

    # Fetch UTXO for the user's address
    confirmed = c.get('users', g.user_email)['Bitcoin']
    pending = 0.0
    addr = []
    addr.append(pub_key)
    txns = rpc.listunspent(addrs=addr)
    for txn in txns:
        pending += float(txn['amount'])/COIN


    # Fetch transactions
    all_transactions = c.search('bitcoin_txns', {'email': g.user_email})
    txns  = [dict(row) for row in all_transactions]

    x.commit()
    return render_template('bitcoin.html', pub_key=pub_key, confirmed="%0.8f" % (confirmed), pending="%0.8f" % (pending), txns=txns, form=form)

###########################################################
# Manage dogecoin
# On page load check if the user has a public dogecoin address,
# If not fetch one from HyperDex and assign it to the user.
# If HyperDex has no more public addresses, report to user and admin
#
# Display the current balance and unconfirmed balance, 
# a QR code and address to receive dogecoins
# A form to send money that accepts an address and amount to send
###########################################################
@app.route('/dogecoin', methods=['POST', 'GET']) 
@login_required
def manage_dogecoin():
    x = c.begin_transaction()
    user_data = x.get('users', g.user_email)
    pub_key = user_data['dogecoin_address']

    form = SendDogecoinForm()

    if request.method == 'POST':
        if not form.validate_on_submit():
            flash(u'Invalid Input')
        else:
            input_address = str(request.form['address']).strip()
            try:
                addr = CDogecoinAddress(input_address)
                amount = float(request.form['amount'])
                if amount == 0.0: raise
                user_balance = x.get('users', g.user_email)['Dogecoin']
                if amount > user_balance:
                    flash('Insufficient Funds')
                else:
                    x.put('dogecoin_txns', datetime.now(), {'pub_key': input_address, 'amount': amount, 'txid': '', 'email': g.user_email})
                    #x.put('users', g.user_email, {'Dogecoin': (user_balance - amount)})
                    x.atomic_sub('users', g.user_email, {'Dogecoin': amount})
                    flash(u'Your transaction for %s to %s is pending' % (amount, input_address))
            except Exception as inst:
                print inst
                error_string = "Couldn't process send. "
                if type(inst) == dogecoin.base58.Base58ChecksumError:
                    error_string += "Invalid Address!"
                elif type(inst) == dogecoin.rpc.JSONRPCException:
                    error_string += "Insufficient Funds!"
                flash(u'%s' % (error_string))

    if user_data['bitcoin_address'] == '': 
        return "<div class='code'>We are still assigning you an address.<br/> Contact support@f13xchange.com if you continue to see this.</div>"

    # Fetch UTXO for the user's address
    confirmed = c.get('users', g.user_email)['Dogecoin']
    pending = 0.0

    addrs=pub_key
    response = requests.get('https://chain.so/api/v2/get_tx_unspent/DOGETEST/' + addrs)

    if response.status_code != 200:
        return "We're facing issues with our Dogecoin API, please try again in a bit. :("

    content = response.json()
    txns = content['data']['txs']

    for txn in txns:
        pending += float(str(txn['value']))

    # Fetch transactions
    all_transactions = c.search('dogecoin_txns', {'email': g.user_email})
    txns  = [dict(row) for row in all_transactions]

    x.commit()
    return render_template('dogecoin.html', pub_key=pub_key, confirmed="%0.8f" % (confirmed), pending="%0.8f" % (pending), txns=txns, form=form)

#########################################################################
# This is a helper function for the analyze function below. 
# This returns the actual chart as and when the user asks for it
#########################################################################
def get_chart_data(currency, chart_type):
    if chart_type == "Order Book":
        # we need to return a data dict with keys buy and sell.
        # The value must be a list of lists that holds the first column as rate
        #   2nd and 3rd column are from and to ranges for that rate
            # Query the DB to fetch the rates and quantities
        buy_order_search  = c.sorted_search('orders', {'currency' : currency, 'action' : 'Buy',  'is_complete' : 0, 'order_type' : 'For Price'}, 'rate', 100, 'max')
        sell_order_search = c.sorted_search('orders', {'currency' : currency, 'action' : 'Sell', 'is_complete' : 0, 'order_type' : 'For Price'}, 'rate', 100, 'min')
            # Create a list of cumulative_quantity
        i = 0
        data = {}
        data['Buy']  = []
        data['Sell'] = []
        for order in buy_order_search:
            data['Buy'].append([order['rate'], i, i+order['quantity_outstanding']])
            i = i + order['quantity_outstanding']
        i = 0
        for order in sell_order_search:
            data['Sell'].append([order['rate'], i, i+order['quantity_outstanding']])
            i = i + order['quantity_outstanding']
        return render_template('buy_sell_chart.html', currency=currency, data_series=data)
    elif chart_type == "Candle Stick":
        # we need to return a data dict of dicts
        # http://www.highcharts.com/samples/data/jsonp.php?a=e&filename=aapl-ohlc.json&callback=?
        # Each row muct be [epoch, open, high, low, close ]
        search = c.sorted_search('txns', {'currency' : currency}, 'time_stamp', 100, 'min')
        data = {}
        data['Buy'] = []
        data['Sell'] = []
        buy_aggregation  = {}
        sell_aggregation = {}
        for result in search:
            timestamp = int(result['time_stamp'])*1000/3600
            if not buy_aggregation.has_key(timestamp):
                buy_aggregation[timestamp] = {}
                buy_aggregation[timestamp]['open']  = result['buy_rate']
                buy_aggregation[timestamp]['high']  = result['buy_rate']
                buy_aggregation[timestamp]['low']   = result['buy_rate']
                buy_aggregation[timestamp]['close'] = result['buy_rate']
                buy_aggregation[timestamp]['open_time']  = int(result['time_stamp'])*1000
                buy_aggregation[timestamp]['close_time'] = int(result['time_stamp'])*1000
            else:
                buy_aggregation[timestamp]['open']  = buy_aggregation[timestamp]['open'] if buy_aggregation[timestamp]['open_time'] < int(result['time_stamp'])*1000 else result['buy_rate']
                buy_aggregation[timestamp]['close'] = buy_aggregation[timestamp]['close'] if buy_aggregation[timestamp]['close_time'] > int(result['time_stamp'])*1000 else result['buy_rate']
                buy_aggregation[timestamp]['low'] = buy_aggregation[timestamp]['low'] if buy_aggregation[timestamp]['low'] < result['buy_rate'] else result['buy_rate']
                buy_aggregation[timestamp]['high'] = buy_aggregation[timestamp]['high'] if buy_aggregation[timestamp]['high'] > result['buy_rate'] else result['buy_rate']
                buy_aggregation[timestamp]['open_time'] = buy_aggregation[timestamp]['open_time'] if buy_aggregation[timestamp]['open_time'] < int(result['time_stamp'])*1000 else int(result['time_stamp'])*1000
                buy_aggregation[timestamp]['close_time'] = buy_aggregation[timestamp]['close_time'] if buy_aggregation[timestamp]['close_time'] > int(result['time_stamp'])*1000 else int(result['time_stamp'])*1000

            if not sell_aggregation.has_key(timestamp):
                sell_aggregation[timestamp] = {}
                sell_aggregation[timestamp]['open']  = result['sell_rate']
                sell_aggregation[timestamp]['high']  = result['sell_rate']
                sell_aggregation[timestamp]['low']   = result['sell_rate']
                sell_aggregation[timestamp]['close'] = result['sell_rate']
                sell_aggregation[timestamp]['open_time']  = int(result['time_stamp'])*1000
                sell_aggregation[timestamp]['close_time'] = int(result['time_stamp'])*1000
            else:
                sell_aggregation[timestamp]['open']  = sell_aggregation[timestamp]['open'] if sell_aggregation[timestamp]['open_time'] < int(result['time_stamp'])*1000 else result['sell_rate']
                sell_aggregation[timestamp]['close'] = sell_aggregation[timestamp]['close'] if sell_aggregation[timestamp]['close_time'] > int(result['time_stamp'])*1000 else result['sell_rate']
                sell_aggregation[timestamp]['low'] = sell_aggregation[timestamp]['low'] if sell_aggregation[timestamp]['low'] < result['sell_rate'] else result['sell_rate']
                sell_aggregation[timestamp]['high'] = sell_aggregation[timestamp]['high'] if sell_aggregation[timestamp]['high'] > result['sell_rate'] else result['sell_rate']
                sell_aggregation[timestamp]['open_time'] = sell_aggregation[timestamp]['open_time'] if sell_aggregation[timestamp]['open_time'] < int(result['time_stamp'])*1000 else int(result['time_stamp'])*1000
                sell_aggregation[timestamp]['close_time'] = sell_aggregation[timestamp]['close_time'] if sell_aggregation[timestamp]['close_time'] > int(result['time_stamp'])*1000 else int(result['time_stamp'])*1000

        for time in buy_aggregation:
            data['Buy'].append([time*3600, buy_aggregation[time]['open'], buy_aggregation[time]['high'], buy_aggregation[time]['low'], buy_aggregation[time]['close']])
        for time in sell_aggregation:
            data['Sell'].append([time*3600, sell_aggregation[time]['open'], sell_aggregation[time]['high'], sell_aggregation[time]['low'], sell_aggregation[time]['close']])
        return render_template('candle_stick_chart.html', currency=currency, data_series=data)
    elif chart_type == "Price History":
        # we need to return a data dict of dicts
        # http://www.highcharts.com/samples/data/jsonp.php?filename=aapl-v.json&callback=?
        # Each row muct be an [epoch, price]
        search = c.sorted_search('txns', {'currency' : currency}, 'time_stamp', 100, 'min')
        data = {}
        data['Buy'] = []
        data['Sell'] = []
        for result in search:
            data['Buy'].append([int(result['time_stamp'])*1000,  result['buy_rate']])
            data['Sell'].append([int(result['time_stamp'])*1000, result['sell_rate']])
        return render_template('price_time_chart.html', currency=currency, data_series=data)
    else:
        return ""

#########################################################################
# The analyze markets page.
#   This returns html that plots charts of the required type
#########################################################################
@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    form = ChartsForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            return render_template('analyze.html', form=form)
        chart_type = chart_dict[int(request.form['chart_type'])][1]
        currency   = currency_dict[int(request.form['currency'])][1]
        return get_chart_data(currency, chart_type)
    return render_template('analyze.html', form=form)

@app.route('/analyze1', methods=['GET', 'POST'])
def analyze1():
    return get_chart_data("Bitcoin", "Candle Stick")

#########################################################################
# The help page.
#   This returns html showing helpful tips
#########################################################################
@app.route('/help', methods=['GET', 'POST'])
@login_required
def help():
    return '''
    <h4> Welcome to f13x cryptocurrency exchange. </h4>
    <div> 
      <table class="table table-responsive">
        <tr><td><b>Home &nbsp</b></td><td> to view your current balance.</td></tr>
        <tr><td><b>Trade &nbsp</b></td><td> to trade some cryptocurrencies.</td></tr>
        <tr><td><b>View Transaction Log &nbsp</b></td><td> to view your previous orders which are completed or cancelled.</td></tr>
        <tr><td><b>Order Book &nbsp</b></td><td> to view your active orders.</td></tr>
        <tr><td><b>Analyze Markets &nbsp</b></td><td> to visualize current market rates.</td></tr>
        <tr><td><b>Manage Funds &nbsp</b></td><td> to add / withdraw funds.</td></tr>
        <tr><td><b>Help &nbsp</b></td><td> to see this menu.</td></tr>
      </table>
    </div>
    '''
#########################################################################
# The profile page.
#   This returns html showing A form to edit profile
#########################################################################
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(name=g.username)
    if request.method == 'POST':
        if not form.validate_on_submit():
            return render_template('profile.html', form=form, email=g.user_email, name=g.username)
        # form is validated now process add funds
        
        name = request.form['name']
        name = unicodedata.normalize('NFKD', name).encode('ascii','ignore')
        c.put('users', g.user_email, {'name' : name})
        return redirect(url_for('index'))
    return render_template('profile.html', form=form, email=g.user_email, name=g.username)


###############################################################################
###############################################################################
# Error handlers
###############################################################################
###############################################################################
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

###############################################################################
###############################################################################
# Login handlers
###############################################################################
###############################################################################

###########################################################
# This login procedure Authenticates users email
# This is from a sample from
# http://peterhudec.github.io/authomatic/
# The authomatic libraray is really wonderful.
###########################################################
@app.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login_pr(provider_name):
    # We need response object for the WerkzeugAdapter.
    response = make_response()

    # Log the user in, pass it the adapter and the provider name.
    result = authomatic.login(WerkzeugAdapter(request, response), provider_name)

    # If there is no LoginResult object, the login procedure is still pending.
    authenticated_email = None
    if result:
        if result.user:
            # We need to update the user to get more info.
            result.user.update()
            return login_or_signup_user(result.user.email, result.user.name)
    
    # Don't forget to return the response.
    return response

###########################################################
# Loads the users login cookie and sets the user_email variable
###########################################################
@app.before_request
def lookup_current_user():
    g.user_email = None
    g.username   = None
    if 'openid' in session:
        try:
            openid = str(session['openid'])
            if c.count('users', { 'email' : openid}) == 1:
                g.user_email = openid
                g.username   = c.get('users', openid)['name']
        except:
            g.user_email = None
            g.username   = None

###########################################################
#This code will be called by the openID after a login attempt.
#We have to either login the user or Create a new user account.
# 1. Check if the login was successful & emailId was provided by the OpenID provider
# 2. Check if the user already exists.
# 3. If this is a regular login.
# 3.1    If the user does not exist redirect to signup page
# 4. If this is a new signup.
# 4.1 If this user already exists redirect to login page
# 4.2 VALID SIGNUP : Create new user
# 5. Create new session cookie for the user.
# 6. Redirect the user to an appropriate page
###########################################################
def login_or_signup_user(email, name):
    # 0. Convert email and name normal non unicode characters.
    email = unicodedata.normalize('NFKD', email).encode('ascii','ignore')
    name  = unicodedata.normalize('NFKD', name ).encode('ascii','ignore')
    
    # 1.
    if str(email) == None or str(email) == "":
        return redirect(url_for('login'))
    # 2.
    user_exists = False
    if c.count('users', { 'email' : str(email) }) == 1L:
        user_exists = True
        
    # 4.1
    if user_exists:
        session['openid'] = str(email)
    else:
        c.put('users', str(email), {'name' : str(name), 'funds' : 0.0, 'Bitcoin' : 0.0, 'Dogecoin' : 0.0 })
        # Send email about new user signup
        msg = Message("New User", sender=EMAIL, recipients=[EMAIL])
        msg.body = "New User %s:" % email
        mail.send(msg)
        session['openid'] = str(email)
        g.user_email = str(email)
        g.username = str(name)
    return redirect(request.args.get('next') or url_for('index'))

###########################################################
# Login a new user.
# 1. Check if a user is already logged in.
# 2. Display the login form
###########################################################
@app.route('/login', methods=['POST', 'GET'])
def login():
    # 1.
    if g.user_email is not None:
        return redirect(url_for('index'))
    # 2.
    return render_template('login.html', title='f13x : Log In')

###########################################################

@app.route('/logout')
@login_required
def logout():
    # logout a signed in user. Delete his cookie
    session.pop('openid', None)
    #flash(u'You were signed out')
    return redirect(url_for('index'))


###########################################################
###########################################################
# ADMIN PAGES
###########################################################
###########################################################

@app.route('/admin', methods=['GET', 'POST'])
@admin_login_required
def admin_main():
    return render_template('admin_index.html', username=g.username)

@app.route('/admin/home', methods=['GET', 'POST'])
@admin_login_required
def admin_home():
    exchange = c.get('users', 'exchange')
    num_users = c.count('users', {})

    txns_search = c.sorted_search('txns', {}, 'time_stamp', 100, 'min')
    txns        = [dict(row) for row in txns_search]
    
    orders_search = c.sorted_search('orders', {'is_complete' : 0}, 'rate', 100, 'max')
    orders        = [dict(row) for row in orders_search]

    return render_template('admin_home.html', bitcoins=exchange['Bitcoin'], dogecoins=exchange['Dogecoin'], num_users = num_users, txns=txns, orders=orders)

@app.route('/admin/user', methods=['GET', 'POST'])
@admin_login_required
def admin_user():
    users = c.search('users', {})
    user_emails = []
    i = 0
    for user in users:
        user_emails.append((str(i), user['email']))
        i = i + 1
    
    form = AdminUserForm()
    form.email.choices = user_emails
    return render_template('admin_user.html', form=form)

@app.route('/admin_delete_user', methods=['GET', 'POST'])
@admin_login_required
def admin_delete_user():
    users = c.search('users', {})
    user_emails = []
    i = 0
    for user in users:
        user_emails.append((str(i), user['email']))
        i = i + 1
    
    form = AdminUserForm()
    if request.method == 'POST':
        email_id = request.form['email']
        email_id = user_emails[int(email_id)][1]
        c.delete('users', email_id)
        flash(u'User ' + email_id + ' deleted')

    return redirect(url_for('admin_user'))

@app.route('/admin/user_manager', methods=['GET', 'POST'])
@admin_login_required
def admin_user_manager():
    users = c.search('users', {})
    user_emails = []
    i = 0
    for user in users:
        user_emails.append((str(i), user['email']))
        i = i + 1

    if 'email' in request.form:
        email_id = request.form['email']
        if email_id.isdigit():
            email_id = user_emails[int(request.form['email'])][1]

    form = AdminUserManageForm()
    if request.method == 'POST':
        if not form.validate_on_submit():
            user_details = c.get('users', str(email_id))
            form = AdminUserManageForm(email=str(email_id), name=str(user_details['name']), Bitcoin=user_details['Bitcoin'], Dogecoin=user_details['Dogecoin'], funds=user_details['funds'])
            form.email.data = str(email_id)
            form.name.data  = str(user_details['name'])
            form.bitcoin_address.data = str(user_details['bitcoin_address'])
            form.dogecoin_address.data = str(user_details['dogecoin_address'])
            return render_template('admin_user_manage.html', form=form)

        added_funds = float(request.form['funds'])
        bitcoins    = float(request.form['Bitcoin'])
        dogecoins   = float(request.form['Dogecoin'])
        name        = request.form['name']
        name        = unicodedata.normalize('NFKD', name).encode('ascii','ignore')

        c.atomic_add('users', str(email_id), {'Bitcoin' : bitcoins, 'Dogecoin' : dogecoins, 'funds' : added_funds})
        c.put('users', str(email_id), {'name' : str(name)})
        flash(u'Edited details successfully')
    
    return render_template('admin_user_manage.html', form=form)

@app.route('/admin/process_orders', methods=['GET', 'POST'])
def process_orders():
    users = c.search('users', {})
    user_emails = []
    for user in users:
        user_emails.append(user['email'])

    for user_email in user_emails:
        x = c.begin_transaction()
        pending_orders = c.search('orders', {'user_email' : user_email, 'is_complete' : 0})
        for order in pending_orders:
            order_book.process_order(order['order_id'], x)
        x.commit()

    flash(u'Finished reprocessing orders')
    return redirect(url_for('admin_home'))
