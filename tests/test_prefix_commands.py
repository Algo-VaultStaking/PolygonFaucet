import asyncio
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import prefix_commands


ADDRESS = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
LOWER_ADDRESS = ADDRESS.lower()


class Role:
    def __init__(self, name, role_id=None):
        self.name = name
        self.id = role_id


class Author:
    def __init__(self, role_names, bot=False):
        self.roles = [Role(name) for name in role_names]
        self.bot = bot
        self.id = 99

    def __str__(self):
        return "tester#0001"


class Sent:
    def __init__(self, content):
        self.content = content

    async def edit(self, content=None, **kwargs):
        if content is not None:
            self.content = content


class Channel:
    def __init__(self):
        self.messages = []

    async def send(self, content, **kwargs):
        sent = Sent(content)
        self.messages.append(sent)
        return sent


class FakeMessage:
    def __init__(self, content, role_names=(), guild=True, bot=False):
        self.content = content
        self.author = Author(role_names, bot=bot)
        self.channel = Channel()
        self.guild = object() if guild else None


def contents(message):
    return [sent.content for sent in message.channel.messages]


class ParseTests(unittest.TestCase):
    def test_ignores_other_messages(self):
        self.assertIsNone(prefix_commands.parse_invocation("hello faucet-mainnet"))
        self.assertIsNone(prefix_commands.parse_invocation(""))
        self.assertIsNone(prefix_commands.parse_invocation(None))

    def test_parses_address_without_changing_case(self):
        parsed = prefix_commands.parse_invocation("  FaUcEt-Mainnet   " + ADDRESS + "  ")
        self.assertEqual(parsed["command"], "faucet-mainnet")
        self.assertEqual(parsed["args"], {"address": ADDRESS})
        self.assertIsNone(parsed["error"])
        self.assertIn("early November", parsed["warning"])
        self.assertIn("/faucet-mainnet", parsed["warning"])
        self.assertNotIn("have been deprecated", parsed["warning"])

    def test_optional_amount_is_omitted_when_absent(self):
        parsed = prefix_commands.parse_invocation("faucet-amoy-override " + ADDRESS)
        self.assertEqual(parsed["args"], {"address": ADDRESS})

    def test_parses_amount_and_ignores_extra_words(self):
        parsed = prefix_commands.parse_invocation(
            "faucet-mainnet-override " + ADDRESS + " 2.5 leftover")
        self.assertEqual(parsed["args"]["tokens"], 2.5)
        self.assertNotIn("leftover", parsed["args"])

    def test_missing_address_returns_prefix_usage(self):
        parsed = prefix_commands.parse_invocation("faucet-mainnet")
        self.assertIn("usage: `faucet-mainnet [address]`", parsed["error"])
        self.assertIn("early November", parsed["warning"])

    def test_bad_amount(self):
        parsed = prefix_commands.parse_invocation("faucet-amoy-override " + ADDRESS + " many")
        self.assertIn("valid amount", parsed["error"])

    def test_unknown_command_lists_slash_commands(self):
        parsed = prefix_commands.parse_invocation("faucet-help")
        self.assertIsNone(parsed["command"])
        self.assertIn("early November", parsed["warning"])
        self.assertIn("/faucet-amoy", parsed["warning"])
        self.assertEqual(parsed["error"], parsed["warning"])

    def test_role_match_is_exact(self):
        member = Author(["Community"])
        self.assertTrue(prefix_commands.member_has_any_role(member, ["Community", "Admin"]))
        self.assertFalse(prefix_commands.member_has_any_role(member, ["community"]))
        self.assertFalse(prefix_commands.member_has_any_role(Author([]), ["Community"]))

    def test_role_messages_match_slash_handlers(self):
        self.assertIn(
            "Community",
            prefix_commands.missing_role_message("faucet-mainnet", ["Community"], ["Developer"]))
        self.assertIn(
            "Developer",
            prefix_commands.missing_role_message("faucet-amoy", ["Community"], ["Developer"]))
        self.assertEqual(
            "You do not have the correct role for this command.",
            prefix_commands.missing_role_message("faucet-version", ["Community"], ["Developer"]))


