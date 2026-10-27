"""Legacy `faucet-` message commands.

Slash commands are the replacement. These message commands keep working and
warn that they will be deprecated in early November.
"""

COMMANDS = {
    "faucet-mainnet": {
        "roles": "member",
        "usage": "faucet-mainnet [address]",
        "args": [("address", "str", True)],
    },
    "faucet-mainnet-override": {
        "roles": "admin",
        "usage": "faucet-mainnet-override [address] [tokens]",
        "args": [("address", "str", True), ("tokens", "float", False)],
    },
    "faucet-balance": {
        "roles": "member",
        "usage": "faucet-balance",
        "args": [],
    },
    "faucet-blacklist": {
        "roles": "admin",
        "usage": "faucet-blacklist [address]",
        "args": [("address", "str", True)],
    },
    "faucet-amoy": {
        "roles": "developer",
        "usage": "faucet-amoy [address]",
        "args": [("address", "str", True)],
    },
    "faucet-amoy-override": {
        "roles": "admin",
        "usage": "faucet-amoy-override [address] [tokens]",
        "args": [("address", "str", True), ("tokens", "float", False)],
    },
    "faucet-amoy-reset": {
        "roles": "admin",
        "usage": "faucet-amoy-reset [user]",
        "args": [("user", "str", True)],
    },
    "faucet-amoy-balance": {
        "roles": "admin",
        "usage": "faucet-amoy-balance",
        "args": [],
    },
    "faucet-version": {
        "roles": "admin",
        "usage": "faucet-version",
        "args": [],
    },
}

SERVER_ONLY = "This command only works in a server."
COMMAND_ERROR = "There was error that <@712863455467667526> needs to fix. Please try again later."


def deprecation_warning(command_name=None):
    base = "The `faucet-` commands will be deprecated in early November."
    if command_name in COMMANDS:
        return base + " Please switch to `/" + command_name + "`."
    names = ", ".join("`/" + name + "`" for name in COMMANDS)
    return base + " Please switch to slash commands: " + names + "."


def missing_role_message(command_name, member_roles, developer_roles):
    if command_name == "faucet-mainnet":
        return "You are missing at least one of the required roles: '" + ", ".join(member_roles) + "'."
    if command_name == "faucet-amoy":
        return "You are missing at least one of the required roles: '" + ", ".join(developer_roles) + "'."
    return "You do not have the correct role for this command."


def member_has_any_role(member, role_names):
    roles = getattr(member, "roles", None)
    if not roles:
        return False
    held = set()
    for role in roles:
        name = getattr(role, "name", None)
        if name is not None:
            held.add(name)
        role_id = getattr(role, "id", None)
        if role_id is not None:
            held.add(role_id)
    return any(required in held for required in role_names)


def parse_invocation(content):
    """Parse a message into a faucet- command.

    Returns None when the message is not a faucet- command. Otherwise returns
    a dict with command, args, error, and warning. Optional arguments that
    were omitted are left out of args so the slash-command default applies.
    """
    if not content:
        return None
    stripped = content.strip()
    if not stripped.lower().startswith("faucet-"):
        return None

    parts = stripped.split()
    command_name = parts[0].lower()
    raw_args = parts[1:]
    known = command_name in COMMANDS
    warning = deprecation_warning(command_name if known else None)
    if not known:
        return {"command": None, "args": None, "error": warning, "warning": warning}

    spec = COMMANDS[command_name]
    parsed = {}
    for index, (name, kind, required) in enumerate(spec["args"]):
        if index >= len(raw_args):
            if required:
                return {
                    "command": command_name,
                    "args": None,
                    "error": "usage: `" + spec["usage"] + "`",
                    "warning": warning,
                }
            continue
        value = raw_args[index]
        if kind == "float":
            try:
                parsed[name] = float(value)
            except ValueError:
                return {
                    "command": command_name,
                    "args": None,
                    "error": "usage: `" + spec["usage"] + "`\nPlease enter a valid amount.",
                    "warning": warning,
                }
        else:
            parsed[name] = value
    return {"command": command_name, "args": parsed, "error": None, "warning": warning}


class PrefixReply:
    """Stand-in interaction so a slash-command callback can answer a message."""

    def __init__(self, message):
        self.user = message.author
        self.guild = message.guild
        self.channel = message.channel
        self.command = None
        self.response = _PrefixResponse(self)
        self.followup = _PrefixFollowup(self)
        self._sent = None

    async def edit_original_response(self, *, content=None, **kwargs):
        if content is None:
            content = kwargs.get("content")
        if self._sent is None:
            self._sent = await self.channel.send(content)
            return self._sent
        await self._sent.edit(content=content)
        return self._sent


class _PrefixResponse:
    def __init__(self, reply):
        self._reply = reply

    def is_done(self):
        return self._reply._sent is not None

    async def defer(self, *args, **kwargs):
        return None

    async def send_message(self, content, **kwargs):
        self._reply._sent = await self._reply.channel.send(content)
        return self._reply._sent


class _PrefixFollowup:
    def __init__(self, reply):
        self._reply = reply

    async def send(self, content, **kwargs):
        return await self._reply.channel.send(content)


async def dispatch_prefix(message, callbacks, has_role, missing_role_text, on_error):
    author = getattr(message, "author", None)
    if author is not None and getattr(author, "bot", False):
        return
    parsed = parse_invocation(getattr(message, "content", None) or "")
    if parsed is None:
        return

    await message.channel.send(parsed["warning"])
    if parsed["error"]:
        if parsed["error"] != parsed["warning"]:
            await message.channel.send(parsed["error"])
        return
    if getattr(message, "guild", None) is None:
        await message.channel.send(SERVER_ONLY)
        return

    command_name = parsed["command"]
    spec = COMMANDS[command_name]
    if not has_role(message.author, spec["roles"]):
        await message.channel.send(missing_role_text(command_name))
        return

    reply = PrefixReply(message)
    try:
        await callbacks[command_name](reply, **parsed["args"])
    except Exception as error:
        try:
            await on_error(error)
        finally:
            await message.channel.send(COMMAND_ERROR)
