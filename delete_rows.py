#!/usr/bin/python
import hyperdex.client
import sys
import hyperdex.admin
from config import SERVER_DB_ADDRESS

c = hyperdex.client.Client(SERVER_DB_ADDRESS, 1982)
a = hyperdex.admin.Admin(SERVER_DB_ADDRESS, 1982)

def delete_rows():
    if 'orders' in a.list_spaces():  
        orders = c.search('orders', {})
        for order in orders:
            c.delete('orders', order['order_id'])
    if 'txns' in a.list_spaces():
        txns = c.search('txns', {})
        for txn in txns:
            c.delete('txns', txn['txn_id'])

def delete_users():
    if 'users' in a.list_spaces():
        users = c.search('users', {})
        for user in users:
            c.delete('users', user['email'])
            #c.put('users', user['email'], {'funds':0.0, 'Bitcoin':0.0, 'Dogecoin':0.0})
        c.put('users', 'exchange', {'name':'exchange', 'funds' : 0.0, 'Bitcoin' : 0.0, 'Dogecoin' : 0.0, 'bitcoin_address': 'mgsriptmbJhzNcgqDBiBLmgFMbJFZbfJkY', 'dogecoin_address': 'nfzF6rTxSpXLLHJHurXWz9Zuo66aB7Rmt3'})

def reset_users():
    if 'users' in a.list_spaces():
        users = c.search('users', {})
        for user in users:
            #c.delete('users', user['email'])
            c.put('users', user['email'], {'funds':0.0, 'Bitcoin':0.0, 'Dogecoin':0.0})
        c.put('users', 'exchange', {'name':'exchange', 'funds' : 0.0, 'Bitcoin' : 0.0, 'Dogecoin' : 0.0, 'bitcoin_address': 'mgsriptmbJhzNcgqDBiBLmgFMbJFZbfJkY', 'dogecoin_address': 'nfzF6rTxSpXLLHJHurXWz9Zuo66aB7Rmt3'})

def reset_currencies():
    c.put('currencies', 'Bitcoin',  {'last_trade' : -1.0, 'highest_buy_rate' : -1.0, 'lowest_sell_rate' : -1.0})
    c.put('currencies', 'Dogecoin', {'last_trade' : -1.0, 'highest_buy_rate' : -1.0, 'lowest_sell_rate' : -1.0})

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset_users()
    else:
        delete_rows()
        delete_users()
