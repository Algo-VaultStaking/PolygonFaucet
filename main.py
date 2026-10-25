import asyncio
from datetime import datetime

import discord
from discord import app_commands

import faucet
import user_db
import configparser
import json
from faucet import valid_address

from logger import log, raw_audit_log

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

MAX_TOKENS_REQUESTED = float(c["TOKEN COUNTS"]["MAX_TOKENS_REQUESTED"])
FAUCET_ADDRESS = str(c["FAUCET"]["address"])
DISCORD_TOKEN = str(c["DISCORD"]["token"])
MEMBER_DISCORD_ROLES = json.loads(c["DISCORD"]["member_roles"])
DEVELOPER_DISCORD_ROLES = json.loads(c["DISCORD"]["developer_roles"])
ADMIN_DISCORD_ROLES = json.loads(c["DISCORD"]["admin_roles"])
ERROR_MESSAGE_CHANNEL = int(c["DISCORD"]["error_channel"])
DB_CHECK = True if str(c["DATABASE"]["db_check"]).lower() == "true" else False

# Message content is only used to notice deprecated faucet- prefix messages.
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

_synced_guilds = set()
_sync_lock = asyncio.Lock()

SLASH_COMMANDS = {
    "faucet-mainnet": "/faucet-mainnet",
    "faucet-mainnet-override": "/faucet-mainnet-override",
    "faucet-balance": "/faucet-balance",
    "faucet-blacklist": "/faucet-blacklist",
    "faucet-amoy": "/faucet-amoy",
    "faucet-amoy-override": "/faucet-amoy-override",
    "faucet-amoy-reset": "/faucet-amoy-reset",
    "faucet-amoy-balance": "/faucet-amoy-balance",
    "faucet-version": "/faucet-version",
}


def thanks(addr):
    return "If you found this faucet helpful, please consider returning funds to `" \
           + addr + "`. It will help keep the faucet running. Thank you!"


async def send_interaction(interaction, content):
    if interaction.response.is_done():
        await interaction.followup.send(content)
    else:
        await interaction.response.send_message(content)


async def report_error(label, error):
    channel = client.get_channel(ERROR_MESSAGE_CHANNEL)
    if channel is None:
        try:
            channel = await client.fetch_channel(ERROR_MESSAGE_CHANNEL)
        except Exception as e:
            log(e)
            return
    await channel.send(label + ": \n" + str(error))


async def sync_guild_commands(guild):
    async with _sync_lock:
        if guild.id in _synced_guilds:
            return
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        _synced_guilds.add(guild.id)
        log("Synced slash commands to " + guild.name + " (" + str(guild.id) + ")")


@client.event
async def on_ready():
    log(f'Logged in as {client.user} (ID: {client.user.id})')
    log('---------')
    for guild in client.guilds:
        try:
            await sync_guild_commands(guild)
        except Exception as e:
            log("Command sync failed for " + str(guild.id) + ": " + str(e))


@client.event
async def on_guild_join(guild):
    try:
        await sync_guild_commands(guild)
    except Exception as e:
        log("Command sync failed for " + str(guild.id) + ": " + str(e))


@client.event
async def on_message(message):
    if message.author.bot or not message.content:
        return
    content = message.content.strip()
    if not content.lower().startswith("faucet-"):
        return
    command_name = content.split(maxsplit=1)[0].lower()
    replacement = SLASH_COMMANDS.get(command_name)
    if replacement:
        hint = "Use `" + replacement + "` instead."
    else:
        choices = ", ".join("`" + name + "`" for name in SLASH_COMMANDS.values())
        hint = "Use slash commands instead: " + choices + "."
    await message.channel.send("The `faucet-` commands have been deprecated. " + hint)


@tree.command(name="faucet-version", description="Print the bot version.")
@app_commands.guild_only()
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def version(interaction: discord.Interaction):
    await interaction.response.send_message("v1.1.0")


