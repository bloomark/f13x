#!/usr/bin/python
import os
import traceback
import unittest
import hyperdex.admin
import hyperdex.client
from datetime import datetime

a = hyperdex.admin.Admin('127.0.0.1', 1982)
c = hyperdex.client.Client('127.0.0.1', 1982)

from config import basedir
from app import app
from app.forms import *
from app.order_book import *
from db_create import create_or_replace_db
from delete_rows import delete_rows, delete_users, reset_currencies

def to_objectset(xs):
    return set([frozenset(x.items()) for x in xs])

def assertEquals(actual, expected):
    if not actual == expected:
        print "AssertEquals failed"
        print "Should be: " + str(expected) + ", but was " + str(actual) + "."

        assert False

def assertTrue(val):
    if not val:
        print "AssertTrue failed"
        assert False

def assertFalse(val):
    if val:
        print "AssertFalse failed"
        assert False

def assert_book(test_input):
    book = view_book()
    book_values = []
    test_values = []
    for entry in book:
        entry.pop('order_id')
        book_values.append(frozenset(entry.values()))
    for entry in test_input:
        test_values.append(frozenset(entry))
    assert hash(frozenset(book_values)) == hash(frozenset(test_values))

def assert_txns(test_input):
    txns = view_log()
    txns_values = []
    test_values = []
    for entry in txns:
        entry.pop('buy_order_id')
        entry.pop('sell_order_id')
        entry.pop('txn_id')
        entry.pop('time_stamp')
        txns_values.append(frozenset(entry.values()))
    for entry in test_input:
        test_values.append(frozenset(entry))
    assert hash(frozenset(txns_values)) == hash(frozenset(test_values))

def exchange(user_email, action, currency, quantity, order_type, expiry, rate=0):
    order_id   = str(uuid.uuid4())
    if order_type == "For Price":
        rate = float(rate)

    if quantity <= 0.0 or ( rate <= 0.0 and order_type == 'For Price'):
        assert False
    
    if expiry == 'Good Until Canceled':
        expiry = 0
    elif expiry == 'Fill or Kill':
        expiry = 1
    elif expiry == 'Day Only':
        expiry = int(datetime.now().strftime("%s")) + 86400

    c.put('orders', order_id, {'action' : action, 'currency' : currency, 
                               'quantity_outstanding' : quantity, 'quantity_fulfilled' : 0.0,
                               'order_type' : order_type, 'rate' : rate, 'expiry' : expiry, 'is_complete' : 0, 
                               'user_email' : user_email})
    x = c.begin_transaction()
    process_order(order_id, x)
    x.commit()

def add_funds(user, bitcoins, dogecoins, added_funds):
    c.atomic_add('users', user['email'], {'Bitcoin' : bitcoins, 'Dogecoin' : dogecoins, 'funds' : added_funds})
    pending_orders = c.search('orders', {'user_email' : user['email'], 'is_complete' : 0})
    x = c.begin_transaction()
    for order in pending_orders:
        process_order(order['order_id'], x)
    x.commit()

def add_user(email, name, bitcoins=0, dogecoins=0, funds=0):
    c.put('users', email, {'name' : name, 'funds' : float(funds), 'Bitcoin' : float(bitcoins), 'Dogecoin' : float(dogecoins)})

def view_book():
    book = c.search('orders', {})
    return [dict(row) for row in book]

def view_log():
    log = c.search('txns', {})
    return [dict(row) for row in log]

def view_users():
    users = c.search('users', {})
    return [dict(row) for row in users]

