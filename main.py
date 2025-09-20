from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import BadArgument, MissingRequiredArgument, CommandInvokeError, MissingRole, MissingAnyRole

import faucet
import user_db
import configparser
import argparse
import json
from faucet import valid_address

from logger import log, raw_audit_log

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')
argparser = argparse.ArgumentParser()

MAX_TOKENS_REQUESTED = float(c["TOKEN COUNTS"]["MAX_TOKENS_REQUESTED"])
FAUCET_ADDRESS = str(c["FAUCET"]["address"])
DISCORD_TOKEN = str(c["DISCORD"]["token"])
MEMBER_DISCORD_ROLES = json.loads(c["DISCORD"]["member_roles"])
DEVELOPER_DISCORD_ROLES = json.loads(c["DISCORD"]["developer_roles"])
ADMIN_DISCORD_ROLES = json.loads(c["DISCORD"]["admin_roles"])
ERROR_MESSAGE_CHANNEL = int(c["DISCORD"]["error_channel"])
DB_CHECK = True if str(c["DATABASE"]["db_check"]).lower() == "true" else False

token = DISCORD_TOKEN
intents = discord.Intents.all()
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='faucet-', intents=intents)


def thanks(addr):
    return "If you found this faucet helpful, please consider returning funds to `" \
           + addr + "`. It will help keep the faucet running. Thank you!"


@bot.event
async def on_ready():
    discord.chunk_guilds_at_startup=False
    log(f'Logged in as {bot.user} (ID: {bot.user.id})')
    log('---------')


@bot.command(name='version', help='usage: faucet-version')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def version(ctx):
    await ctx.send('v1.1.0')


@bot.command(name='mainnet', help='usage: faucet-mainnet  [address]')
@commands.has_any_role(*MEMBER_DISCORD_ROLES)
async def mainnet_faucet(ctx, address: str):
    tokens = 0.01

    # if the user is too new to the guild
    # joined_delta = (datetime.now() - ctx.author.joined_at)
    # if joined_delta.days < 1 and joined_delta.seconds//3600 < 2:
    #     response = "Your account is too new to this guild. Please wait before requesting mainnet POL tokens."

    # if the address's balance already has enough POL, deny
    if faucet.get_balance(address) >= MAX_TOKENS_REQUESTED:
        response = "Address has greater than " + str(MAX_TOKENS_REQUESTED) + " POL."
        raw_audit_log(str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) + ") already has " +
                      str(faucet.get_faucet_balance()) + " tokens in their wallet.")

    # if the user or address has already the max tokens, deny
    elif DB_CHECK and (user_db.get_user_totals(ctx.author.id, address, "Mainnet") >= MAX_TOKENS_REQUESTED):
        log(str(tokens) + " excess tokens requested by " + str(ctx.author.id) + " author and " + str(
            address) + " address.")
        response = "You have already requested the maximum allowed."
        raw_audit_log(str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) +
                      ") requested too many tokens.")

    # if we do not have a good address
    elif not valid_address(address):
        response = "usage: `faucet-mainnet  [address]`. \n" \
                   "Please enter a valid address."
        raw_audit_log(str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) +
                      ") has an invalid address.")

    # if the address has 0 transactions, deny
    elif not user_db.get_if_existing_account(address):
        response = "Address must have activity/previous transactions before requesting."
        raw_audit_log(str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) + ") has 0 transactions.")

    # if the faucet does not have enough funds, deny
    elif faucet.get_faucet_balance() < (tokens + MAX_TOKENS_REQUESTED):
        response = "The faucet does not have enough funds. Please refill. cc:<@712863455467667526>\n" \
                   "`" + FAUCET_ADDRESS + "`"
        raw_audit_log(str(datetime.now()) + ": The faucet is out of funds.")

    elif address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif DB_CHECK and user_db.check_if_blacklisted(ctx.author.id, address):
        response = "User blacklisted."
        raw_audit_log(str(datetime.now()) + ": " + address + " is on the blacklist.")

    # if we passed all the above checks, proceed
    else:
        await ctx.send("The transaction has started and can take up to 2 minutes. Please wait until " +
                       "confirmation before requesting more.")

        success = faucet.send_faucet_transaction(address, tokens)