@tree.command(name="faucet-mainnet", description="Send 0.01 POL on Polygon mainnet.")
@app_commands.guild_only()
@app_commands.describe(address="Wallet address")
@app_commands.checks.has_any_role(*MEMBER_DISCORD_ROLES)
async def mainnet_faucet(interaction: discord.Interaction, address: str):
    await interaction.response.defer()
    tokens = 0.01
    author = interaction.user

    # if the user is too new to the guild
    # joined_delta = (datetime.now() - ctx.author.joined_at)
    # if joined_delta.days < 1 and joined_delta.seconds//3600 < 2:
    #     response = "Your account is too new to this guild. Please wait before requesting mainnet POL tokens."

    balance = await asyncio.to_thread(faucet.get_balance, address)
    # if the address's balance already has enough POL, deny
    if balance >= MAX_TOKENS_REQUESTED:
        response = "Address has greater than " + str(MAX_TOKENS_REQUESTED) + " POL."
        faucet_balance = await asyncio.to_thread(faucet.get_faucet_balance)
        raw_audit_log(str(datetime.now()) + ": " + str(author) + "(" + str(author.id) + ") already has " +
                      str(faucet_balance) + " tokens in their wallet.")

    # if the user or address has already the max tokens, deny
    elif DB_CHECK and (await asyncio.to_thread(user_db.get_user_totals, author.id, address, "Mainnet") >= MAX_TOKENS_REQUESTED):
        log(str(tokens) + " excess tokens requested by " + str(author.id) + " author and " + str(
            address) + " address.")
        response = "You have already requested the maximum allowed."
        raw_audit_log(str(datetime.now()) + ": " + str(author) + "(" + str(author.id) +
                      ") requested too many tokens.")

    # if we do not have a good address
    elif not valid_address(address):
        response = "usage: `/faucet-mainnet` `[address]`. \n" \
                   "Please enter a valid address."
        raw_audit_log(str(datetime.now()) + ": " + str(author) + "(" + str(author.id) +
                      ") has an invalid address.")

    # if the address has 0 transactions, deny
    #elif not user_db.get_if_existing_account(address):
    #    response = "Address must have activity/previous transactions before requesting."
    #    raw_audit_log(str(datetime.now()) + ": " + str(ctx.author) + "(" + str(ctx.author.id) + ") has 0 transactions.")

    # if the faucet does not have enough funds, deny
    elif await asyncio.to_thread(faucet.get_faucet_balance) < (tokens + MAX_TOKENS_REQUESTED):
        response = "The faucet does not have enough funds. Please refill. cc:<@712863455467667526>\n" \
                   "`" + FAUCET_ADDRESS + "`"
        raw_audit_log(str(datetime.now()) + ": The faucet is out of funds.")

    elif address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    #elif DB_CHECK and user_db.check_if_blacklisted(ctx.author.id, address):
    #    response = "User blacklisted."
    #    raw_audit_log(str(datetime.now()) + ": " + address + " is on the blacklist.")

    # if we passed all the above checks, proceed
    else:
        await interaction.edit_original_response(content="The transaction has started and can take up to 2 minutes. Please wait until " +
                       "confirmation before requesting more.")

        success = await asyncio.to_thread(faucet.send_faucet_transaction, address, tokens)

        if success:
            if DB_CHECK:
                await asyncio.to_thread(user_db.add_user, str(author.id), str(author))
                await asyncio.to_thread(user_db.add_transaction, str(author.id), address, tokens,
                                        datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), "Mainnet")
            response = "**Sent " + str(tokens) + " POL to " + address[:6] + "..." + \
                       address[-4:] + ".**\n" + \
                       thanks(FAUCET_ADDRESS)

        else:
            response = "The bot cannot confirm the transaction went through, please check on Polygonscan. " \
                       "If still not received, try again. cc: <@712863455467667526>"
        await interaction.followup.send(response)
        return

    await interaction.edit_original_response(content=response)


@tree.command(name="faucet-mainnet-override", description="Send a custom amount of mainnet POL.")
@app_commands.guild_only()
@app_commands.describe(address="Wallet address", tokens="Amount of POL to send")
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def mainnet_faucet_override(interaction: discord.Interaction, address: str, tokens: float = 0.01):
    await interaction.response.defer()
    log('mainnet_faucet_override called')

    # if we have a good address
    if address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif valid_address(address):

        if await asyncio.to_thread(faucet.get_faucet_balance) > (tokens + 0.01):
            await interaction.edit_original_response(content="The transaction has started and can take up to 2 minutes.")

            success = await asyncio.to_thread(faucet.send_faucet_transaction, address, tokens)
            if success:
                response = f"Sent {str(tokens)} POL to {address[:4]}...{address[-2:]}."
            else:
                response = "There was an error, please try again later or alert an admin."
            await interaction.followup.send(response)
            return
        else:
            response = "The faucet does not have enough funds. Please refill. \n`{FAUCET_ADDRESS}`"
    else:
        response = "usage: `/faucet-mainnet-override` `[address]` `[tokens]`. \n" \
                   "Please enter a valid address."
    await interaction.edit_original_response(content=response)


