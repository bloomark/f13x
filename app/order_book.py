from hyperdex.client import LessEqual, GreaterEqual
from app import c
from datetime import datetime
import uuid
import copy
import time

########################################################################
# SETTING
EXCHANGE_RATE_PER_TRANSACTION = 0.001
EXCHANGE_BRIDGES_BUY_SELL_GAP = 1
########################################################################


#########################################################################
# Helper function to get order from order book
#########################################################################
def get_order_by_id(order_id, c):
    order = c.get('orders', order_id)
    order['order_id'] = order_id
    return order

#########################################################################
# This function gives orders from the book which are incomplete, 
# same currency. Different Action(Buy/Sell). 
# Order Type and Rate will meet the following criteria
# a). If Order is Rate-Sell
#       If the current orders sell rate is lowest_sell_rate
#           Return Market Buy orders
#       Return Rate Buy orders which are gte orders rate
# b). If Order is Rate-Buy
#       If the current orders buy rate is highest_buy_rate
#           Return Market Sell orders
#       Return Rate Sell orders which are lte orders rate
# c). If Order is Market-Sell
#       Return Rate Buy orders
#       Return Market Buy orders
# d). If Order is Market-Buy
#       Return Rate Sell orders
#       Return Market Sell orders
#########################################################################
def get_matching_orders(input_order):
    #  Same currency. Different Action (Buy/Sell)
    search_criteria_rate = {'currency' : input_order['currency']}
    search_criteria_rate['action'] = "Buy" if input_order['action'] == "Sell" else "Sell"
    search_criteria_rate['is_complete'] = 0
    search_criteria_market = copy.deepcopy(search_criteria_rate)
    search_criteria_rate['order_type'] = "For Price"
    search_criteria_market['order_type'] = "At Market"

    query_market = True
    quote   = c.get('currencies', input_order['currency'])
    rate    = input_order['rate']
    
    is_sell = input_order['action'] == "Sell"
    is_rate = input_order['order_type'] == "For Price"

    if not is_rate and quote['last_trade'] == -1:
        query_market = False

    if is_rate:
        search_criteria_rate['rate'] = GreaterEqual(rate) if is_sell else LessEqual(rate)
        if is_sell and rate > quote['lowest_sell_rate'] : query_market = False
        if not is_sell and rate < quote['highest_buy_rate'] : query_market = False
    else:
        # If it is a market order do not query the market_orders
        query_market = False

    # Get the search iterator over rate and market orders
    market_orders_itr = c.search('orders', search_criteria_market) if query_market else None
    rate_orders_itr   = c.search('orders', search_criteria_rate)
    # Fetch the actual records into memory
    market_orders     = [dict(row) for row in market_orders_itr] if market_orders_itr is not None else []
    rate_orders       = [dict(row) for row in rate_orders_itr]
    return (rate_orders, market_orders, quote)


