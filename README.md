# Polygon Network Faucet

A Discord bot that sends small amounts of POL to community members on **Polygon mainnet** and **Amoy testnet**. Users request funds with prefix commands (`faucet-…`); the bot role-gates requests, checks wallet format and request limits, then broadcasts an EIP-1559 transfer from a shared faucet wallet.

The same faucet address has sent:

| Network | Outgoing transactions (account nonce) |
| --- | ---: |
| Polygon mainnet | **20,178** |
| Polygon Amoy | **29,531** |

Nonce is the number of transactions the faucet wallet has sent on that chain (requests, admin overrides, and other outgoing txs from the same key). Figures above were read from chain at the time of this README update.

## What it does

In Discord, eligible members run:

| Command | Who | What |
| --- | --- | --- |
| `faucet-mainnet [address]` | Community roles | Sends **0.01 POL** on Polygon mainnet |
| `faucet-balance` | Community roles | Shows remaining mainnet faucet POL |
| `faucet-amoy [address]` | Developer roles | Sends **5 POL** on Amoy testnet |
| `faucet-amoy-balance` | Admins | Shows remaining Amoy faucet POL |
| `faucet-mainnet-override [address] [tokens]` | Admins | Mainnet send with a custom amount |
| `faucet-amoy-override [address] [tokens]` | Admins | Amoy send with a custom amount |
| `faucet-amoy-reset [user]` | Admins | Resets a user’s Amoy request cap |
| `faucet-blacklist [address]` | Admins | Blacklists a wallet |
| `faucet-version` | Admins | Prints the bot version |

Requests are denied when the address is invalid (including all-lowercase), the wallet already holds more than the configured max, the user or address has already taken the cap, or the faucet is low on funds. Optional MariaDB tracking stores Discord user ID, username, wallet, amount, and network so the same person cannot drain the faucet through repeat requests.

The bot is a **prefix command** app. It needs Discord **Message Content Intent** to read `faucet-` commands and the wallet address argument. It does not need Server Members or Presence intents: it does not scan member lists, join events, or online status.

## Setup

Clone this repository:

```bash
git clone https://github.com/Algo-VaultStaking/PolygonFaucet.git
```

Copy `config.ini.example` to `config.ini` and fill in Discord token, faucet address and key, RPCs, role names, and optional database settings.

If `db_check` is true, you need a MySQL/MariaDB instance. That is what enforces per-user and per-wallet request totals. Without it, the bot still enforces “wallet already has enough POL” on mainnet, but not Discord-user request history.

Add a systemd unit for start/stop:

```bash
sudo cat > /etc/systemd/system/faucet.service << "EOF"
[Unit]
  Description=PolygonFaucet

[Service]
  ExecStart=/usr/bin/python3 /home/ubuntu/PolygonFaucet/main.py
  LimitNOFILE=4096

[Install]
  WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable faucet
sudo service faucet start
```