class DispatchTests(unittest.TestCase):
    def test_runs_callback_after_warning(self):
        seen = {}

        async def version(interaction):
            seen["user"] = interaction.user
            await interaction.response.send_message("v1.1.0")

        async def run():
            message = FakeMessage("faucet-version", ["Admin"])
            await prefix_commands.dispatch_prefix(
                message,
                {"faucet-version": version},
                lambda member, group: True,
                lambda command_name: "no role",
                self.fail,
            )
            return message

        message = asyncio.run(run())
        self.assertIn("early November", contents(message)[0])
        self.assertEqual(contents(message)[1], "v1.1.0")
        self.assertIs(seen["user"], message.author)

    def test_transaction_replies_stay_separate_from_warning(self):
        async def mainnet(interaction, address):
            await interaction.response.defer()
            await interaction.edit_original_response(content="started " + address)
            await interaction.followup.send("sent")

        async def run():
            message = FakeMessage("faucet-mainnet " + ADDRESS, ["Community"])
            await prefix_commands.dispatch_prefix(
                message,
                {"faucet-mainnet": mainnet},
                lambda member, group: group == "member",
                lambda command_name: "no role",
                self.fail,
            )
            return message

        message = asyncio.run(run())
        self.assertEqual(
            contents(message),
            [
                prefix_commands.deprecation_warning("faucet-mainnet"),
                "started " + ADDRESS,
                "sent",
            ],
        )

    def test_missing_role_does_not_run_command(self):
        async def should_not_run(interaction, address):
            raise AssertionError("command ran")

        async def run():
            message = FakeMessage("faucet-mainnet " + ADDRESS, ["Guest"])
            await prefix_commands.dispatch_prefix(
                message,
                {"faucet-mainnet": should_not_run},
                lambda member, group: False,
                lambda command_name: "missing " + command_name,
                self.fail,
            )
            return message

        message = asyncio.run(run())
        self.assertEqual(contents(message)[1], "missing faucet-mainnet")

    def test_direct_message_does_not_run_command(self):
        async def should_not_run(interaction):
            raise AssertionError("command ran")

        async def run():
            message = FakeMessage("faucet-version", ["Admin"], guild=False)
            await prefix_commands.dispatch_prefix(
                message,
                {"faucet-version": should_not_run},
                lambda member, group: True,
                lambda command_name: "no role",
                self.fail,
            )
            return message

        message = asyncio.run(run())
        self.assertIn(prefix_commands.SERVER_ONLY, contents(message))

    def test_callback_error_is_reported(self):
        reported = []

        async def boom(interaction):
            raise RuntimeError("rpc down")

        async def on_error(error):
            reported.append(str(error))

        async def run():
            message = FakeMessage("faucet-balance", ["Community"])
            await prefix_commands.dispatch_prefix(
                message,
                {"faucet-balance": boom},
                lambda member, group: True,
                lambda command_name: "no role",
                on_error,
            )
            return message

        message = asyncio.run(run())
        self.assertEqual(reported, ["rpc down"])
        self.assertEqual(contents(message)[-1], prefix_commands.COMMAND_ERROR)

    def test_bot_and_plain_text_are_ignored(self):
        async def run():
            bot_message = FakeMessage("faucet-version", ["Admin"], bot=True)
            plain = FakeMessage("hello", ["Admin"])
            await prefix_commands.dispatch_prefix(
                bot_message, {}, lambda *args: True, lambda command_name: "", self.fail)
            await prefix_commands.dispatch_prefix(
                plain, {}, lambda *args: True, lambda command_name: "", self.fail)
            return bot_message, plain

        bot_message, plain = asyncio.run(run())
        self.assertEqual(contents(bot_message), [])
        self.assertEqual(contents(plain), [])