#        if success:
        if DB_CHECK:
            user_db.add_user(str(ctx.author.id), str(ctx.author))
            user_db.add_transaction(str(ctx.author.id), address, tokens, datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
                                    "Mainnet")
        response = "**Sent " + str(tokens) + " POL to " + address[:6] + "..." + \
                   address[-4:] + ".**\n" + \
                   thanks(FAUCET_ADDRESS)

#        else:
#            response = "The bot cannot confirm the transaction went through, please check on Polygonscan. " \
#                       "If still not received, try again. cc: <@712863455467667526>"

    # embed = discord.Embed()
    # embed.description = response
    await ctx.send(response)


@bot.command(name='mainnet-override', help='usage: faucet-override [address] [tokens]')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def mainnet_faucet_override(ctx, address: str, tokens=0.01):
    log('mainnet_faucet_override called')

    # if we have a good address
    if address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif valid_address(address):

        if faucet.get_faucet_balance() > (tokens + 0.01):
            await ctx.send("The transaction has started and can take up to 2 minutes.")

            success = faucet.send_faucet_transaction(address, tokens)
            if success:
                response = f"Sent {str(tokens)} POL to {address[:4]}...{address[-2:]}."
            else:
                response = "There was an error, please try again later or alert an admin."
        else:
            response = "The faucet does not have enough funds. Please refill. \n`{FAUCET_ADDRESS}`"
    else:
        response = "usage: `faucet  send  [address]  [tokens]`. \n" \
                   "Please enter a valid address."
    await ctx.send(response)


@mainnet_faucet.error
async def mainnet_faucet_error(ctx, error):
    error_channel = bot.get_channel(id=ERROR_MESSAGE_CHANNEL)
    if str(error) == "Command raised an exception: TypeError: string indices must be integers":
        await ctx.send("usage: `faucet-mainnet  [address]`. \n"
                       "Please do not use brackets when entering an address.")
        await error_channel.send("CommandInvokeError: \n" + str(error))
        raise error
    if isinstance(error, CommandInvokeError):
        await ctx.send("There was error that <@712863455467667526> needs to fix. Please try again later.")
        await error_channel.send("CommandInvokeError: \n" + str(error))
        raise error
    elif isinstance(error, BadArgument):
        await ctx.send("usage: `faucet-mainnet  [address]`. \n"
                       "Please enter a valid address.")
        await error_channel.send("BadArgument: \n" + str(error))
        raise error
    elif isinstance(error, MissingRequiredArgument):
        await ctx.send("usage: `faucet-mainnet  [address]`")
        await error_channel.send("MissingRequiredArgument: \n" + str(error))
        raise error
    elif isinstance(error, MissingAnyRole):
        await ctx.send(
            "You are missing at least one of the required roles: '" + ", ".join(MEMBER_DISCORD_ROLES) + "'.")
        await error_channel.send("MissingRole: \n" + str(error))
        raise error
    else:
        await error_channel.send("Else: \n" + str(error))
        raise error


@bot.command(name='balance', help='usage: faucet-balance')
@commands.has_any_role(*MEMBER_DISCORD_ROLES)
async def get_mainnet_balance(ctx):
    try:
        balance = faucet.get_faucet_balance()
        response = "The faucet has " + str(balance) + " POL. \n" \
                                                      "To contribute, you can send POL to `" + FAUCET_ADDRESS + "`."
        raw_audit_log(
            str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) + ") checked the balance.")
        await ctx.send(response)
    except Exception as e:
        log(e)


@bot.command(name='blacklist', help='usage: faucet-blacklist [address]')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def blacklist_address(ctx, address: str):
    if not DB_CHECK:
        await ctx.send("Database checks not enabled.")
    await ctx.send(user_db.add_blacklisted_address(ctx.author.id, address))
    log(address + " blacklisted.")
    return


