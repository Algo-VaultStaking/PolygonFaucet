import datetime
from math import floor
import requests
import configparser
from logger import log, raw_audit_log

import mariadb

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

FAUCET_ADDRESS = str(c["FAUCET"]["address"])
POLYGONSCAN_API_KEY = str(c["GENERAL"]["api_key"])
DB_CHECK = True if str(c["DATABASE"]["db_check"]).lower() == "true" else False

if DB_CHECK:
    DB_USER = str(c["DATABASE"]["user"])
    DB_PASSWORD = str(c["DATABASE"]["password"])
    DB_HOST = str(c["DATABASE"]["host"])
    DB_NAME = str(c["DATABASE"]["name"])


# Connect to MariaDB Platform
def connection():
    try:
        conn = mariadb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=3306,
            database=DB_NAME
        )

        return conn

    except mariadb.Error as e:
        raw_audit_log(f"Error connecting to MariaDB Platform: {e}")
        exit()


def initial_setup():
    try:
        conn = connection()
        cur = conn.cursor()
        # cur.execute("DROP TABLE Transactions;")
        # cur.execute("DROP TABLE Users;")
        # cur.execute("DROP TABLE Blacklisted;")

        cur.execute("CREATE TABLE Transactions(UserID VARCHAR(20), "
                    "Address VARCHAR(42), "
                    "Tokens FLOAT(10,4), "
                    "FirstSeen VARCHAR(30), "
                    "LastSeen VARCHAR(30));")

        cur.execute("CREATE TABLE Users(UserID VARCHAR(20), "
                    "Username varchar(50));")

        cur.execute("CREATE TABLE Blacklisted(UserID VARCHAR(20), "
                    "Address VARCHAR(42), "
                    "Blacklisted BOOLEAN, "
                    "Imported BOOLEAN);")
        cur.close()
        conn.close()
    except mariadb.Error as e:
        raw_audit_log(f"Error: {e}")


def get_user_totals(user_id: str, address: str, network: str):
    conn = connection()
    cur = conn.cursor()
    cur.execute("SELECT UserID, Address, Tokens, Network FROM Transactions")
    tokens = 0.0
    for id, addr, tkns, ntwk in cur:
        if (str(user_id) == str(id) or addr == address) and ntwk == network:
            tokens += tkns
    cur.close()
    conn.close()
    return tokens


