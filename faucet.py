import re
import configparser
from datetime import datetime

from logger import log, raw_audit_log
from web3 import Web3

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

FAUCET_ADDRESS = str(c["FAUCET"]["address"])
FAUCET_PRIVKEY = str(c["FAUCET"]["private_key"])

rpc_url = str(c["RPC"]["mainnet"])
w3 = Web3(Web3.HTTPProvider(rpc_url))

mumbai_rpc_url = str(c["RPC"]["mumbai"])
mumbai_w3 = Web3(Web3.HTTPProvider(mumbai_rpc_url))

amoy_rpc_url = str(c["RPC"]["amoy"])
amoy_w3 = Web3(Web3.HTTPProvider(amoy_rpc_url))


def valid_address(address):
    if len(address) == 42 and re.search('0[xX][0-9a-fA-F]{40}', address) and ('[' not in address):
        return True
    return False


# Send a transaction to the requestor
def send_faucet_transaction(address: str, tokens: float):

    # Token input is in Matic, we need to add the additional 18 decimal places
    tokens = tokens * 1e18

    # Get how many transactions we've done to know what our next nonce will be
    nonce = w3.eth.getTransactionCount(FAUCET_ADDRESS)
    log("Trying to send mainnet transaction with nonce " + str(nonce) + "...")

    # Iterate over a few different gas values, with 30 seconds between to make sure it goes through
    for gas in [35 * 1e9, 50 * 1e9, 100 * 1e9, 350 * 1e9, 500 * 1e9, 1000 * 1e9]:
        try:
            log("Trying mainnet transaction to " + address + " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))

            # Create the transaction
            signed_txn = w3.eth.account.sign_transaction(dict(
                nonce=nonce,
                gasPrice=int(gas),
                gas=21000,
                to=address,
                value=int(tokens),
                data=b'',
                chainId=137,
            ),
                FAUCET_PRIVKEY,
            )

            # Send the transaction
            txn_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # Wait for confirmation the transaction was mined
            w3.eth.wait_for_transaction_receipt(txn_hash, timeout=30)

            log("Sent mainnet transaction to " + address + " with nonce " + str(nonce))
            raw_audit_log(str(datetime.now()) + ": Sent " + str(tokens) + " Matic to " + str(address) +
                          " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))
            return True
        except Exception as e:
            raw_audit_log(str(datetime.now()) + ": Sending failed: " + str(e))
    raw_audit_log(str(datetime.now()) + ": Sending failed.")
    return False


def send_mumbai_faucet_transaction(address: str, tokens: float):
    nonce = mumbai_w3.eth.getTransactionCount(FAUCET_ADDRESS)

    for gas in [int(35 * 1e9), int(50 * 1e9), int(100 * 1e9), int(350 * 1e9), int(500 * 1e9), int(1000 * 1e9)]:
        try:
            log("Trying testnet transaction to " + address + " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))

            # Create the transaction
            signed_txn = mumbai_w3.eth.account.sign_transaction(dict(
                nonce=nonce,
                gasPrice=int(gas),
                gas=50000,
                to=address,
                value=int(tokens * 1e18),
                data=b'',
                chainId=80001,
            ),
                FAUCET_PRIVKEY,
            )

            # Send the transaction
            txn_hash = mumbai_w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # Wait for confirmation the transaction was mined
            mumbai_w3.eth.wait_for_transaction_receipt(txn_hash, timeout=30)

            log("Sent testnet transaction to " + address + " with nonce " + str(nonce))
            raw_audit_log(str(datetime.now()) + ": Sent " + str(tokens) + " Matic to " + str(address) +
                          " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))
            return True
        except Exception as e:
            raw_audit_log(str(datetime.now()) + ": Sending failed: " + str(e))
    raw_audit_log(str(datetime.now()) + ": Sending failed.")
    return False


def send_amoy_faucet_transaction(address: str, tokens: float):
    nonce = amoy_w3.eth.getTransactionCount(FAUCET_ADDRESS)

    for gas in [int(35 * 1e9), int(50 * 1e9), int(100 * 1e9), int(350 * 1e9), int(500 * 1e9), int(1000 * 1e9)]:
        try:
            log("Trying testnet transaction to " + address + " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))

            # Create the transaction
            signed_txn = amoy_w3.eth.account.sign_transaction(dict(
                nonce=nonce,
                gasPrice=int(gas),
                gas=50000,
                to=address,
                value=int(tokens * 1e18),
                data=b'',
                chainId=80002,
            ),
                FAUCET_PRIVKEY,
            )

            # Send the transaction
            txn_hash = amoy_w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # Wait for confirmation the transaction was mined
            amoy_w3.eth.wait_for_transaction_receipt(txn_hash, timeout=30)

            log("Sent testnet transaction to " + address + " with nonce " + str(nonce))
            raw_audit_log(str(datetime.now()) + ": Sent " + str(tokens) + " Matic to " + str(address) +
                          " with nonce " + str(nonce) + " and gas " + str(gas / 1e9))
            return True
        except Exception as e:
            raw_audit_log(str(datetime.now()) + ": Sending failed: " + str(e))
    raw_audit_log(str(datetime.now()) + ": Sending failed.")
    return False


# Get address balance
def get_balance(address):
    try:
        response = w3.eth.getBalance(address) / 1e18
    except Exception as e:
        print(e)
        response = 0.0
    return response


# Get faucet balance
def get_faucet_balance():
    try:
        response = w3.eth.getBalance(FAUCET_ADDRESS) / 1e18
    except Exception as e:
        print(e)
        response = 0.0
    return response


def get_mumbai_balance():
    try:
        response = mumbai_w3.eth.getBalance(FAUCET_ADDRESS) / 1e18
    except Exception as e:
        response = e
    return response


def get_amoy_balance():
    try:
        response = amoy_w3.eth.getBalance(FAUCET_ADDRESS) / 1e18
    except Exception as e:
        response = e
    return response
