@bot.command(name='mumbai', help='usage: faucet-mumbai [address]')
@commands.has_any_role(*DEVELOPER_DISCORD_ROLES)
async def mumbai_faucet(ctx, address: str):
    log("Mumbai-faucet called")
    tokens = 1

    # if the faucet does not have enough funds, deny
    if faucet.get_mumbai_balance() < (tokens + 0.1):
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

    # if the user has requested more than 50 POL, prevent the spam
    elif DB_CHECK and (user_db.get_user_totals(ctx.author.id, address, "Mumbai") >= 50):
        response = "You have already requested 50 POL. Please ping <@712863455467667526> for more."

    # if we passed all the above checks, proceed
    elif valid_address(address):

        await ctx.send("The transaction has started and can take up to 2 minutes. Please wait until " +
                       "confirmation before requesting more.")

        success = faucet.send_mumbai_faucet_transaction(address, tokens)

        # success = True
        if success:
            if DB_CHECK:
                user_db.add_transaction(str(ctx.author.id), address, tokens,
                                    datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), "Mumbai")
            response = "**Sent " + str(tokens) + " mumbai POL to " + address[:6] + "..." + \
                       address[-4:] + ".**"

        else:
            response = "The bot cannot confirm the transaction went through, please check on Polygonscan. " \
                       "If still not received, try again."

    else:
        response = "usage: `faucet-mumbai  [address]`. \n" \
                   "Please enter a valid address."
    log("Mumbai-faucet: " + response)
    await ctx.send(response)
    return


@bot.command(name='mumbai-override', help='usage: faucet-mumbai-override [address] [tokens]')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def mumbai_faucet_override(ctx, address: str, tokens=1):
    log('mumbai_faucet_override called')

    # if we have a good address
    if address == address.lower():
        response = "Your address appears to be in the wrong format. Please make sure your address has both upper- " \
                   "and lower-case letters. This can be found on Polygonscan, or your wallet."
        raw_audit_log(str(datetime.now()) + ": " + address + " was in the wrong format.")

    elif valid_address(address):

        if faucet.get_mumbai_balance() > (tokens + 0.01):
            await ctx.send("The transaction has started and can take up to 2 minutes.")

            success = faucet.send_mumbai_faucet_transaction(address, tokens)
            if success:
                response = "**Sent " + str(tokens) + " POL to " + address[:4] + "..." + address[-2:] + \
                           ". **The faucet now has " + str(faucet.get_mumbai_balance()) + " POL left."
            else:
                response = "There was an error."
        else:
            response = f"The faucet does not have enough funds. Please refill.\n`{FAUCET_ADDRESS}`"
    else:
        response = "usage: `faucet  send  [address]  [tokens]`. \n" \
                   "Please enter a valid address."
    await ctx.send(response)


@bot.command(name='mumbai-balance', help='usage: faucet-mumbai-balance')
@commands.has_any_role(*ADMIN_DISCORD_ROLES)
async def get_mumbai_balance(ctx):
    try:
        balance = faucet.get_mumbai_balance()
        response = "The faucet has " + str(balance) + " POLmum"
        await ctx.send(response)
    except Exception as e:
        log(e)


@mumbai_faucet.error
async def mumbai_faucet_error(ctx, error):
    if isinstance(error, CommandInvokeError):
        await ctx.send("There was an issue, possibly with the RPC.")
        raise error
    elif isinstance(error, MissingAnyRole):
        await ctx.send(
            "You are missing at least one of the required roles: '" + ", ".join(DEVELOPER_DISCORD_ROLES) + "'.")
        raise error
    elif isinstance(error, BadArgument):
        await ctx.send("usage: `faucet-mumbai  [address]  [tokens]`. \n"
                       "Please enter a valid address.")
        raise error
    elif isinstance(error, MissingRequiredArgument):
        await ctx.send("usage: `faucet-mumbai  [address]  [tokens]`")
        raise error
    else:
        log(error)
        raise error