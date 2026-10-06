import asyncio
import unittest

from fake_gemini import VALID_KEY, FakeGemini, call_chunk, done_chunk, text_chunk

from devos.credentials import Credentials
from devos.providers.base import ProviderError
from devos.providers.gemini import Gemini, to_contents, to_declaration


async def collect(stream):
    return [ev async for ev in stream]


class GeminiTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGemini()
        self.key = VALID_KEY
        self.g = Gemini(lambda: self.key, base_url=self.fake.base_url, backoff=0.01)

    def tearDown(self):
        self.fake.close()

    def test_streaming_text_and_tool_call(self):
        self.fake.script = [[text_chunk("Hel"), text_chunk("lo"), call_chunk("read_file", {"path": "a"}), done_chunk()]]
        tools = [{"name": "read_file", "description": "d",
                  "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"],
                                  "additionalProperties": False}},
                 {"name": "git_status", "description": "d", "inputSchema": {"type": "object", "properties": {}}}]
        events = asyncio.run(collect(self.g.stream_chat([{"role": "user", "text": "hi"}], tools, "SYS",
                                                        "gemini-flash-latest")))
        self.assertEqual([e["text"] for e in events if e["type"] == "text"], ["Hel", "lo"])
        calls = [e for e in events if e["type"] == "tool_call"]
        self.assertEqual((calls[0]["name"], calls[0]["args"]), ("read_file", {"path": "a"}))
        done = events[-1]
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["message"]["text"], "Hello")
        self.assertEqual(done["usage"], {"input_tokens": 10, "output_tokens": 5})
        req = self.fake.requests[0]
        self.assertEqual(req["path"], "/v1beta/models/gemini-flash-latest:streamGenerateContent?alt=sse")
        self.assertEqual(req["body"]["systemInstruction"]["parts"][0]["text"], "SYS")
        decls = req["body"]["tools"][0]["functionDeclarations"]
        self.assertNotIn("additionalProperties", decls[0]["parameters"])
        self.assertNotIn("parameters", decls[1])  # no-arg tool

    def test_thought_signature_round_trip(self):
        self.fake.script = [[call_chunk("git_status", {}, signature="SIG-XYZ"), done_chunk()]]
        events = asyncio.run(collect(self.g.stream_chat([{"role": "user", "text": "x"}], None, None, "m")))
        msg = events[-1]["message"]
        contents = to_contents([{"role": "user", "text": "x"}, msg,
                                {"role": "tool", "results": [{"id": "c", "name": "git_status", "result": {"ok": 1}}]}])
        self.assertEqual(contents[1]["parts"][0]["thoughtSignature"], "SIG-XYZ")
        self.assertEqual(contents[2]["parts"][0]["functionResponse"]["name"], "git_status")

    def test_invalid_key(self):
        self.key = "AIza" + "X" * 35
        with self.assertRaises(ProviderError) as cm:
            asyncio.run(self.g.test_credentials())
        self.assertEqual(cm.exception.kind, "invalid_key")
        with self.assertRaises(ProviderError) as cm:
            asyncio.run(collect(self.g.stream_chat([{"role": "user", "text": "x"}], None, None, "m")))
        self.assertEqual(cm.exception.kind, "invalid_key")
        self.assertEqual(len(self.fake.requests), 1)  # not retried

    def test_retry_on_rate_limit(self):  # AI-012
        self.fake.script = [429, 503, [text_chunk("ok"), done_chunk()]]
        events = asyncio.run(collect(self.g.stream_chat([{"role": "user", "text": "x"}], None, None, "m")))
        self.assertEqual(events[0]["text"], "ok")
        self.assertEqual(len(self.fake.requests), 3)

    def test_gives_up_after_two_retries(self):
        self.fake.script = [429, 429, 429, [text_chunk("never")]]
        with self.assertRaises(ProviderError) as cm:
            asyncio.run(collect(self.g.stream_chat([{"role": "user", "text": "x"}], None, None, "m")))
        self.assertEqual(cm.exception.kind, "quota")
        self.assertEqual(len(self.fake.requests), 3)

    def test_network_error(self):
        g = Gemini(lambda: self.key, base_url="http://127.0.0.1:9/v1beta", backoff=0.01)
        with self.assertRaises(ProviderError) as cm:
            asyncio.run(g.test_credentials())
        self.assertEqual(cm.exception.kind, "network")

    def test_list_models(self):
        self.assertEqual(asyncio.run(self.g.list_models()), ["gemini-flash-latest"])

    def test_https_required(self):
        with self.assertRaises(ValueError):
            Gemini(lambda: "k", base_url="http://example.com")

    def test_declaration_conversion(self):
        d = to_declaration({"name": "n", "description": "d", "inputSchema": {
            "type": "object", "properties": {"a": {"type": "array", "items": {"type": "string", "x": 1}}}}})
        self.assertEqual(d["parameters"]["properties"]["a"]["items"], {"type": "string"})


class FakeBackend:
    def __init__(self, ok=True):
        self.ok, self.store_ = ok, {}

    def available(self):
        return self.ok

    def store(self, p, s):
        self.store_[p] = s
        return True

    def lookup(self, p):
        return self.store_.get(p)

    def clear(self, p):
        self.store_.pop(p, None)


class CredentialsTest(unittest.TestCase):
    def test_keyring(self):
        b = FakeBackend()
        c = Credentials(b)
        self.assertEqual(c.set("gemini", " AIzaKEY12345678 \n"), "keyring")
        self.assertEqual(b.store_["gemini"], "AIzaKEY12345678")
        self.assertEqual(Credentials(b).get("gemini"), "AIzaKEY12345678")
        c.remove("gemini")
        self.assertIsNone(Credentials(b).get("gemini"))

    def test_memory_fallback(self):
        c = Credentials(FakeBackend(ok=False))
        self.assertEqual(c.set("gemini", "AIzaKEY12345678"), "memory")
        self.assertEqual(c.status("gemini"), "memory")
        self.assertEqual(c.get("gemini"), "AIzaKEY12345678")

    def test_rejects_bad_keys(self):
        with self.assertRaises(ValueError):
            Credentials(FakeBackend()).set("gemini", "two words")