@mainnet_faucet.error
async def mainnet_faucet_error(interaction, error):
    original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
    if isinstance(original, TypeError) and "string indices must be integers" in str(original):
        await send_interaction(interaction, "usage: `/faucet-mainnet` `[address]`. \n"
                       "Please do not use brackets when entering an address.")
        await report_error("CommandInvokeError", error)
        return
    if isinstance(error, app_commands.CommandInvokeError):
        await send_interaction(interaction, "There was error that <@712863455467667526> needs to fix. Please try again later.")
        await report_error("CommandInvokeError", error)
        return
    elif isinstance(error, app_commands.TransformerError):
        await send_interaction(interaction, "usage: `/faucet-mainnet` `[address]`. \n"
                       "Please enter a valid address.")
        await report_error("BadArgument", error)
        return
    elif isinstance(error, app_commands.MissingAnyRole):
        await send_interaction(interaction,
            "You are missing at least one of the required roles: '" + ", ".join(MEMBER_DISCORD_ROLES) + "'.")
        await report_error("MissingRole", error)
        return
    else:
        await send_interaction(interaction, "There was error that <@712863455467667526> needs to fix. Please try again later.")
        await report_error("Else", error)


@tree.command(name="faucet-balance", description="Show the mainnet faucet balance.")
@app_commands.guild_only()
@app_commands.checks.has_any_role(*MEMBER_DISCORD_ROLES)
async def get_mainnet_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        balance = await asyncio.to_thread(faucet.get_faucet_balance)
        response = "The faucet has " + str(balance) + " POL. \n" \
                                                      "To contribute, you can send POL to `" + FAUCET_ADDRESS + "`."
        raw_audit_log(
            str(datetime.now()) + ": " + str(interaction.user) + "(" + str(interaction.user.id) + ") checked the balance.")
        await interaction.edit_original_response(content=response)
    except Exception as e:
        log(e)
        await interaction.edit_original_response(content="There was an error reading the faucet balance.")


@tree.command(name="faucet-blacklist", description="Blacklist a wallet address.")
@app_commands.guild_only()
@app_commands.describe(address="Wallet address")
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def blacklist_address(interaction: discord.Interaction, address: str):
    await interaction.response.defer()
    if not DB_CHECK:
        await interaction.edit_original_response(content="Database checks not enabled.")
        result = await asyncio.to_thread(user_db.add_blacklisted_address, interaction.user.id, address)
        await interaction.followup.send(result)
    else:
        result = await asyncio.to_thread(user_db.add_blacklisted_address, interaction.user.id, address)
        await interaction.edit_original_response(content=result)
    log(address + " blacklisted.")


@tree.command(name="faucet-amoy", description="Send 5 POL on Amoy testnet.")
@app_commands.guild_only()
@app_commands.describe(address="Wallet address")
@app_commands.checks.has_any_role(*DEVELOPER_DISCORD_ROLES)
async def amoy_faucet(interaction: discord.Interaction, address: str):
    await interaction.response.defer()
    log("amoy-faucet called")
    tokens = 5
    author = interaction.user

    # if the faucet does not have enough funds, deny
    if await asyncio.to_thread(faucet.get_amoy_balance) < (tokens + 0.1):
        response = "The faucet does not have enough funds. Please refill <@712863455467667526>. \n" \
                   "`" + FAUCET_ADDRESS + "`"
        raw_audit_log(str(datetime.now()) + ": The faucet is out of funds.")

    elif address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif DB_CHECK and await asyncio.to_thread(user_db.check_if_blacklisted, author.id, address):
        response = "User blacklisted."
        raw_audit_log(str(datetime.now()) + ": " + address + " is on the blacklist.")

    # if the user has requested more than 100 POL, prevent the spam
    elif DB_CHECK and (await asyncio.to_thread(user_db.get_user_totals, author.id, address, "Amoy") >= 250):
        response = "You have already requested 250 POL. Please ping <@712863455467667526> for more."

    # if we passed all the above checks, proceed
    elif valid_address(address):

        await interaction.edit_original_response(content="The transaction has started and can take up to 2 minutes. Please wait until " +
                       "confirmation before requesting more.")

        success = await asyncio.to_thread(faucet.send_amoy_faucet_transaction, address, tokens)

        if success:
            if DB_CHECK:
                await asyncio.to_thread(user_db.add_transaction, str(author.id), address, tokens,
                                    datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), "Amoy")
            response = "**Sent " + str(tokens) + " amoy POL to " + address[:6] + "..." + \
                       address[-4:] + ".**"

        else:
            response = "The bot cannot confirm the transaction went through, please check on Polygonscan. " \
                       "If still not received, try again."
        log("amoy-faucet: " + response)
        await interaction.followup.send(response)
        return

    else:
        response = "usage: `/faucet-amoy` `[address]`. \n" \
                   "Please enter a valid address."
    log("amoy-faucet: " + response)
    await interaction.edit_original_response(content=response)


