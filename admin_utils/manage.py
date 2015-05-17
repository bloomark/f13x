#!/usr/bin/python
import sys
import os
import hyperdex.client
import hyperdex.admin
import subprocess
import json
import hyperdex.client

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
import requests
import binascii
from addrgen import get_addr

from admin_secrets import NAME, bitcoin_service_url, dogecoin_service_url, SERVER_DB_ADDRESS, MANAGER_DB_ADDRESS, EXCHANGE_BITCOIN_ADDRESS, EXCHANGE_DOGECOIN_ADDRESS

hexlify = binascii.hexlify
unhexlify = binascii.unhexlify

# Connect to Bitcoin RPC
bitcoin.SelectParams(NAME)
rpc = bitcoin.rpc.Proxy(service_url=bitcoin_service_url + ':' + str(bitcoin.params.RPC_PORT))

# Connect to Dogecoin RPC
dogecoin.SelectParams(NAME)
dogecoin_rpc = dogecoin.rpc.Proxy(service_url=dogecoin_service_url + ':' + str(dogecoin.params.RPC_PORT))

# Connect to HyperDex
a = hyperdex.admin.Admin(MANAGER_DB_ADDRESS, 1982)
webserver_c = hyperdex.client.Client(SERVER_DB_ADDRESS, 1982)
manager_c = hyperdex.client.Client(MANAGER_DB_ADDRESS, 1982)