def add_transaction(user_id: str, address: str, tokens: float, timestamp: str, network: str):
    conn = connection()
    cur = conn.cursor()
    cur.execute("SELECT UserID, Address, Tokens, Network FROM Transactions")
    found = False
    current_tokens = 0
    for id, addr, tkns, ntwk in cur:
        if user_id == id and addr == address and ntwk == network:
            current_tokens = tkns
            found = True

    tokens = floor((tokens + current_tokens) * 10000) / 10000
    try:
        if found:
            command = "UPDATE Transactions " \
                      "SET tokens = " + str(tokens) + ", LastSeen = '" + timestamp + "' " \
                      "WHERE UserID = '" + user_id + "' AND Address = '" + address + "' AND Network = '" + network + "';"
            cur.execute(command)
            conn.commit()
        else:
            cur.execute("INSERT INTO Transactions VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, address, tokens, timestamp, timestamp, network))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except mariadb.Error as e:
        raw_audit_log(f"Error: {e}")
        conn.close()
        return False


def add_user(user_name: str, user_id: str):
    conn = connection()
    cur = conn.cursor()
    cur.execute("SELECT UserID, Username FROM Users")

    for uid, name in cur:
        if user_id == uid and name == user_name:
            cur.close()
            conn.close()
            return True

    try:
        cur.execute("INSERT INTO Users VALUES (?, ?)", (user_id, user_name))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except mariadb.Error as e:
        raw_audit_log(f"Error: {e}")
        return False


def reset_amoy_amount(user: int):
    conn = connection()
    cur = conn.cursor()
    command = f"INSERT INTO Transactions VALUES (\"{user}\", \"0x0\", -150, \"01/01/2022, 00:00:00\", \"01/01/2022, 00:00:00\", \"Amoy\");"
    cur.execute(command)
    conn.commit()
    conn.close()
    return True


def check_if_blacklisted(user: str, address: str):
    conn = connection()
    cur = conn.cursor()
    cur.execute("SELECT UserID FROM Blacklisted;")

    for user_id in cur:
        if user_id[0] == user:
            add_blacklisted_user(user, address)
            conn.close()
            raw_audit_log(str(user) + " is on the blacklist.")
            return True

    response = requests.get("https://api.etherscan.io/v2/api?chainid=137" +
                            "&module=account" +
                            "&action=txlist" +
                            "&address=" + address +
                            "&startblock=10000000" +
                            "&endblock=99999999" +
                            "&page=1" +
                            "&offset=100" +
                            "&sort=asc" +
                            "&apikey=" + POLYGONSCAN_API_KEY)

    addresses = [address]
    result = response.json()['result']
    for tx in result:
        addresses.append(tx['from'])
        addresses.append(tx['to'])

    cur.execute("SELECT Address FROM Blacklisted")

    for addr in cur:
        if addr[0] in addresses:
            add_blacklisted_address(user, address)
            conn.close()
            raw_audit_log(str(address) + " is on the blacklist.")
            return True

    cur.execute("SELECT Address FROM Transactions")

    addresses.remove(address)
    for addr in cur:
        if addr[0] in addresses:
            conn.close()
            raw_audit_log(address + " has a connection to " + addr[0] + ".")
            return True

    conn.close()
    raw_audit_log(str(user) + " and " + str(address) + " not found in the blacklist.")
    return False


def add_blacklisted_address(user: str, address: str):
    conn = connection()
    cur = conn.cursor()
    command = "SELECT * FROM Blacklisted " \
              "WHERE UserID = '" + str(user) + "' AND Address = '" + address + "';"
    cur.execute(command)
    if cur.fetchall():
        response = "Address already blacklisted."
    else:
        cur.execute("INSERT INTO Blacklisted VALUES (?, ?, ?, ?)", (address, 1, 1, user))
        conn.commit()
        response = "Address blacklisted."
    conn.close()
    return response


def add_blacklisted_user(user: str, address=""):
    conn = connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Blacklisted WHERE UserID = (?)", (user,))
    if cur.fetchall():
        response = "User already blacklisted."
    else:
        cur.execute("INSERT INTO Blacklisted VALUES (?, ?, ?, ?)", (address, 1, 1, user))
        conn.commit()
        response = "Address blacklisted."
    conn.close()
    return response


def get_if_existing_account(address: str):
    response = requests.get("https://api.etherscan.io/v2/api?chainid=137"
                            "&module=account" +
                            "&action=txlist" +
                            "&address=" + address +
                            "&startblock=10000000" +
                            "&endblock=99999999" +
                            "&page=1" +
                            "&offset=10" +
                            "&sort=asc" +
                            "&apikey=" + POLYGONSCAN_API_KEY)
    normal_tx_content = response.json()['result']
    normal_transactions = len(normal_tx_content)

    response = requests.get("https://api.etherscan.io/v2/api?chainid=137" +
                            "&module=account" +
                            "&action=tokentx" +
                            "&address=" + address +
                            "&startblock=1000000" +
                            "&endblock=99999999" +
                            "&page=1" +
                            "&offset=5" +
                            "&sort=asc" +
                            "&apikey=" + POLYGONSCAN_API_KEY)
    erc_20_transactions = len(response.json()['result'])

    response = requests.get("https://api.etherscan.io/v2/api?chainid=137" +
                            "&module=account" +
                            "&action=tokennfttx" +
                            "&address=" + address +
                            "&startblock=1000000" +
                            "&endblock=99999999" +
                            "&page=1" +
                            "&offset=5" +
                            "&sort=asc" +
                            "&apikey=" + POLYGONSCAN_API_KEY)
    erc_721_transactions = len(response.json()['result'])

    raw_audit_log(address + " has " + str(normal_transactions) + " transactions and " +
                  str(erc_20_transactions) + " erc-20 transactions.")

    if 1 <= normal_transactions < 20 or 1 <= erc_20_transactions < 20 or 1 <= erc_721_transactions < 20:
        return True
    return False