def _install_import_stubs():
    faucet = types.ModuleType("faucet")

    def valid_address(address):
        return (
            isinstance(address, str)
            and len(address) == 42
            and address.startswith("0x")
            and "[" not in address
        )

    faucet.valid_address = valid_address
    faucet.get_balance = lambda address: 0.0
    faucet.get_faucet_balance = lambda: 10.0
    faucet.get_amoy_balance = lambda: 100.0
    faucet.send_faucet_transaction = lambda address, tokens: True
    faucet.send_amoy_faucet_transaction = lambda address, tokens: True
    sys.modules["faucet"] = faucet

    user_db = types.ModuleType("user_db")
    user_db.get_user_totals = lambda *args, **kwargs: 0
    user_db.add_user = lambda *args, **kwargs: None
    user_db.add_transaction = lambda *args, **kwargs: None
    user_db.add_blacklisted_address = lambda user_id, address: "blacklisted " + address
    user_db.check_if_blacklisted = lambda *args, **kwargs: False
    user_db.reset_amoy_amount = lambda user: None
    sys.modules["user_db"] = user_db
    return faucet, user_db


class MainPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cwd = os.getcwd()
        cls._tmpdir = tempfile.TemporaryDirectory()
        config = """\
[GENERAL]
audit_log = /tmp/faucet-audit.txt
api_key = test

[TOKEN COUNTS]
MAX_TOKENS_REQUESTED = 0.02
MAX_AMOY_TOKENS_REQUESTED = 5

[FAUCET]
address = 0x0000000000000000000000000000000000000001
private_key = test-key

[RPC]
mainnet = https://polygon-rpc.com
amoy = https://rpc-amoy.polygon.technology

[DISCORD]
token = test-token
member_roles = ["Community"]
developer_roles = ["Developer"]
admin_roles = ["Admin"]
error_channel = 123

[DATABASE]
db_check = false
user =
password =
host =
name =
"""
        os.chdir(cls._tmpdir.name)
        with open("config.ini", "w", encoding="utf-8") as handle:
            handle.write(config)
        cls.faucet, cls.user_db = _install_import_stubs()
        import main
        cls.main = main

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cwd)
        cls._tmpdir.cleanup()

    def setUp(self):
        self.sent = []
        self.amoy_sent = []
        self.blacklisted = []
        self.resets = []

        def send_mainnet(address, tokens):
            self.sent.append((address, tokens))
            return True

        def send_amoy(address, tokens):
            self.amoy_sent.append((address, tokens))
            return True

        def blacklist(user_id, address):
            self.blacklisted.append((user_id, address))
            return "blacklisted " + address

        def reset(user):
            self.resets.append(user)

        self.faucet.get_balance = lambda address: 0.0
        self.faucet.get_faucet_balance = lambda: 10.0
        self.faucet.get_amoy_balance = lambda: 100.0
        self.faucet.send_faucet_transaction = send_mainnet
        self.faucet.send_amoy_faucet_transaction = send_amoy
        self.user_db.add_blacklisted_address = blacklist
        self.user_db.reset_amoy_amount = reset
        self.main.report_error = self._capture_report
        self.reported = []

    async def _capture_report(self, label, error):
        self.reported.append((label, str(error)))

    def _run(self, message):
        asyncio.run(self.main.on_message(message))
        return contents(message)

    def test_slash_commands_are_still_registered(self):
        names = sorted(command.name for command in self.main.tree.get_commands())
        self.assertEqual(names, sorted(prefix_commands.COMMANDS))

    def test_prefix_callbacks_cover_every_command(self):
        self.assertEqual(set(self.main.PREFIX_CALLBACKS), set(prefix_commands.COMMANDS))

    def test_version_runs_for_admin(self):
        replied = self._run(FakeMessage("faucet-version", ["Admin"]))
        self.assertIn("early November", replied[0])
        self.assertIn("/faucet-version", replied[0])
        self.assertEqual(replied[1], "v1.1.0")

    def test_version_role_denial(self):
        replied = self._run(FakeMessage("faucet-version", ["Community"]))
        self.assertEqual(replied[1], "You do not have the correct role for this command.")
        self.assertNotIn("v1.1.0", replied)

    def test_mainnet_sends_after_warning(self):
        replied = self._run(FakeMessage("faucet-mainnet " + ADDRESS, ["Community"]))
        self.assertIn("early November", replied[0])
        self.assertIn("transaction has started", replied[1])
        self.assertIn("Sent 0.01 POL", replied[2])
        self.assertEqual(self.sent, [(ADDRESS, 0.01)])

    def test_lowercase_address_is_rejected_without_sending(self):
        replied = self._run(FakeMessage("faucet-mainnet " + LOWER_ADDRESS, ["Community"]))
        self.assertIn("wrong format", replied[1])
        self.assertEqual(self.sent, [])

    def test_mainnet_missing_role_names_community(self):
        replied = self._run(FakeMessage("faucet-mainnet " + ADDRESS, ["Admin"]))
        self.assertIn("Community", replied[1])
        self.assertEqual(self.sent, [])

    def test_missing_argument_does_not_send(self):
        replied = self._run(FakeMessage("faucet-amoy", ["Developer"]))
        self.assertIn("usage: `faucet-amoy [address]`", replied[1])
        self.assertEqual(self.amoy_sent, [])

    def test_amoy_sends_five_pol(self):
        replied = self._run(FakeMessage("faucet-amoy " + ADDRESS, ["Developer"]))
        self.assertIn("early November", replied[0])
        self.assertIn("/faucet-amoy", replied[0])
        self.assertTrue(any("Sent 5 amoy POL" in line for line in replied))
        self.assertEqual(self.amoy_sent, [(ADDRESS, 5)])

    def test_amoy_override_default_amount(self):
        replied = self._run(FakeMessage("faucet-amoy-override " + ADDRESS, ["Admin"]))
        self.assertTrue(any("Sent 1.0 POL" in line or "Sent 1 POL" in line for line in replied))
        self.assertEqual(self.amoy_sent, [(ADDRESS, 1.0)])

    def test_mainnet_override_custom_amount(self):
        replied = self._run(FakeMessage("faucet-mainnet-override " + ADDRESS + " 0.2", ["Admin"]))
        self.assertTrue(any("Sent 0.2 POL" in line for line in replied))
        self.assertEqual(self.sent, [(ADDRESS, 0.2)])

    def test_balance(self):
        replied = self._run(FakeMessage("faucet-balance", ["Community"]))
        self.assertIn("The faucet has 10.0 POL", replied[1])

    def test_blacklist_and_reset(self):
        blacklisted = self._run(FakeMessage("faucet-blacklist " + ADDRESS, ["Admin"]))
        self.assertIn("blacklisted " + ADDRESS, blacklisted)
        self.assertEqual(self.blacklisted, [(99, ADDRESS)])

        reset = self._run(FakeMessage("faucet-amoy-reset 55", ["Admin"]))
        self.assertIn("Reset <@55>'s amoy POL limit", reset[1])
        self.assertEqual(self.resets, ["55"])

    def test_amoy_requires_developer_role(self):
        replied = self._run(FakeMessage("faucet-amoy " + ADDRESS, ["Community"]))
        self.assertIn("Developer", replied[1])
        self.assertEqual(self.amoy_sent, [])

    def test_unknown_prefix_does_not_send_tokens(self):
        replied = self._run(FakeMessage("faucet-mumbai " + ADDRESS, ["Admin"]))
        self.assertEqual(len(replied), 1)
        self.assertIn("early November", replied[0])
        self.assertIn("/faucet-mainnet", replied[0])
        self.assertEqual(self.sent, [])

    def test_plain_messages_and_bots_are_ignored(self):
        self.assertEqual(self._run(FakeMessage("please send pol", ["Admin"])), [])
        self.assertEqual(
            self._run(FakeMessage("faucet-version", ["Admin"], bot=True)),
            [],
        )

    def test_handler_error_warns_and_reports(self):
        def boom(address):
            raise RuntimeError("rpc down")

        self.faucet.get_balance = boom
        replied = self._run(FakeMessage("faucet-mainnet " + ADDRESS, ["Community"]))
        self.assertIn("early November", replied[0])
        self.assertEqual(replied[-1], prefix_commands.COMMAND_ERROR)
        self.assertEqual(self.reported[0][0], "PrefixCommand")
        self.assertIn("rpc down", self.reported[0][1])
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