class Manager:
    def __init__(self):
        pass

    def cashout(self, args):
        if len(args) < 1 or len(args) > 1:
            print 'Usage:'
            print './manage.py cashout <btc|doge>'
            return

        if args[0] == 'btc':
            self.cashout_btc()
        elif args[0] == 'doge':
            self.cashout_doge()
        else:
            print 'Onlt btc|doge supported.'

    def cashout_btc(self):
        ''' For every incomplete cashout 'transaction', create add the address,
        amount pair to the payments dictionary and then call the sendmany() rpc
        from the 'exchange' account. Then update all the 'transactions' you 
        just completed with the BTC transactionID, i.e. lxtxid.
        '''
        webserver_x = webserver_c.begin_transaction()
        payments = {}
        serviced_txns = []
        lxtxid = ''
        for order in webserver_c.search('bitcoin_txns', {'txid': ''}): 
            try:
                amount = order['amount'] - 0.0002
                addr = order['pub_key']
                if addr in payments.keys(): payments[addr] += (amount * COIN)
                else: payments[addr] = (amount * COIN)
                serviced_txns.append(order['when'])
            except:
                continue
        if len(payments) > 0:
            print 'Calling send'
            txid = rpc.sendmany(fromaccount='', payments=payments)
            lxtxid = b2lx(txid)
            print '%s' % lxtxid
            for when in serviced_txns:
                webserver_x.put('bitcoin_txns', when, {'txid': str(lxtxid)})
        webserver_x.commit()

    def cashout_doge(self):
        ''' For every incomplete cashout 'transaction', create add the address,
        amount pair to the payments dictionary and then call the sendmany() rpc
        from the 'exchange' account. Then update all the 'transactions' you 
        just completed with the BTC transactionID, i.e. lxtxid.
        '''
        webserver_x = webserver_c.begin_transaction()
        payments = {}
        serviced_txns = []
        lxtxid = ''
        for order in webserver_c.search('dogecoin_txns', {'txid': ''}): 
            try:
                amount = order['amount'] - 0.0002
                addr = order['pub_key']
                if addr in payments.keys(): payments[addr] += (amount * COIN)
                else: payments[addr] = (amount * COIN)
                serviced_txns.append(order['when'])
            except:
                continue
        if len(payments) > 0:
            print 'Calling send'
            txid = dogecoin_rpc.sendmany(fromaccount='', payments=payments)
            lxtxid = b2lx(txid)
            print '%s' % lxtxid
            for when in serviced_txns:
                webserver_x.put('dogecoin_txns', when, {'txid': str(lxtxid)})
        webserver_x.commit()

    def initdb(self, args):
        if len(args) > 0:
            print 'Usage:'
            print './manage.py initdb'
            return

        list_spaces = a.list_spaces()
        print list_spaces

        a.add_space('''
            space bitcoin_keypairs
                key pub_key

                attributes
                    string priv_key

                subspace priv_key
        ''')

        a.add_space('''
            space dogecoin_keypairs
                key pub_key

                attributes
                    string priv_key

                subspace priv_key
        ''')

    def keygen(self, args):
        if len(args) < 1 or len(args) > 1:
            print 'Usage:'
            print './manage.py keygen <btc|doge>'
            return

        if args[0]=='btc':
            self.keygen_btc()
        elif args[0]=='doge':
            self.keygen_doge()
        else:
            print 'Only btc|doge supported.'

    def keygen_btc(self):
        manager_x = manager_c.begin_transaction()
        webserver_x = webserver_c.begin_transaction()
        for i in range (0, 5):
            addr = get_addr(111)
            print addr
            manager_x.put('bitcoin_keypairs', addr[0], {'priv_key': addr[1]})
            webserver_x.put('bitcoin_addresses', addr[0], {'pub_key_foo': addr[0]})
        manager_x.commit()
        webserver_x.commit()
        print 'Generated 5 keys'

    def keygen_doge(self):
        manager_x = manager_c.begin_transaction()
        webserver_x = webserver_c.begin_transaction()
        for i in range (0, 5):
            addr = get_addr(113)
            print addr
            manager_x.put('dogecoin_keypairs', addr[0], {'priv_key': addr[1]})
            webserver_x.put('dogecoin_addresses', addr[0], {'pub_key_foo': addr[0]})
        manager_x.commit()
        webserver_x.commit()
        print 'Generated 5 keys'        

    def help(self):
        print 'manager.py - Admin manager for f13x.\n'
        print 'Usage:'
        print './manage.py <command> [params]  Send command to manager'
        print './manage.py help                List commands\n'
        print 'Commands:'
        print 'sweep [btc|doge]                Sweep all bitcoins from the web server to the exchange'
        print 'keygen [btc|doge]               Generate and store private public addresses for the currency'
        print 'initdb                          Create the hyperdex spaces required by the admin'
        print 'cashout [btc|doge]              Compelete all pending outgoing transactions'

    def sweep(self, args):
        if len(args) < 1 or len(args) > 1:
            print 'Usage:'
            print './manage.py sweep <btc|ltc>'
            return

        if args[0]=='btc':
            # Fetch all user entries
            users = webserver_c.search('users', {})
            for user in users:
                if user['bitcoin_address'] != '' and user['name'] != 'exchange':
                    self.sweep_btc_account(
                        SENDER_ADDRESS=user['bitcoin_address'], 
                        email=user['email'])
        elif args[0]=='doge':
            # Fetch all user entries
            users = webserver_c.search('users', {})
            for user in users:
                if user['dogecoin_address'] != '' and user['name'] != 'exchange':
                    self.sweep_doge_account(
                        SENDER_ADDRESS=user['dogecoin_address'], 
                        email=user['email'])
        else:
            print 'Only btc|ltc supported.'

    def sweep_btc_account(self, SENDER_ADDRESS='', email=''):
        addrs = []
        addrs.append(SENDER_ADDRESS)

        transactions = []
        transactions_with_key = []
        sum = 0.0

        utxo = rpc.listunspent(minconf=6, addrs=addrs)
        # Return if there are no transactions
        if len(utxo) == 0: return

        for txo in utxo:
            sum += float(txo['amount'])/COIN
            transaction = {}
            transaction['txid'] = b2lx(txo['outpoint'].hash)
            transaction['vout'] = txo['outpoint'].n
            transactions.append(transaction)
            transaction['scriptPubKey'] = hexlify(txo['scriptPubKey'])
            transactions_with_key.append(transaction)

        # Need to calculate transaction fee
        transaction_fee = 0.0001

        addresses = {}
        addresses[EXCHANGE_BITCOIN_ADDRESS] = sum - transaction_fee

        # Pickup the private key from the database, hardcoded for now
        PRIVATE_KEY = manager_c.get('bitcoin_keypairs', SENDER_ADDRESS)['priv_key']
        private_keys = []
        private_keys.append(PRIVATE_KEY)

        try:
            raw_tx = rpc.createrawtransaction(
                transactions, 
                addresses)
            signed_transaction = rpc.signrawtransaction(
                raw_tx, 
                transactions_with_key, 
                private_keys)
        except:
            raise
            return

        if not signed_transaction['complete'] or not signed_transaction:
            raise 'Transaction signing unsuccessful'
            return
        else:
            txid = rpc.sendrawtransaction(signed_transaction['tx'])
            print 'Sent %s from %s to %s' % (addresses[EXCHANGE_BITCOIN_ADDRESS], SENDER_ADDRESS, PRIVATE_KEY)
            lxtxid = b2lx(txid)
            print lxtxid
            # Update the the users space in hyperdex, add 'sum' bitcoin to the 
            # user's balance keyed on email-id.
            x = webserver_c.begin_transaction()
            #x.put('users', email, {'Bitcoin': x.get('users', email)['Bitcoin'] + addresses[EXCHANGE_BITCOIN_ADDRESS]})
            x.atomic_add('users', email, {'Bitcoin': addresses[EXCHANGE_BITCOIN_ADDRESS]})
            x.commit()

    def sweep_doge_account(self, SENDER_ADDRESS='', email=''):
        addrs=SENDER_ADDRESS
        response = requests.get('https://chain.so/api/v2/get_tx_unspent/DOGETEST/' + addrs)

        if response.status_code != 200:
            return

        content = response.json()
        utxo = content['data']['txs']

        transactions = []
        transactions_with_key = []
        sum = 0.0

        # Return if there are no transactions
        if len(utxo) == 0: return

        for txo in utxo:
            if txo['confirmations'] >= 6:
                sum += float(str(txo['value']))
                transaction = {}
                transaction['txid'] = str(txo['txid'])
                transaction['vout'] = txo['output_no']
                transactions.append(transaction)
                transaction['scriptPubKey'] = str(txo['script_hex']).strip()
                transactions_with_key.append(transaction)

        # Need to calculate transaction fee
        transaction_fee = 0.0001

        addresses = {}
        addresses[EXCHANGE_DOGECOIN_ADDRESS] = sum - transaction_fee

        # Pickup the private key from the database, hardcoded for now
        PRIVATE_KEY = manager_c.get('dogecoin_keypairs', SENDER_ADDRESS)['priv_key']
        private_keys = []
        private_keys.append(PRIVATE_KEY)

        try:
            raw_tx = dogecoin_rpc.createrawtransaction(
                transactions, 
                addresses)
            signed_transaction = dogecoin_rpc.signrawtransaction(
                raw_tx, 
                transactions_with_key, 
                private_keys)
        except:
            raise
            return

        if not signed_transaction['complete'] or not signed_transaction:
            raise 'Transaction signing unsuccessful'
            return
        else:
            txid = dogecoin_rpc.sendrawtransaction(signed_transaction['tx'])
            print 'Sent %s from %s to %s' % (addresses[EXCHANGE_DOGECOIN_ADDRESS], SENDER_ADDRESS, PRIVATE_KEY)
            lxtxid = b2lx(txid)
            print lxtxid
            # Update the the users space in hyperdex, add 'sum' dogecoin to the 
            # user's balance keyed on email-id.
            x = webserver_c.begin_transaction()
            #x.put('users', email, {'Dogecoin': x.get('users', email)['Dogecoin'] + addresses[EXCHANGE_DOGECOIN_ADDRESS]})
            x.atomic_add('users', email, {'Dogecoin': addresses[EXCHANGE_DOGECOIN_ADDRESS]})
            x.commit()

manager = Manager()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        manager.help()
        os._exit(0) 

    try:
        func = getattr(manager, sys.argv[1])
    except:
        manager.help()
        os._exit(0)
    
    sys.argv.pop(0)
    sys.argv.pop(0)

    func(sys.argv)
