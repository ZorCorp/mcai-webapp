"""cmd_setup must fail on a bad mcai.dev key before any browser opens."""

import argparse
import builtins
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "mcai_webapp.py")


def load_module(home):
    """Import a fresh copy of the script with HOME pointed at a temp dir."""
    os.environ["MCAI_WEBAPP_HOME"] = home
    os.environ.pop("MCAI_CLIENT_SECRET", None)
    os.environ.pop("MCAI_API_KEY", None)
    spec = importlib.util.spec_from_file_location("mw_setup_gate_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class SetupKeyGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.m = load_module(self.tmp.name)

        # No test may reach the real network. Individual tests that expect an
        # HTTP call must opt in explicitly; everything else fails loudly
        # instead of silently hitting mcai.dev or Google.
        def blocked_http(method, url, body=None, headers=None, timeout=60):
            raise AssertionError("unexpected network call: " + method + " " + url)
        self.m.http_json = blocked_http

        self.oauth_flow_calls = []

        def tracked_oauth_flow():
            self.oauth_flow_calls.append(True)
            raise AssertionError("run_oauth_flow must not be called on a bad mcai.dev key")
        self.m.run_oauth_flow = tracked_oauth_flow

    def tearDown(self):
        self.tmp.cleanup()

    def test_bad_key_dies_before_browser_opens(self):
        """The headline safety property: a bad mcai.dev key must fail in
        cmd_setup's own verification step, never reaching run_oauth_flow()."""
        self.m.probe_mcai_key = lambda key: False
        args = argparse.Namespace(api_key="bad-key", force=False)

        with self.assertRaises(self.m.Fail) as ctx:
            self.m.cmd_setup(args)

        self.assertIn("MCAI_UNAUTHORIZED", str(ctx.exception))
        self.assertEqual(self.oauth_flow_calls, [])

    def test_client_from_env_secret_does_not_claim_mcai_dev(self):
        """get_oauth_client(force=True) returns the client straight from the file
        pointed at by MCAI_CLIENT_SECRET — nothing is fetched from mcai.dev and
        nothing is written/chmod'd on that path. cmd_setup's confirmation line
        must say so, not repeat the old unconditional 'fetched from mcai.dev
        (chmod 600)' claim, which is false in this branch."""
        secret_path = os.path.join(self.tmp.name, "byo-client.json")
        with open(secret_path, "w") as f:
            json.dump({
                "installed": {
                    "client_id": "586459078049-vqud.apps.googleusercontent.com",
                    "client_secret": "s3cr3t",
                }
            }, f)
        os.environ["MCAI_CLIENT_SECRET"] = secret_path

        # Skip the OAuth-token branch (and thus the blocked run_oauth_flow
        # stub) — that behaviour is covered elsewhere; this test is only
        # about the OAuth-client confirmation line.
        with open(self.m.TOKEN_FILE, "w") as f:
            f.write("{}")

        self.m.probe_mcai_key = lambda key: True
        args = argparse.Namespace(api_key="test-key", force=False)

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                self.m.cmd_setup(args)
        finally:
            os.environ.pop("MCAI_CLIENT_SECRET", None)

        output = buf.getvalue()
        self.assertNotIn("OAuth client fetched from mcai.dev", output)
        self.assertEqual(self.oauth_flow_calls, [])


    def test_missing_key_dies_without_prompting(self):
        """A terminal connector has no attached TTY. A prompt there reaches nobody
        and blocks until the caller gives up, so cmd_setup must refuse outright."""
        args = argparse.Namespace(api_key=None, force=False)

        def must_not_prompt(*a, **k):
            raise AssertionError("cmd_setup must never call input() — there is no TTY")

        real_input = builtins.input
        builtins.input = must_not_prompt
        try:
            with self.assertRaises(self.m.Fail) as ctx:
                self.m.cmd_setup(args)
        finally:
            builtins.input = real_input

        self.assertIn("NO_MCAI_API_KEY", str(ctx.exception))
        self.assertEqual(self.oauth_flow_calls, [])


if __name__ == "__main__":
    unittest.main()
