import hyperdex.client

import smtplib

from bitcoin.core import COIN, b2lx
import bitcoin.wallet
import bitcoin.rpc
try:
    from bitcoin.case58 import CBitcoinAddress
except:
    from bitcoin.wallet import CBitcoinAddress

from config import SERVER_DB_ADDRESS, MAIL_USERNAME, MAIL_PASSWORD, NAME

c = hyperdex.client.Client(SERVER_DB_ADDRESS, 1982)

EMAIL = MAIL_USERNAME
username = MAIL_USERNAME
password = MAIL_PASSWORD

server = smtplib.SMTP("smtp.gmail.com:587")
server.starttls()
server.login(username,password)

bitcoin.SelectParams(NAME)
rpc = bitcoin.rpc.Proxy(timeout=900)

uninitiated_users = list(c.search('users', {'bitcoin_address': ''}))
for user in uninitiated_users:
    x = c.begin_transaction()
    num = c.count('bitcoin_addresses', {})
    if num == 0:
    	server.sendmail(EMAIL, EMAIL, "[BTC_KEY] Empty")
        break
    else:
        pub_key = ''
        bitcoin_addresses = c.sorted_search('bitcoin_addresses', {}, 'pub_key_foo', 1, 'min')
        for bitcoin_key in bitcoin_addresses:
            pub_key = bitcoin_key['pub_key_foo']
        x.delete('bitcoin_addresses', pub_key)
        x.put('users', user['email'], {'bitcoin_address': pub_key})
        rpc.importaddress(pub_key, label=user['email'])
        server.sendmail(EMAIL, EMAIL, "[BTC_KEY] %s assigned to %s" % (pub_key, user['email']))
    x.commit()

uninitiated_users = list(c.search('users', {'dogecoin_address': ''}))
for user in uninitiated_users:
    x = c.begin_transaction()
    num = c.count('dogecoin_addresses', {})
    if num == 0:
        server.sendmail(EMAIL, EMAIL, "[DOGE_KEY] Empty")
        break
    else:
        pub_key = ''
        dogecoin_addresses = c.sorted_search('dogecoin_addresses', {}, 'pub_key_foo', 1, 'min')
        for dogecoin_key in dogecoin_addresses:
            pub_key = dogecoin_key['pub_key_foo']
        x.delete('dogecoin_addresses', pub_key)
        x.put('users', user['email'], {'dogecoin_address': pub_key})
        # Dogecoin doesn't yet support import address :(
        # dogecoin_rpc.importaddress(pub_key, label=user['email'])
        server.sendmail(EMAIL, EMAIL, "[DOGE_KEY] %s assigned to %s" % (pub_key, user['email']))
    x.commit()    

server.quit()
