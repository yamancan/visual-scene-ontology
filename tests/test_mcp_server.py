"""The MCP server: the wire, the four tools, and the paths that must not crash.

`vson/mcp.py` is a protocol adapter over `vson/api.py`, and that shapes what is
worth testing here. The gates, the transpilers and the renderers are tested
where they live; re-asserting them through a JSON envelope would only prove the
envelope forwards. What is tested here is everything the adapter *adds*:

  * **The wire.** One scripted stdio session against a real subprocess —
    `initialize`, the `notifications/initialized` notification, `tools/list`,
    then a call to each of the four tools — asserting the shape of every reply:
    JSON-RPC framing, one line per message, an answer to every request and to
    no notification, ids echoed, results where results belong.
  * **The tools do what their descriptions say.** The verdict is the library's
    verdict, the conversions are the library's conversions, and
    `vson_skill_prompt` is `skills/vson-extractor/SKILL.md` byte for byte —
    that last one is the whole point of the tool, and a wrapper line added
    around it would be a silent change to what an agent is told to write.
  * **A bad document is a verdict, not a crash.** The distinction the module
    draws between `ToolError` (a call that could not be made — reported to the
    model with `isError`) and a JSON-RPC error (a protocol failure the model
    never sees) is asserted in both directions, and a non-conformant document
    is asserted to be neither: it is an ordinary result whose `conforms` is
    false and whose findings carry the `sh:message` text a repair is written
    from.
  * **Nothing kills the server.** Unparseable bytes, an unknown method, a
    malformed request, an unknown tool, and a call with contradictory arguments
    each produce a reply and leave the loop running.

The subprocess half runs `python3 -m vson.mcp` — the documented second entry
point — so it also establishes that the entry point exists and that starting it
costs no arguments. The `vson mcp` half, which shells out to that same module
from the Rust binary, is `cli/tests/standalone_home.rs`.

Run: python3 -m unittest tests.test_mcp_server
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

try:
    import rdflib  # noqa: F401 — probe: the whole package needs it

    from vson import mcp
except ImportError:  # pragma: no cover — dependency probe
    mcp = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD_P = os.path.join(REPO, "examples", "gallery", "01_minimal.vson")
GOOD_X = os.path.join(REPO, "examples", "gallery-x", "01_minimal.x.vson")
BAD_T = os.path.join(REPO, "tests", "fixtures", "bad_no_viewer.ttl")
SKILL_MD = os.path.join(REPO, "skills", "vson-extractor", "SKILL.md")
SKILL_X_MD = os.path.join(REPO, "skills", "vson-extractor-x", "SKILL.md")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def request(request_id, method, **params):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params:
        message["params"] = params
    return message


def call(request_id, name, **arguments):
    return request(request_id, "tools/call", name=name, arguments=arguments)


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class StdioSessionTests(unittest.TestCase):
    """One real conversation with one real child process.

    Everything else in this file drives the dispatcher in-process, which is
    faster and says nothing about framing. This says the framing works: a
    client that writes lines and reads lines gets answers.
    """

    @classmethod
    def setUpClass(cls) -> None:
        script = [
            request(
                1,
                "initialize",
                protocolVersion="2025-06-18",
                capabilities={},
                clientInfo={"name": "vson-test", "version": "0"},
            ),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            request(2, "tools/list"),
            call(3, "vson_validate", path=GOOD_P),
            call(4, "vson_convert", direction="x2t", path=GOOD_X),
            call(5, "vson_export", format="caption", path=GOOD_P),
            call(6, "vson_skill_prompt"),
            call(7, "vson_validate", path=BAD_T),
        ]
        cls.script = script
        body = "".join(json.dumps(m) + "\n" for m in script)
        done = subprocess.run(
            [sys.executable, "-m", "vson.mcp"],
            input=body.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO,
            timeout=600,
        )
        cls.done = done
        cls.lines = [
            line for line in done.stdout.decode("utf-8").split("\n") if line.strip()
        ]
        cls.replies = [json.loads(line) for line in cls.lines]

    def reply(self, request_id):
        for message in self.replies:
            if message.get("id") == request_id:
                return message
        self.fail("no reply with id {}".format(request_id))

    def result(self, request_id):
        message = self.reply(request_id)
        self.assertNotIn("error", message, message.get("error"))
        return message["result"]

    def content(self, request_id) -> str:
        result = self.result(request_id)
        self.assertEqual(result["content"][0]["type"], "text")
        return result["content"][0]["text"]

    # -- the wire ----------------------------------------------------------

    def test_the_server_exits_cleanly_when_the_client_closes_stdin(self) -> None:
        self.assertEqual(
            self.done.returncode,
            0,
            self.done.stderr.decode("utf-8", "replace"),
        )

    def test_one_line_per_message_and_no_line_is_anything_else(self) -> None:
        # Every byte on stdout belongs to the protocol. A print() left in a
        # renderer would land here as a line that is not JSON.
        for line in self.lines:
            json.loads(line)

    def test_every_request_is_answered_and_the_notification_is_not(self) -> None:
        asked = [m["id"] for m in self.script if "id" in m]
        self.assertEqual([m["id"] for m in self.replies], asked)

    def test_every_reply_is_jsonrpc_2_0_with_a_result_or_an_error(self) -> None:
        for message in self.replies:
            self.assertEqual(message["jsonrpc"], "2.0")
            self.assertEqual(
                ("result" in message) ^ ("error" in message),
                True,
                message,
            )

    def test_initialize_negotiates_and_names_the_server(self) -> None:
        result = self.result(1)
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertEqual(result["serverInfo"]["name"], "vson")
        self.assertIn("tools", result["capabilities"])
        # The instructions are the reason the skill tool exists: an agent that
        # reads them calls it before writing anything.
        self.assertIn("vson_skill_prompt", result["instructions"])

    def test_tools_list_publishes_four_tools_with_input_schemas(self) -> None:
        tools = self.result(2)["tools"]
        self.assertEqual(
            [tool["name"] for tool in tools],
            ["vson_validate", "vson_convert", "vson_export", "vson_skill_prompt"],
        )
        for tool in tools:
            self.assertTrue(tool["description"].strip())
            schema = tool["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)

    # -- the four tools ----------------------------------------------------

    def test_a_conformant_document_comes_back_as_a_clean_verdict(self) -> None:
        result = self.result(3)
        self.assertIs(result["isError"], False)
        record = json.loads(self.content(3))
        self.assertEqual(record, result["structuredContent"])
        self.assertIs(record["conforms"], True)
        self.assertIsNone(record["gate"])
        self.assertEqual(record["findings"], [])
        self.assertEqual(record["profile"], "strict")
        self.assertEqual(record["report"], "vson-validate-records/1")

    def test_x2t_returns_the_turtle_the_library_returns(self) -> None:
        from vson import api

        self.assertEqual(self.content(4), api.from_x(read(GOOD_X)))

    def test_the_caption_is_the_renderers_caption(self) -> None:
        from vson import api

        self.assertEqual(self.content(5), api.caption(GOOD_P))

    def test_the_skill_prompt_is_the_shipped_file_byte_for_byte(self) -> None:
        self.assertEqual(self.content(6), read(SKILL_MD))

    def test_a_bad_document_is_a_verdict_with_violations_not_an_error(self) -> None:
        result = self.result(7)
        self.assertIs(
            result["isError"],
            False,
            "a document that breaks a shape is an answer, not a tool failure",
        )
        record = json.loads(self.content(7))
        self.assertIs(record["conforms"], False)
        self.assertEqual(record["gate"], "shacl")
        self.assertTrue(record["findings"])
        finding = record["findings"][0]
        # The fields a repair prompt is built from (docs/vson.md §5.16.1).
        for field in ("gate", "rule", "severity", "message", "shape", "focus_node"):
            self.assertIn(field, finding)
        self.assertIn("viewer", finding["message"])


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class ProtocolTests(unittest.TestCase):
    """The dispatcher, in process — the branches a happy session never takes."""

    def setUp(self) -> None:
        self.server = mcp.Server(None, None)

    def send(self, message):
        return self.server.handle(message)

    def test_an_unknown_protocol_version_gets_the_newest_this_server_has(self):
        self.assertEqual(mcp.negotiate("1999-01-01"), mcp.LATEST_PROTOCOL_VERSION)
        self.assertEqual(mcp.negotiate(None), mcp.LATEST_PROTOCOL_VERSION)
        for version in mcp.PROTOCOL_VERSIONS:
            self.assertEqual(mcp.negotiate(version), version)

    def test_a_known_protocol_version_is_echoed_back(self) -> None:
        reply = self.send(request(1, "initialize", protocolVersion="2024-11-05"))
        self.assertEqual(reply["result"]["protocolVersion"], "2024-11-05")

    def test_ping_is_answered(self) -> None:
        self.assertEqual(self.send(request(9, "ping"))["result"], {})

    def test_an_unknown_method_is_a_method_not_found_error(self) -> None:
        reply = self.send(request(2, "resources/list"))
        self.assertEqual(reply["error"]["code"], mcp.METHOD_NOT_FOUND)

    def test_an_unknown_notification_is_answered_with_silence(self) -> None:
        self.assertIsNone(self.send({"jsonrpc": "2.0", "method": "notifications/x"}))

    def test_the_initialized_notification_is_recorded_and_not_answered(self) -> None:
        self.assertIsNone(
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        )
        self.assertTrue(self.server.initialized)

    def test_a_message_that_is_not_an_object_is_an_invalid_request(self) -> None:
        self.assertEqual(self.send("hello")["error"]["code"], mcp.INVALID_REQUEST)
        self.assertEqual(self.send({"jsonrpc": "2.0", "id": 1})["error"]["code"],
                         mcp.INVALID_REQUEST)

    def test_params_that_are_not_an_object_are_invalid_params(self) -> None:
        reply = self.send({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []})
        self.assertEqual(reply["error"]["code"], mcp.INVALID_PARAMS)

    def test_a_batch_is_answered_with_a_batch_and_notifications_drop_out(self):
        # Batching exists in revision 2025-03-26 and not in 2025-06-18. It is
        # accepted on every revision this server answers, which is the lenient
        # direction: refusing one a client is entitled to send would be a real
        # incompatibility, accepting one it will never send costs nothing.
        replies = self.send(
            [
                request(1, "ping"),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                request(2, "ping"),
            ]
        )
        self.assertEqual([r["id"] for r in replies], [1, 2])

    def test_a_batch_of_only_notifications_is_answered_with_silence(self) -> None:
        self.assertIsNone(
            self.send([{"jsonrpc": "2.0", "method": "notifications/initialized"}])
        )

    def test_an_empty_batch_is_an_invalid_request(self) -> None:
        self.assertEqual(self.send([])["error"]["code"], mcp.INVALID_REQUEST)

    def test_a_line_that_is_not_json_is_a_parse_error_and_not_a_crash(self) -> None:
        reply = self.server.handle_line(b"{not json\n")
        self.assertEqual(reply["error"]["code"], mcp.PARSE_ERROR)

    def test_a_line_that_is_not_utf8_is_a_parse_error(self) -> None:
        reply = self.server.handle_line(b"\xff\xfe\n")
        self.assertEqual(reply["error"]["code"], mcp.PARSE_ERROR)

    def test_a_blank_line_is_ignored(self) -> None:
        self.assertIsNone(self.server.handle_line(b"\n"))
        self.assertIsNone(self.server.handle_line(b"   \n"))

    def test_an_unknown_tool_is_a_protocol_error_not_a_tool_result(self) -> None:
        reply = self.send(call(3, "vson_hallucinate"))
        self.assertEqual(reply["error"]["code"], mcp.INVALID_PARAMS)
        self.assertIn("vson_validate", reply["error"]["message"])

    def test_arguments_that_are_not_an_object_are_invalid_params(self) -> None:
        reply = self.send(
            request(4, "tools/call", name="vson_skill_prompt", arguments="p")
        )
        self.assertEqual(reply["error"]["code"], mcp.INVALID_PARAMS)

    def test_omitted_arguments_are_an_empty_object(self) -> None:
        reply = self.send(request(5, "tools/call", name="vson_skill_prompt"))
        self.assertEqual(reply["result"]["content"][0]["text"], read(SKILL_MD))

    def test_the_tool_table_and_the_published_list_are_the_same_set(self) -> None:
        self.assertEqual(
            sorted(mcp.CALLS), sorted(tool["name"] for tool in mcp.TOOLS)
        )

    def test_every_published_schema_admits_only_what_the_tool_reads(self) -> None:
        # `additionalProperties: false` is what makes a typo in an argument
        # name visible to the client instead of silently ignored here.
        for tool in mcp.TOOLS:
            schema = tool["inputSchema"]
            self.assertIs(schema["additionalProperties"], False, tool["name"])
            for name in schema.get("required", []):
                self.assertIn(name, schema["properties"], tool["name"])


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class ToolErrorTests(unittest.TestCase):
    """Calls that cannot be made. Every one is a result the model can read."""

    def setUp(self) -> None:
        self.server = mcp.Server(None, None)

    def failure(self, name, **arguments) -> str:
        reply = self.server.handle(call(1, name, **arguments))
        result = reply["result"]
        self.assertIs(result["isError"], True, result)
        return result["content"][0]["text"]

    def test_neither_a_document_nor_a_path_is_a_tool_error(self) -> None:
        self.assertIn("exactly one", self.failure("vson_validate"))

    def test_both_a_document_and_a_path_is_a_tool_error(self) -> None:
        self.assertIn(
            "exactly one",
            self.failure("vson_validate", document="(s / Composition)", path=GOOD_P),
        )

    def test_a_path_that_does_not_exist_names_itself(self) -> None:
        message = self.failure("vson_validate", path="no/such/scene.vson")
        self.assertIn("scene.vson", message)

    def test_a_document_that_will_not_parse_is_a_tool_error(self) -> None:
        message = self.failure("vson_convert", direction="p2t", document="(((")
        self.assertIn("VSON-P", message)

    def test_an_unknown_syntax_is_a_tool_error(self) -> None:
        message = self.failure("vson_validate", document="(s / Composition)", syntax="q")
        self.assertIn("syntax", message)

    def test_an_unknown_export_format_is_a_tool_error(self) -> None:
        message = self.failure("vson_export", format="graphml", path=GOOD_P)
        self.assertIn("format", message)

    def test_cypher_refuses_a_graph_it_cannot_read(self) -> None:
        # `export cypher` parses Penman, and no back-conversion from the graph
        # to an authoring syntax is shipped — so VSON-T in is a sentence, not a
        # traceback, whether or not a binary is reachable.
        message = self.failure("vson_export", format="cypher", path=BAD_T)
        self.assertIn("VSON-P", message)

    def test_a_document_argument_that_is_not_a_string_is_a_tool_error(self) -> None:
        self.assertIn("string", self.failure("vson_validate", document=7))

    def test_an_extension_that_names_no_syntax_is_not_guessed_at(self) -> None:
        # A guess here would answer a file of Penman named `.txt` with a
        # confident sentence about VSON-T and advice that cannot work.
        message = self.failure(
            "vson_export",
            format="cypher",
            path=os.path.join(REPO, "pyproject.toml"),
        )
        self.assertIn(".toml", message)
        self.assertIn(".x.vson", message)
        self.assertIn("`syntax`", message)
        self.assertNotIn("is VSON-T", message)

    def test_every_tool_names_the_bad_argument_before_the_bad_path(self) -> None:
        # The order stated above the three call_* functions: declared
        # arguments, then the document, then the environment. A call that is
        # wrong twice is answered the same way whichever tool it went to.
        for name, arguments in (
            ("vson_validate", {"profile": "lenient"}),
            ("vson_convert", {"direction": "t2p"}),
            ("vson_export", {"format": "graphml"}),
        ):
            message = self.failure(name, path="no/such/scene.vson", **arguments)
            self.assertIn("must be one of", message, name)
            self.assertNotIn("no such file", message, name)


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class CypherOrderTests(unittest.TestCase):
    """`export cypher` on a machine with no `vson` binary anywhere.

    Every assertion here is about an order — the input is settled before the
    environment is consulted — and the branch that proves it is unreachable on
    a machine where `cargo build` has run, which is every machine this suite is
    normally run on. So `cli_binary` is stubbed to the answer that machine
    cannot give: without that, reverting the order would stay green.
    """

    def setUp(self) -> None:
        self.reachable = mcp.cli_binary
        mcp.cli_binary = lambda: None

    def tearDown(self) -> None:
        mcp.cli_binary = self.reachable

    def error(self, **arguments) -> str:
        with self.assertRaises(mcp.ToolError) as caught:
            mcp.call_export(dict(arguments, format="cypher"))
        return str(caught.exception)

    def test_a_graph_is_refused_as_a_graph_before_a_binary_is_looked_for(self):
        message = self.error(path=BAD_T)
        self.assertIn("VSON-P", message)
        self.assertNotIn("cargo", message)

    def test_penman_with_no_binary_says_which_binary_and_how_to_get_one(self):
        message = self.error(path=GOOD_P)
        self.assertIn(mcp.CLI_ENV, message)
        self.assertIn("cargo build", message)

    def test_a_document_that_names_a_file_is_still_a_document(self) -> None:
        # `document` is text because the caller said `document`. Re-deriving
        # that with os.path.isfile against the process's own directory is how
        # a model writing `"scene.vson"` would silently render whatever file
        # the server happened to be standing next to.
        previous = os.getcwd()
        os.chdir(os.path.dirname(GOOD_P))
        try:
            message = self.error(document=os.path.basename(GOOD_P))
        finally:
            os.chdir(previous)
        self.assertIn("<document>", message)
        self.assertIn("VSON-P", message)


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class StagedFileTests(unittest.TestCase):
    """Text becoming the file the Cypher binary reads, when that goes wrong."""

    def temporaries(self):
        import glob
        import tempfile

        return set(glob.glob(os.path.join(tempfile.gettempdir(), "*.vson")))

    def test_a_document_that_cannot_be_encoded_is_a_tool_error(self) -> None:
        # A lone surrogate survives json.loads and is a str that has no UTF-8
        # encoding — an opaque JSON-RPC internal error if it is not caught, and
        # a temp file left behind if the cleanup assumes a written one.
        before = self.temporaries()
        with self.assertRaises(mcp.ToolError) as caught:
            mcp._staged_penman("(s / Composition)\ud800")
        self.assertIn("Cypher", str(caught.exception))
        self.assertEqual(before, self.temporaries())

    def test_a_document_that_encodes_becomes_a_file_with_that_text(self) -> None:
        body = read(GOOD_P)
        staged = mcp._staged_penman(body)
        try:
            self.assertEqual(read(staged), body)
            self.assertTrue(staged.endswith(".vson"))
        finally:
            mcp._discard(staged)
        self.assertFalse(os.path.exists(staged))
        mcp._discard(staged)  # a second removal is not an error


@unittest.skipIf(mcp is None, "rdflib/pyshacl not installed")
class ToolBehaviourTests(unittest.TestCase):
    """The tools themselves, called directly — no envelope in the way."""

    def test_the_relaxed_profile_is_named_in_the_record_it_produced(self) -> None:
        record = mcp.call_validate({"path": GOOD_P, "profile": "relaxed"})
        self.assertEqual(record["profile"], "relaxed")

    def test_text_input_and_path_input_reach_the_same_verdict(self) -> None:
        from_path = mcp.call_validate({"path": GOOD_P})
        from_text = mcp.call_validate({"document": read(GOOD_P)})
        self.assertEqual(from_path["conforms"], from_text["conforms"])
        self.assertEqual(from_path["findings"], from_text["findings"])

    def test_p2t_and_the_library_agree(self) -> None:
        from vson import api

        self.assertEqual(
            mcp.call_convert({"direction": "p2t", "path": GOOD_P}),
            api.to_turtle(read(GOOD_P)),
        )

    def test_fol_reads_all_three_syntaxes(self) -> None:
        from_p = mcp.call_export({"format": "fol", "path": GOOD_P})
        from_x = mcp.call_export({"format": "fol", "path": GOOD_X})
        self.assertEqual(from_p, from_x)
        self.assertIn("Composition(scene).", from_p)

    def test_the_vson_x_skill_is_the_other_shipped_file(self) -> None:
        self.assertEqual(
            mcp.call_skill_prompt({"notation": "x"}), read(SKILL_X_MD)
        )
        self.assertEqual(mcp.call_skill_prompt({}), read(SKILL_MD))

    def test_a_relative_path_resolves_against_the_declared_base(self) -> None:
        # `vson mcp` starts this server in the repository home so that
        # `python3 -m` can import it, and hands the user's own directory down in
        # $VSON_MCP_CWD. Without that, every relative path a caller typed would
        # be resolved somewhere the caller never was.
        previous = os.environ.get(mcp.CWD_ENV)
        os.environ[mcp.CWD_ENV] = os.path.join(REPO, "examples", "gallery")
        try:
            self.assertEqual(mcp.base_directory(), os.environ[mcp.CWD_ENV])
            record = mcp.call_validate({"path": "01_minimal.vson"})
        finally:
            if previous is None:
                del os.environ[mcp.CWD_ENV]
            else:
                os.environ[mcp.CWD_ENV] = previous
        self.assertIs(record["conforms"], True)

    def test_the_module_entry_point_takes_no_arguments(self) -> None:
        # Both branches write to stderr — which is where an MCP server's
        # diagnostics belong, and where a test suite's output does not.
        import io
        import contextlib

        noise = io.StringIO()
        with contextlib.redirect_stderr(noise):
            self.assertEqual(mcp.main(["--help"]), 0)
            self.assertEqual(mcp.main(["--serve", "8080"]), 2)
        self.assertIn("vson_skill_prompt", noise.getvalue())


if __name__ == "__main__":
    unittest.main()
