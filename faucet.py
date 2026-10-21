import re
import configparser
from datetime import datetime

from logger import log, raw_audit_log
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

FAUCET_ADDRESS = str(c["FAUCET"]["address"])
FAUCET_PRIVKEY = str(c["FAUCET"]["private_key"])

GWEI = 10 ** 9
MAX_FEE_CAP = 1000 * GWEI
RECEIPT_TIMEOUT = 5
FEE_BUMP_GWEI = 50 * GWEI
FEE_BUMP_FACTOR = 1.15

rpc_url = str(c["RPC"]["mainnet"])
w3 = Web3(Web3.HTTPProvider(rpc_url))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

amoy_rpc_url = str(c["RPC"]["amoy"])
amoy_w3 = Web3(Web3.HTTPProvider(amoy_rpc_url))
amoy_w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)


def valid_address(address):
    if len(address) == 42 and re.search('0[xX][0-9a-fA-F]{40}', address) and ('[' not in address):
        return True
    return False


def _eip1559_fees(client):
    hist = client.eth.fee_history(5, "latest", [50])
    base_fee = int(hist["baseFeePerGas"][-1])
    try:
        priority = int(client.eth.max_priority_fee)
    except Exception:
        priority = int(hist["reward"][-1][0])
    if hist["reward"] and hist["reward"][-1]:
        priority = max(priority, int(hist["reward"][-1][0]))
    priority = max(priority, 25 * GWEI)
    max_fee = base_fee * 2 + priority
    if max_fee < priority:
        max_fee = priority
    return max_fee, priority


def _bump_fees(max_fee, priority):
    bump = max(FEE_BUMP_GWEI, int(max_fee * (FEE_BUMP_FACTOR - 1)))
    max_fee = max_fee + bump
    priority = max(priority + FEE_BUMP_GWEI, int(priority * FEE_BUMP_FACTOR))
    if priority > max_fee:
        max_fee = priority
    return max_fee, priority


def _send_eip1559_transaction(client, address: str, value_wei: int, chain_id: int, gas_limit: int, network: str):
    nonce = client.eth.get_transaction_count(FAUCET_ADDRESS)
    max_fee, priority = _eip1559_fees(client)
    log("Trying to send " + network + " transaction with nonce " + str(nonce) + "...")

    while max_fee <= MAX_FEE_CAP:
        try:
            log("Trying " + network + " transaction to " + address + " with nonce " + str(nonce) +
                " maxFee=" + str(max_fee / GWEI) + " priority=" + str(priority / GWEI))

            signed_txn = client.eth.account.sign_transaction(dict(
                type=2,
                nonce=nonce,
                maxFeePerGas=int(max_fee),
                maxPriorityFeePerGas=int(priority),
                gas=gas_limit,
                to=Web3.to_checksum_address(address),
                value=int(value_wei),
                data=b'',
                chainId=chain_id,
            ),
                FAUCET_PRIVKEY,
            )

            txn_hash = client.eth.send_raw_transaction(signed_txn.raw_transaction)
            client.eth.wait_for_transaction_receipt(txn_hash, timeout=RECEIPT_TIMEOUT)

            log("Sent " + network + " transaction to " + address + " with nonce " + str(nonce))
            raw_audit_log(str(datetime.now()) + ": Sent " + str(value_wei) + " wei to " + str(address) +
                          " with nonce " + str(nonce) + " maxFee=" + str(max_fee / GWEI) +
                          " priority=" + str(priority / GWEI))
            return True
        except Exception as e:
            raw_audit_log(str(datetime.now()) + ": Sending failed: " + str(e))
            max_fee, priority = _bump_fees(max_fee, priority)
    raw_audit_log(str(datetime.now()) + ": Sending failed.")
    return False


# Send a transaction to the requestor
def send_faucet_transaction(address: str, tokens: float):
    # Token input is in Matic, we need to add the additional 18 decimal places
    return _send_eip1559_transaction(w3, address, int(tokens * 1e18), 137, 21000, "mainnet")


def send_amoy_faucet_transaction(address: str, tokens: float):
    return _send_eip1559_transaction(amoy_w3, address, int(tokens * 1e18), 80002, 50000, "testnet")


# Get address balance
def get_balance(address):
    try:
        response = w3.eth.get_balance(address) / 1e18
    except Exception as e:
        print(e)
        response = 0.0
    return response


# Get faucet balance
def get_faucet_balance():
    try:
        response = w3.eth.get_balance(FAUCET_ADDRESS) / 1e18
    except Exception as e:
        print(e)
        response = 0.0
    return response


def get_amoy_balance():
    try:
        response = amoy_w3.eth.get_balance(FAUCET_ADDRESS) / 1e18
    except Exception as e:
        response = e
    return response