@tree.command(name="faucet-amoy-override", description="Send a custom amount of Amoy POL.")
@app_commands.guild_only()
@app_commands.describe(address="Wallet address", tokens="Amount of POL to send")
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def amoy_faucet_override(interaction: discord.Interaction, address: str, tokens: float = 1.0):
    await interaction.response.defer()
    log('amoy_faucet_override called')

    # if we have a good address
    if address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif valid_address(address):

        if await asyncio.to_thread(faucet.get_amoy_balance) > (tokens + 0.01):
            await interaction.edit_original_response(content="The transaction has started and can take up to 2 minutes.")

            success = await asyncio.to_thread(faucet.send_amoy_faucet_transaction, address, tokens)
            if success:
                remaining = await asyncio.to_thread(faucet.get_amoy_balance)
                response = "**Sent " + str(tokens) + " POL to " + address[:4] + "..." + address[-2:] + \
                           ". **The faucet now has " + str(remaining) + " POL left."
            else:
                response = "There was an error."
            await interaction.followup.send(response)
            return
        else:
            response = f"The faucet does not have enough funds. Please refill.\n`{FAUCET_ADDRESS}`"
    else:
        response = "usage: `/faucet-amoy-override` `[address]` `[tokens]`. \n" \
                   "Please enter a valid address."
    await interaction.edit_original_response(content=response)


@tree.command(name="faucet-amoy-reset", description="Reset a user's Amoy request cap.")
@app_commands.guild_only()
@app_commands.describe(user="Discord user id")
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def amoy_faucet_reset(interaction: discord.Interaction, user: str):
    await interaction.response.defer()
    print('amoy_faucet_reset called')

    response = f"Reset <@{user}>'s amoy POL limit. They can request 150 more POL."
    await asyncio.to_thread(user_db.reset_amoy_amount, user)

    await interaction.edit_original_response(content=response)


@tree.command(name="faucet-amoy-balance", description="Show the Amoy faucet balance.")
@app_commands.guild_only()
@app_commands.checks.has_any_role(*ADMIN_DISCORD_ROLES)
async def get_amoy_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        balance = await asyncio.to_thread(faucet.get_amoy_balance)
        response = "The faucet has " + str(balance) + " testnet POL."
        await interaction.edit_original_response(content=response)
    except Exception as e:
        log(e)
        await interaction.edit_original_response(content="There was an error reading the Amoy faucet balance.")


@amoy_faucet.error
async def amoy_faucet_error(interaction, error):
    if isinstance(error, app_commands.CommandInvokeError):
        await send_interaction(interaction, "There was an issue, possibly with the RPC.")
        return
    elif isinstance(error, app_commands.MissingAnyRole):
        await send_interaction(interaction,
            "You are missing at least one of the required roles: '" + ", ".join(DEVELOPER_DISCORD_ROLES) + "'.")
        return
    elif isinstance(error, app_commands.TransformerError):
        await send_interaction(interaction, "usage: `/faucet-amoy` `[address]`. \n"
                       "Please enter a valid address.")
        return
    else:
        log(error)
        await send_interaction(interaction, "There was an issue, possibly with the RPC.")


@tree.error
async def on_app_command_error(interaction, error):
    command = interaction.command
    if isinstance(command, app_commands.Command) and command.on_error is not None:
        return
    if isinstance(error, app_commands.CheckFailure):
        await send_interaction(interaction, "You do not have the correct role for this command.")
        return
    if isinstance(error, app_commands.TransformerError):
        name = command.name if command is not None else "command"
        await send_interaction(interaction, "usage: `/" + name + "`.\nPlease check the command options.")
        return
    log(error)
    await send_interaction(interaction, "There was error that <@712863455467667526> needs to fix. Please try again later.")


client.run(DISCORD_TOKEN)