@bot.command(name='amoy', help='usage: faucet-amoy [address]')
@commands.has_any_role(*DEVELOPER_DISCORD_ROLES)
async def amoy_faucet(ctx, address: str):
    log("amoy-faucet called")
    tokens = 5

    # if the faucet does not have enough funds, deny
    if faucet.get_amoy_balance() < (tokens + 0.1):
        response = "The faucet does not have enough funds. Please refill <@712863455467667526>. \n" \
                   "`" + FAUCET_ADDRESS + "`"
        raw_audit_log(str(datetime.now()) + ": The faucet is out of funds.")

    elif address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif DB_CHECK and user_db.check_if_blacklisted(ctx.author.id, address):
        response = "User blacklisted."
        raw_audit_log(str(datetime.now()) + ": " + address + " is on the blacklist.")

    # if the user has requested more than 100 POL, prevent the spam
    elif DB_CHECK and (user_db.get_user_totals(ctx.author.id, address, "Amoy") >= 250):
        response = "You have already requested 250 POL. Please ping <@712863455467667526> for more."

    # if we passed all the above checks, proceed
    elif valid_address(address):

        await ctx.send("The transaction has started and can take up to 2 minutes. Please wait until " +
                       "confirmation before requesting more.")

        success = faucet.send_amoy_faucet_transaction(address, tokens)

        # success = True
        if success:
            if DB_CHECK:
                user_db.add_transaction(str(ctx.author.id), address, tokens,
                                    datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), "Amoy")
            response = "**Sent " + str(tokens) + " amoy POL to " + address[:6] + "..." + \
                       address[-4:] + ".**"

        else:
            response = "The bot cannot confirm the transaction went through, please check on Polygonscan. " \
                       "If still not received, try again."

    else:
        response = "usage: `faucet-amoy  [address]`. \n" \
                   "Please enter a valid address."
    log("amoy-faucet: " + response)
    await ctx.send(response)
    return


@bot.command(name='amoy-override', help='usage: faucet-amoy-override [address] [tokens]')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def amoy_faucet_override(ctx, address: str, tokens=1):
    log('amoy_faucet_override called')

    # if we have a good address
    if address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif valid_address(address):

        if faucet.get_amoy_balance() > (tokens + 0.01):
            await ctx.send("The transaction has started and can take up to 2 minutes.")

            success = faucet.send_amoy_faucet_transaction(address, tokens)
            if success:
                response = "**Sent " + str(tokens) + " POL to " + address[:4] + "..." + address[-2:] + \
                           ". **The faucet now has " + str(faucet.get_amoy_balance()) + " POL left."
            else:
                response = "There was an error."
        else:
            response = f"The faucet does not have enough funds. Please refill.\n`{FAUCET_ADDRESS}`"
    else:
        response = "usage: `faucet  send  [address]  [tokens]`. \n" \
                   "Please enter a valid address."
    await ctx.send(response)


@bot.command(name='amoy-reset', help='usage: faucet-amoy-reset [address]')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def amoy_faucet_reset(ctx, user: str):
    print('amoy_faucet_reset called')

    response = f"Reset <@{user}>'s amoy POL limit. They can request 150 more POL."
    user_db.reset_amoy_amount(user)

    await ctx.send(response)


@bot.command(name='amoy-balance', help='usage: faucet-amoy-balance')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def get_amoy_balance(ctx):
    try:
        balance = faucet.get_amoy_balance()
        response = "The faucet has " + str(balance) + " testnet POL."
        await ctx.send(response)
    except Exception as e:
        log(e)


@amoy_faucet.error
async def amoy_faucet_error(ctx, error):
    if isinstance(error, CommandInvokeError):
        await ctx.send("There was an issue, possibly with the RPC.")
        raise error
    elif isinstance(error, MissingAnyRole):
        await ctx.send(
            "You are missing at least one of the required roles: '" + ", ".join(DEVELOPER_DISCORD_ROLES) + "'.")
        raise error
    elif isinstance(error, BadArgument):
        await ctx.send("usage: `faucet-amoy  [address]`. \n"
                       "Please enter a valid address.")
        raise error
    elif isinstance(error, MissingRequiredArgument):
        await ctx.send("usage: `faucet-amoy  [address]`")
        raise error
    else:
        log(error)
        raise error


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')


bot.run(token)
