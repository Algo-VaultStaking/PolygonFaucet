# Polygon Network Faucet

A Discord bot that sends small amounts of POL to community members on **Polygon mainnet** and **Amoy testnet**. Users request funds with slash commands (`/faucet-…`); the bot role-gates requests, checks wallet format and request limits, then broadcasts an EIP-1559 transfer from a shared faucet wallet.

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
| `/faucet-mainnet` | Community roles | Sends **0.01 POL** on Polygon mainnet |
| `/faucet-balance` | Community roles | Shows remaining mainnet faucet POL |
| `/faucet-amoy` | Developer roles | Sends **5 POL** on Amoy testnet |
| `/faucet-amoy-balance` | Admins | Shows remaining Amoy faucet POL |
| `/faucet-mainnet-override` | Admins | Mainnet send with a custom amount |
| `/faucet-amoy-override` | Admins | Amoy send with a custom amount |
| `/faucet-amoy-reset` | Admins | Resets a user’s Amoy request cap |
| `/faucet-blacklist` | Admins | Blacklists a wallet |
| `/faucet-version` | Admins | Prints the bot version |

Requests are denied when the address is invalid (including all-lowercase), the wallet already holds more than the configured max, the user or address has already taken the cap, or the faucet is low on funds. Optional MariaDB tracking stores Discord user ID, username, wallet, amount, and network so the same person cannot drain the faucet through repeat requests.

The bot is a **slash command** app. Commands are registered to each server it is in when it starts, and to a server when it joins. Invite or re-authorize the bot with the `bot` and `applications.commands` scopes or the slash commands will not appear.

Prefix commands such as `faucet-mainnet` are deprecated. If someone types a message that starts with `faucet-`, the bot replies that those commands have been deprecated and points them at the slash command. That reply is the only reason the bot still needs the **Message Content** intent. It does not need Server Members or Presence intents.

## Setup

Clone this repository:

```bash
git clone https://github.com/Algo-VaultStaking/PolygonFaucet.git
cd PolygonFaucet
```

Copy `config.ini.example` to `config.ini` and fill in the Discord token, faucet address and key, RPCs, and role names. When `db_check` is true, set the database user, password, name, and host to the AWS MariaDB instance.

```bash
cp config.ini.example config.ini
docker build -t polygonfaucet .
docker run -d --name polygonfaucet -v "$PWD/config.ini:/app/config.ini:ro" polygonfaucet
```

`config.ini` is mounted into the container and is not copied into the image. The image includes the MariaDB client library so the bot can reach AWS MariaDB. It does not run a database.

```bash
docker logs -f polygonfaucet
docker stop polygonfaucet
docker start polygonfaucet
```

After changing `config.ini`, restart the container with `docker restart polygonfaucet`. Without `db_check`, the bot still enforces “wallet already has enough POL” on mainnet, but not Discord-user request history.
