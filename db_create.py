#!/usr/bin/python
import hyperdex.admin
import hyperdex.client
from config import SERVER_DB_ADDRESS

a = hyperdex.admin.Admin(SERVER_DB_ADDRESS, 1982)
c = hyperdex.client.Client(SERVER_DB_ADDRESS, 1982)

def create_or_replace_db():
    if 'users' in a.list_spaces():
        a.rm_space('users')
    if 'orders' in a.list_spaces():
        a.rm_space('orders')
    if 'txns' in a.list_spaces():
        a.rm_space('txns')
    if 'currencies' in a.list_spaces():
        a.rm_space('currencies')
    if 'bitcoin_addresses' in a.list_spaces():
        a.rm_space('bitcoin_addresses')
    if 'bitcoin_txns' in a.list_spaces():
        a.rm_space('bitcoin_txns')
    if 'dogecoin_addresses' in a.list_spaces():
        a.rm_space('dogecoin_addresses')
    if 'dogecoin_txns' in a.list_spaces():
        a.rm_space('dogecoin_txns')

    a.add_space('''
    space users
        key string email

        attributes
            string       name,
            float        funds,
            float        Bitcoin,
            float        Dogecoin,
            string       bitcoin_address,
            string       dogecoin_address

        subspace name
        subspace funds, Bitcoin, Dogecoin
    ''')
    print 'DB Created space users...'

    a.add_space('''
    space orders
        key string order_id

        attributes
            string action,
            string currency,
            float  quantity_outstanding,
            float  quantity_fulfilled,
            string order_type,
            float  rate,
            int    expiry,
            int    is_complete,
            string user_email

        subspace currency, action, order_type, is_complete, user_email
    ''')
    print 'DB Created space orders...'

    a.add_space('''
    space txns
        key string txn_id

        attributes
            string buy_order_id,
            string sell_order_id,
            string buy_user_email,
            string sell_user_email,
            string buy_order_type,
            string sell_order_type,
            string currency,
            float  quantity,
            float  buy_rate,
            float  sell_rate,
            float  pocketed,
            float  time_stamp

        subspace time_stamp
        subspace buy_order_id, sell_order_id
        subspace buy_user_email, sell_user_email
    ''')
    print 'DB Created space txns...'

    a.add_space('''
    space currencies
        key string currency

        attributes
            float last_trade,
            float highest_buy_rate,
            float lowest_sell_rate

        subspace last_trade, highest_buy_rate, lowest_sell_rate
    ''')
    print 'DB Created space currencies...'

    a.add_space('''
    space bitcoin_addresses
        key string pub_key

        attributes
            string pub_key_foo

        subspace pub_key_foo
    ''')
    print 'DB Created space bitcoin_keys...'

    a.add_space('''
    space bitcoin_txns
        key timestamp(day) when

        attributes
            string pub_key,
            float amount,
            string txid,
            string email

        subspace amount, txid, pub_key, email
    ''')
    print 'DB Created space bitcoin_txns...'

    a.add_space('''
    space dogecoin_addresses
        key string pub_key

        attributes
            string pub_key_foo

        subspace pub_key_foo
    ''')
    print 'DB Created space dogecoin_keys...'

    a.add_space('''
    space dogecoin_txns
        key timestamp(day) when

        attributes
            string pub_key,
            float amount,
            string txid,
            string email

        subspace amount, txid, pub_key, email
    ''')
    print 'DB Created space dogecoin_txns...'

    c.put('currencies', 'Bitcoin',  {'last_trade' : -1.0, 'highest_buy_rate' : -1.0, 'lowest_sell_rate' : -1.0})
    c.put('currencies', 'Dogecoin', {'last_trade' : -1.0, 'highest_buy_rate' : -1.0, 'lowest_sell_rate' : -1.0})
    c.put('users', 'exchange', {'name':'exchange', 'funds' : 0.0, 'Bitcoin' : 0.0, 'Dogecoin' : 0.0, 'bitcoin_address': 'mgsriptmbJhzNcgqDBiBLmgFMbJFZbfJkY', 'dogecoin_address': 'nfzF6rTxSpXLLHJHurXWz9Zuo66aB7Rmt3'})

if __name__ == "__main__":
    create_or_replace_db()
