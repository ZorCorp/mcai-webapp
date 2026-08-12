"""access_token() refetches a rotated client and retries once before failing."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "mcai_webapp.py")


def load_module(home):
    os.environ["MCAI_WEBAPP_HOME"] = home
    os.environ.pop("MCAI_CLIENT_SECRET", None)
    os.environ["MCAI_API_KEY"] = "test-key"
    spec = importlib.util.spec_from_file_location("mw_token_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def http_error():
    return urllib.error.HTTPError(
        "https://oauth2.googleapis.com/token", 400, "Bad Request", {},
        io.BytesIO(b'{"error":"invalid_client"}'))


class AccessTokenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.m = load_module(self.tmp.name)
        with open(self.m.TOKEN_FILE, "w") as f:
            json.dump({"refresh_token": "rt"}, f)
        self.client_calls = []
        self.post_calls = []

        def fake_client(force=False):
            self.client_calls.append(force)
            return {"client_id": "cid", "client_secret": "sec"}

        self.m.get_oauth_client = fake_client

        # No test may reach the real network. Individual tests that expect a
        # token-endpoint call must opt in via set_post(); everything else
        # fails loudly instead of silently hitting Google or mcai.dev.
        def blocked_post(url, fields, timeout=60):
            raise AssertionError("unexpected network call: _post_form " + url)
        self.m._post_form = blocked_post

        def blocked_http(method, url, body=None, headers=None, timeout=60):
            raise AssertionError("unexpected network call: http_json " + method + " " + url)
        self.m.http_json = blocked_http

    def tearDown(self):
        self.tmp.cleanup()

    def set_post(self, *outcomes):
        """Each outcome is either a dict to return or an exception to raise."""
        seq = list(outcomes)

        def fake(url, fields, timeout=60):
            self.post_calls.append(fields.get("grant_type"))
            out = seq.pop(0)
            if isinstance(out, Exception):
                raise out
            return out
        self.m._post_form = fake

    def test_happy_path_fetches_client_once(self):
        self.set_post({"access_token": "at-1"})
        self.assertEqual(self.m.access_token(), "at-1")
        self.assertEqual(self.client_calls, [False])
        self.assertEqual(len(self.post_calls), 1)

    def test_refetches_client_and_retries_after_failure(self):
        self.set_post(http_error(), {"access_token": "at-2"})
        self.assertEqual(self.m.access_token(), "at-2")
        self.assertEqual(self.client_calls, [False, True])
        self.assertEqual(len(self.post_calls), 2)

    def test_two_failures_report_token_refresh_failed(self):
        self.set_post(http_error(), http_error())
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.access_token()
        self.assertIn("TOKEN_REFRESH_FAILED", str(ctx.exception))
        self.assertIn("invalid_client", str(ctx.exception))
        self.assertEqual(self.client_calls, [False, True])

    def test_missing_token_file_reports_not_authenticated(self):
        os.remove(self.m.TOKEN_FILE)
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.access_token()
        self.assertIn("NOT_AUTHENTICATED", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
