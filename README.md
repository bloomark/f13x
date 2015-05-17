#f13x - Bitcoin Exchange

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
