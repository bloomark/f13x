hyperdex coordinator -f -l 127.0.0.1 -p 1982 --data=/home/akhil/hyperdex/tutorial/HyperFlaskr/coordinator --daemon
sleep 10;
hyperdex daemon -f --listen=127.0.0.1 --listen-port=2012 --coordinator=127.0.0.1 --coordinator-port=1982 --data=/home/akhil/hyperdex/tutorial/HyperFlaskr/data/ --daemon
ps -eaf | grep hyperdex

