from datetime import datetime
import configparser
import logging
#from systemd.journal import JournalHandler
#log = logging.getLogger('faucet')
#log.addHandler(JournalHandler())
#log.setLevel(logging.INFO)

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

#AUDIT_LOG = str(c["GENERAL"]["audit_log"])

#def log(message):
#    if secrets.environment == 'test':
#        print(message)
#
#    else:
#        log = logging.getLogger('faucet')
#        log.setLevel(logging.INFO)
#        log.info(message)


def log(message):
    raw_audit_log(message)


def audit_log(user_name: str, user_id: str, address: str, tokens: float):
    f = open(AUDIT_LOG, "a")
    audit = str(datetime.now()) + ": " + user_name + "(" + user_id + ") requested " + str(tokens) + " to " + address
    f.write(audit)
    f.write('\n')
    f.close()


def raw_audit_log(message: str):
    print(message)
    #f = open(AUDIT_LOG, "a")
    #f.write(message)
    #f.write('\n')
    #f.close()