context = None
class TestCase(unittest.TestCase):

    def setUp(self):
        delete_rows()

    def tearDown(self):
        delete_rows()
        delete_users()
        
    #@unittest.skip("demonstrating skipping")
    def test_empty_db(self):
        ''' Tests Empty Database '''
        print ""; print "Testing Empty DB"
        try:
            default_users_table = [{'Dogecoin': 0.0, 'name': 'exchange', 'funds': 0.0, 'Bitcoin': 0.0, 'email': 'exchange'}]
            assert [] == view_log()
            assert [] == view_book()
            #assert view_users() == default_users_table
        except:
            print "Empty DB test failed"
        else:
            print "Empty DB Test passed"

 
    #@unittest.skip("demonstrating skipping")
    def test_adding_rate_buy_orders_to_book(self):
        ''' Adding a Rate-Buy order for Bitcoin then Dogecoin then both'''
        print ""; print "Adding Rate-Buy orders"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            exchange('test@example.com', 'Buy', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 1)
            table_with_test_user = [{'Dogecoin': 0.0, 'name': 'exchange', 'funds': 0.0, 'Bitcoin': 0.0, 'email': 'exchange', 'bitcoin_address': 'mgsriptmbJhzNcgqDBiBLmgFMbJFZbfJkY', 'dogecoin_address': ''}, {'Dogecoin': 10.0, 'name': 'test_user', 'funds': 10.0, 'Bitcoin': 10.0, 'email': 'test@example.com', 'bitcoin_address': 'mgsriptmbJhzNcgqDBiBLmgFMbJFZbfJkY', 'dogecoin_address': 'nfzF6rTxSpXLLHJHurXWz9Zuo66aB7Rmt3'}]
            assert view_log() == []
            assert view_users() == table_with_test_user
            assert_book([['test@example.com', 'Buy', 'Bitcoin', 10.0, 0.0, 'For Price', 1, 1.0, 0]])
            exchange('test@example.com', 'Buy', 'Dogecoin', 10, 'For Price', 'Good Until Canceled', 1)
            assert_book([['test@example.com', 'Buy', 'Bitcoin', 10.0, 0.0, 'For Price', 1, 1.0, 0], 
                         ['test@example.com', 'Buy', 'Dogecoin', 10.0, 0.0, 'For Price', 1, 1.0, 0]
                        ])
        except Exception, e:
            print "Adding Rate-Buy orders failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding Rate-Buy orders passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_rate_sell_orders_to_the_book(self):
        ''' Adding a Rate-Sell order for Bitcoin then Dogecoin then both'''
        print ""; print "Adding Rate-Sell orders"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            exchange('test@example.com', 'Sell', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 1)
            assert view_log() == []
            assert_book([['test@example.com', 'Sell', 'Bitcoin', 10.0, 0.0, 'For Price', 1, 1.0, 0]])
            exchange('test@example.com', 'Sell', 'Dogecoin', 10, 'For Price', 'Good Until Canceled', 1)
            assert_book([['test@example.com', 'Sell', 'Bitcoin', 10.0, 0.0, 'For Price', 1, 1.0, 0], 
                         ['test@example.com', 'Sell', 'Dogecoin', 10.0, 0.0, 'For Price', 1, 1.0, 0]
                        ])
        except Exception, e:
            print "Adding Rate-Sell orders failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding Rate-Sell orders passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_rate_sell_then_a_rate_buy_order(self):
        ''' Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy different user'''
        print ""; print "Rate-Sell then Rate-Buy same quantity same rate"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            exchange('test@example.com', 'Sell', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 1)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 1)
            assert_txns([["Bitcoin", 9.990009990009991, 0.999, 1.001, 0.01998001998001889, 'test@example.com', 'test1@example.com', 'For Price', 'For Price']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType
            assert_book([['test@example.com', 'Sell', 'Bitcoin', 0.009990009990008986, 9.990009990009991, 'For Price', 0, 1.0, 1], 
                         ['test1@example.com', 'Buy', 'Bitcoin', 0.009990009990008986, 9.990009990009991, 'For Price', 0, 1.0, 1]
                        ])
        except Exception, e:
            print "Rate-Sell then Rate-Buy same quantity same rate failed"
            traceback.print_exc()
            raise e
        else:
            print "Rate-Sell then Rate-Buy same quantity same rate passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_a_rate_sell_then_a_rate_buy_order_different_quantities(self):
        ''' Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy different quantities'''
        print ""; print "Rate-Sell then Rate-Buy same quantity same rate different quantities"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            exchange('test@example.com', 'Sell', 'Bitcoin', 20, 'For Price', 'Good Until Canceled', 1.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 5, 'For Price', 'Good Until Canceled', 1.0)

            assert_txns([[5.0, 'Bitcoin', 0.999, 1.001, 0.009999999999999454, 'test@example.com', 'test1@example.com', 'For Price', 'For Price']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType

            assert_book([['test@example.com', 'Sell', 'Bitcoin', 15.0, 5.0, 'For Price', 0, 1.0, 0], 
                         ['test1@example.com', 'Buy', 'Bitcoin', 0.0, 5.0, 'For Price', 1.0, 1]
                        ])
            exchange('test@example.com', 'Sell', 'Dogecoin', 7, 'For Price', 'Good Until Canceled', 1.0)
            exchange('test1@example.com', 'Buy', 'Dogecoin', 20, 'For Price', 'Good Until Canceled', 1.0)

            assert_txns([[5.0, 'Bitcoin', 0.999, 1.001, 0.009999999999999454, 'test@example.com', 'test1@example.com', 'For Price', 'For Price'],
                         [7.0, 'Dogecoin', 0.999, 1.001, 0.013999999999999235, 'test@example.com', 'test1@example.com', 'For Price', 'For Price']])
            assert_book([['test@example.com', 'Sell', 'Bitcoin',  15.0, 5.0, 'For Price', 0, 1.0, 0],
                         ['test1@example.com', 'Buy', 'Bitcoin',  0.0,  5.0, 'For Price', 0, 1.0, 1],
                         ['test1@example.com', 'Buy', 'Dogecoin', 13.0, 7.0, 'For Price', 0, 1.0, 0],
                         ['test@example.com', 'Sell', 'Dogecoin', 0.0,  7.0, 'For Price', 0, 1.0, 1]])

        except Exception, e:
            print "Rate-Sell then Rate-Buy same quantity same rate different quantities failed"
            traceback.print_exc()
            raise e
        else:
            print "Rate-Sell then Rate-Buy same quantity same rate different quantities passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_a_rate_sell_then_a_rate_buy_order_different_rates(self):
        ''' Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy different rates'''
        print ""; print "Rate-Sell then Rate-Buy same quantity same rate different rates"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            # Buy bitcoins at a higher rate
            exchange('test@example.com', 'Sell', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 1.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 10, 'For Price', 'Good Until Canceled', 2.0)

            assert_txns([[6.662225183211193, 'Bitcoin', 1.501, 1.499, 0.01332445036642092, 'test1@example.com', 'test@example.com', 'For Price', 'For Price']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType
            assert_book([['test@example.com', 'Sell', 'Bitcoin',  3.337774816788807, 6.662225183211193, 'For Price', 0, 1.0, 0],
                        ['test1@example.com', 'Buy',  'Bitcoin',  3.337774816788807, 6.662225183211193, 'For Price', 0, 2.0, 0]])
            # Sell Dogecoins at a higher rate. Cant perform this txn
            exchange('test1@example.com', 'Sell', 'Dogecoin', 10, 'For Price', 'Good Until Canceled', 2.0)
            exchange('test@example.com',  'Buy',  'Dogecoin', 10, 'For Price', 'Good Until Canceled', 1.0)
            assert_txns([[6.662225183211193, 'Bitcoin', 1.501, 1.499, 0.01332445036642092, 'test1@example.com', 'test@example.com', 'For Price', 'For Price']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType
            assert_book([['test@example.com', 'Sell', 'Bitcoin',  3.337774816788807, 6.662225183211193, 'For Price', 0, 1.0, 0],
                        ['test1@example.com', 'Buy',  'Bitcoin',  3.337774816788807, 6.662225183211193, 'For Price', 0, 2.0, 0],
                        ['test1@example.com', 'Sell', 'Dogecoin', 10.0, 0.0, 'For Price', 2.0, 0],
                        ['test@example.com', 'Buy', 'Dogecoin', 10.0, 0.0, 'For Price', 1.0, 0]])
        except Exception, e:
            print "Rate-Sell then Rate-Buy same quantity same rate different rates failed"
            traceback.print_exc()
            raise e
        else:
            print "Rate-Sell then Rate-Buy same quantity same rate different rates passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_a_rate_sell_then_a_market_buy_order(self):
        ''' Adding a Rate-Sell order for Bitcoin then Bitcoin Market-Buy '''
        print ""; print "Adding a Rate-Sell order for Bitcoin then Bitcoin Market-Buy"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            exchange('test@example.com', 'Sell', 'Bitcoin', 1.5, 'For Price', 'Good Until Canceled', 2.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 1.5, 'At Market', 'Good Until Canceled', 0.0)

            assert_txns([[1.5, 'Bitcoin', 1.999, 2.001, 0.0029999999999996696, 'test1@example.com', 'test@example.com', 'For Price', 'At Market']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType
            assert_book([['test@example.com', 'Sell', 'Bitcoin',  0.0, 1.5, 'For Price', 0, 2.0, 1],
                        ['test1@example.com', 'Buy',  'Bitcoin',  0.0, 1.5, 'At Market', 0, 1.0, 1]])
        except Exception, e:
            print "Adding a Rate-Sell order for Bitcoin then Bitcoin Market-Buy failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding a Rate-Sell order for Bitcoin then Bitcoin Market-Buy passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_a_market_sell_then_a_rate_buy_order(self):
        ''' Adding a Market-Sell order for Bitcoin then Bitcoin Rate-Buy '''
        print ""; print "Adding a Market-Sell order for Bitcoin then Bitcoin Rate-Buy"
        try:
            reset_currencies()
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            
            exchange('test@example.com', 'Sell', 'Bitcoin', 1.5, 'At Market', 'Good Until Canceled', 0.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 1.5, 'For Price', 'Good Until Canceled', 2.0)
      
            assert_txns([[1.5, 'Bitcoin', 1.999, 2.001, 0.0029999999999996696, 'test1@example.com', 'test@example.com', 'For Price', 'At Market']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType

            assert_book([['test@example.com', 'Sell', 'Bitcoin',  0.0, 1.5, 'At Market', 0, 0.0, 1],
                        ['test1@example.com', 'Buy',  'Bitcoin',  0.0, 1.5, 'For Price', 0, 2.0, 1]])

        except Exception, e:
            print "Adding a Market-Sell order for Bitcoin then Bitcoin Rate-Buy failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding a Market-Sell order for Bitcoin then Bitcoin Rate-Buy passed"

    #@unittest.skip("demonstrating skipping")
    def test_adding_a_market_sell_then_a_market_buy_order(self):
        ''' Adding a Market-Sell order for Bitcoin then Bitcoin Market-Buy '''
        print ""; print "Adding a Market-Sell order for Bitcoin then Bitcoin Market-Buy"
        try:
            add_user('test@example.com', 'test_user', 10, 10, 10)
            add_user('test1@example.com', 'test_user1', 10, 10, 10)
            
            exchange('test@example.com', 'Sell', 'Bitcoin', 1.5, 'At Market', 'Good Until Canceled', 0.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 1.5, 'At Market', 'Good Until Canceled', 0.0)
            assert view_log() == []
            assert_book([['test@example.com', 'Sell', 'Bitcoin', 1.5, 0.0, 'At Market', 0, 0.0, 0],
                         ['test1@example.com', 'Buy', 'Bitcoin', 1.5, 0.0, 'At Market', 0, 0.0, 0]
                        ])
        except Exception, e:
            print "Adding a Market-Sell order for Bitcoin then Bitcoin Market-Buy failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding a Market-Sell order for Bitcoin then Bitcoin Market-Buy passed"

    #@unittest.skip("demonstrating skipping")
    def test_add_funds_rate_buy_then_rate_sell(self):
        ''' Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy then add_funds'''
        print ""; print "Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy then add_funds"
        try:
            add_user('test@example.com', 'test_user', 0, 0, 0)
            add_user('test1@example.com', 'test_user1', 0, 0, 0)
            
            exchange('test@example.com', 'Sell', 'Bitcoin', 1.5, 'For Price', 'Good Until Canceled', 2.0)
            exchange('test1@example.com', 'Buy', 'Bitcoin', 1.5, 'For Price', 'Good Until Canceled', 2.0)
            assert view_log() == []
            assert_book([['test@example.com', 'Sell', 'Bitcoin', 1.5, 0.0, 'For Price', 0, 2.0, 0],
                         ['test1@example.com', 'Buy', 'Bitcoin', 1.5, 0.0, 'For Price', 0, 2.0, 0]
                        ])

            for user in view_users():
                add_funds(user, 10.0, 10.0, 10.0)
            assert_txns([[1.5, 'Bitcoin', 1.999, 2.001, 0.0029999999999996696, 'test1@example.com', 'test@example.com', 'For Price', 'For Price']])
            # Currency, Quantity, sRate, bRate, Pocketed, bEmail, sEmail, bType, sType
        
            assert_book([['test@example.com', 'Sell', 'Bitcoin',  0.0, 1.5, 'For Price', 0, 2.0, 1],
                        ['test1@example.com', 'Buy',  'Bitcoin',  0.0, 1.5, 'For Price', 0, 2.0, 1]])
        except Exception, e:
            print "Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy then add_funds failed"
            traceback.print_exc()
            raise e
        else:
            print "Adding a Rate-Sell order for Bitcoin then Bitcoin Rate-Buy then add_funds passed"

if __name__ == '__main__':
    create_or_replace_db()
    unittest.main()