#########################################################################
# This function matches orders order1 and order2.
# 0. Check if the order to be matched with is expired
# 1. Swap order1 and order2 such that order1 is Buy and order2 is Sell
# 2. compute the quantity of the shares that are to be exchanged.
# 2.1   Calculate the buy_rate and sell_rate
# 2.2   Calculate buy quantity, and sell quantity
# 2.3   Bridge excessive gap between buy and sell rate
# 3  Calculate the quantity of currency to be exchanged.
#    If transaction is not viable return
# 4. Make the trade. The exchange pockets the difference between the rates.
# 4.1 Transfer cryptocurrency from, and the currencies table sell order to buy order
# 4.2 Transfer money from buy order and to sell order
# 4.3 Add pocketed cryptocurrency to exchange account
# 4.4 Modify the orders
# 4.5 Check and set if an order is completed
# 4.6 Modify the currencies table
# 4.7 Create an entry in txns to record this txn
#########################################################################
def match_orders(buy_order, sell_order, quote, c):
    # 0.
    # Buy_order is an existing order from the book.
    if buy_order['expiry'] not in [0, 1] and buy_order['expiry'] <= int(datetime.now().strftime("%s")):
        # Order has expired
        c.put('orders', buy_order['order_id'], {'is_complete' : 3})
        return False
    # 1.
    if buy_order['action'] == "Sell":
        (buy_order, sell_order) = (sell_order, buy_order)
    # 2.
    buy_is_rate  = buy_order['order_type'] == "For Price"
    sell_is_rate = sell_order['order_type'] == "For Price"
     
    # 2.1
    buy_rate     = buy_order['rate'] if buy_is_rate else sell_order['rate']
    sell_rate    = sell_order['rate'] if sell_is_rate else buy_order['rate']
    # Both are market orders.
    if not buy_is_rate and not sell_is_rate : buy_rate = sell_rate = quote['last_trade']

    # 2.2
    buy_quantity  = sell_quantity = 0.0
    if not buy_is_rate and buy_rate <= 0.0: return False
    if not sell_is_rate and sell_rate <= 0.0: return False
    
    # 2.3
    if EXCHANGE_BRIDGES_BUY_SELL_GAP == 1:
        if buy_is_rate and sell_is_rate and buy_rate > sell_rate:
            avg_rate = (buy_rate + sell_rate)/2
            buy_rate = sell_rate = avg_rate
  
    buy_rate = buy_rate + EXCHANGE_RATE_PER_TRANSACTION
    sell_rate = max(0.0, sell_rate - EXCHANGE_RATE_PER_TRANSACTION)

    buy_quantity  = min(c.get('users', buy_order['user_email'])['Bitcoin']/buy_rate, buy_order['quantity_outstanding'])
    sell_quantity = min(c.get('users', sell_order['user_email'])[sell_order['currency']], sell_order['quantity_outstanding'])

    # 3.
    quantity = min(buy_quantity, sell_quantity)
    if quantity == 0: return False
   
    # 4.
    rate_diff = abs(buy_rate - sell_rate)
    # 4.1
    c.atomic_add('users', buy_order['user_email'],  {buy_order['currency']:  quantity})
    c.atomic_sub('users', sell_order['user_email'], {sell_order['currency']: quantity})
    # 4.2
    c.atomic_sub('users', buy_order['user_email'],  {'Bitcoin': quantity*buy_rate})
    c.atomic_add('users', sell_order['user_email'], {'Bitcoin': quantity*sell_rate})
    # 4.3
    if rate_diff != 0.0: c.atomic_add('users', 'exchange', {'Bitcoin': quantity*rate_diff})
    # 4.4
    c.atomic_sub('orders', buy_order['order_id'],   {'quantity_outstanding': quantity})
    c.atomic_sub('orders', sell_order['order_id'],  {'quantity_outstanding': quantity})
    c.atomic_add('orders', buy_order['order_id'],   {'quantity_fulfilled': quantity})
    c.atomic_add('orders', sell_order['order_id'],  {'quantity_fulfilled': quantity})
    # 4.5
    if buy_order['quantity_outstanding']  == quantity : c.put('orders', buy_order['order_id'],  {'is_complete': 1})
    if sell_order['quantity_outstanding'] == quantity : c.put('orders', sell_order['order_id'], {'is_complete': 1})
    # 4.6
    rate_to_set = max(buy_rate, sell_rate)
    if sell_rate < quote['lowest_sell_rate']:
        c.put('currencies', sell_order['currency'], {'lowest_sell_rate': sell_rate})
        rate_to_set = sell_rate
    if buy_rate > quote['highest_buy_rate']:
        c.put('currencies', buy_order['currency'], {'highest_buy_rate': buy_rate})
        rate_to_set = buy_rate
    c.put('currencies', buy_order['currency'], {'last_trade': rate_to_set})
    # 4.7
    txn_id = str(uuid.uuid4())
    c.put('txns', txn_id, {'buy_order_id' : buy_order['order_id'], 'sell_order_id' : sell_order['order_id'], \
          'buy_user_email' : buy_order['user_email'], 'sell_user_email' : sell_order['user_email'], \
          'buy_order_type' : buy_order['order_type'], 'sell_order_type' : sell_order['order_type'], \
          'buy_rate' : buy_rate, 'sell_rate' : sell_rate, \
          'quantity' : quantity, 'currency' : buy_order['currency'], \
          'pocketed' : quantity*rate_diff, 'time_stamp' : int(time.time())})

#########################################################################
# This function is called when the user enters a new order.
# We have to match this order against the existing orders in the book.
# 1. Load the given order
# 2. Load all matching orders from the book
# 3. Call exchange on that order
#########################################################################
def process_order(order_id, x):
    # 1.
    input_order = get_order_by_id(order_id, x)
    currency = input_order['currency']
    # 2.
    (rate_orders, market_orders, quote) = get_matching_orders(input_order)
    # 3.
    for rate_order_from_book in rate_orders:
        match_orders(rate_order_from_book, get_order_by_id(order_id, x), c.get('currencies', currency), x)
    for market_order_from_book in market_orders:
        match_orders(market_order_from_book, get_order_by_id(order_id, x), c.get('currencies', currency), x)
    input_order = get_order_by_id(order_id, x)
    if input_order['quantity_outstanding']  == 0.0 and input_order['expiry'] == 1:
        # This was a Fill or Kill order and it was not filled. Cancel this order
        x.abort()

