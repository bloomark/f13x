#f13x - Bitcoin Exchange

At a high level, f13x can be broken into these components.

+ Flask Server
+ Webserver's hyperspaces (database tables)
+ The webserver's own instances of bitcoind.
+ A connection to chain.so_, we use their blockchain API.

+ Admin's hyperspaces (the admin has his own hyperspaces because this is the location of the private keys, that ought not to be exposed to the internet)
+ Admin's bitcoind and dogecoind

The administrator would only need to manage the web server, run with Flask, and the data stores, HyperDex along with providing bitcoind and dogecoind endpoints to monitor addresses and spend outputs.

The Webserver
-------------
The Flask server is the user facing part of the application. It hosts most of the application logic, including order matching, and provides users with their order history and account balance information. We uses AJAX and highcharts to visualize exchange information in real-time. Public addresses are picked up from a pool of unused addresses and assigned to users by a cron job. Since the web server never sees private keys we invoke the importaddress RPC call on the daemons to import these as watch-only addresses (importaddress_ isn't yet implemented on the dogecoin master, hence the need for chain.so_).

The web server also has its own hyperspaces, schemas can be viewed in the db_create.py file, that contain information on users, orders, transactions and a pool of unused addresses. The hyperspaces can be located either on the same machine as the Flask web server or on a different machine with changes in the code to point to the appropriate endpoint.

Admin's Server
--------------
We think it's most secure if the admin's and the web server's hyperspaces are on different machines because of the need to key bitcoin and dogecoin private keys as secret as possible, else anyone would be able to steal unspents! The admin periodically generates new keypairs and pushes only public keys to the webserver's hyperspace for consumption by new users. Additionally, the admin's instances of bitcoind and dogecoind store the exchange's private keys, *much important*.

When a user send satoshis or koinus to his f13x public address they aren't credited to his account until the admin calls his 'sweep' command, instead they continue to remain as unspent outputs in his public address. On calling sweep, the admin program looks up unspent outputs for each user and user uses their private keys to sign a transaction that send all unspents to the exchange's account and subsequently updates user balances in the front-end data stores. Until this point, unspents with >6 confirmations show up as pending balance on the user's finance page.

A cashout is when a user wants to send satoshis or koinus from his account to another address. Cashing out is the most sensitive operation on f13x. It isn't safe to let satisfy a user's cash out request instantaneously, the frequency with which pending cashouts are processed is upto the admin. All requests are processed when a cashout is requested and transaction id's are made available to the user.

Summary
-------
This concludes a high level overview of f13x. To sum it up, here are the endpoints we need

1 x Flask

2 x Bitcoin daemons

1 x Dogecoin daemons

2 x HyperDex hyperspaces (datastores) 

##Dependencies
- pip install Flask
- pip install Flask-WTF
- pip install Flask-Mail
- pip install Flask-OpenID
- pip install Flask-Login
- pip install httplib2
- apt-get install libssl-dev
- apt-get install pkg-config
- pip install simplekv
- pip install git+https://github.com/petertodd/python-bitcoinlib
- pip install -i https://pypi.binstar.org/pypi/simple flask-oidc
- pip install https://pypi.python.org/packages/source/F/Flask-KVSession/Flask-KVSession-0.6.1.tar.gz
- pip install --upgrade google-api-python-client
- pip install authomatic

- sudo add-apt-repository ppa:bitcoin/bitcoin
- sudo apt-get update
- sudo apt-get install bitcoind

    ## Install bittcoin
    git clone https://github.com/bitcoin/bitcoin.git
    cd bitcoin
    git tag
    git checkout v0.10.1rc3
    apt-get install dh-autoreconf
    ./autogen.sh
    ./configure
    sudo apt-get install libdb5.1++-dev
    ./configure --with-incompatible-bdb
    sudo apt-get install libboost-all-dev
    make
    sudo make install

Enable Google+ API on Google developers console

##Usage
- python ./db_create.py to initiate the database
- python f13x.py
- Head to localhost:5000 on your browser
