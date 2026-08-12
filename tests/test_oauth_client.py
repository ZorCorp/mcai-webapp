"""get_oauth_client() — resolution order, caching, and failure modes."""

import importlib.util
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
    os.environ["MCAI_API_KEY"] = "test-key"
    spec = importlib.util.spec_from_file_location("mw_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


GOOD_PAYLOAD = {
    "installed": {
        "client_id": "123.apps.googleusercontent.com",
        "client_secret": "s3cr3t",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


class GetOAuthClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.m = load_module(self.home)
        self.calls = []

        # No test may reach the real network. Individual tests that expect an
        # HTTP call must opt in via stub_http(); everything else fails loudly
        # instead of silently hitting mcai.dev.
        def blocked(method, url, body=None, headers=None, timeout=60):
            raise AssertionError("unexpected network call: " + method + " " + url)
        self.m.http_json = blocked

    def tearDown(self):
        self.tmp.cleanup()

    def stub_http(self, status, payload):
        def fake(method, url, body=None, headers=None, timeout=60):
            self.calls.append(url)
            return status, payload
        self.m.http_json = fake

    def test_fetches_from_server_and_caches(self):
        self.stub_http(200, GOOD_PAYLOAD)
        client = self.m.get_oauth_client()
        self.assertEqual(client["client_id"], "123.apps.googleusercontent.com")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(os.path.exists(self.m.CLIENT_FILE))
        with open(self.m.CLIENT_FILE) as f:
            cached = json.load(f)
        self.assertEqual(cached, {"installed": GOOD_PAYLOAD["installed"]})

    def test_cache_file_is_chmod_600(self):
        self.stub_http(200, GOOD_PAYLOAD)
        self.m.get_oauth_client()
        mode = os.stat(self.m.CLIENT_FILE).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_second_call_uses_cache(self):
        self.stub_http(200, GOOD_PAYLOAD)
        self.m.get_oauth_client()
        client = self.m.get_oauth_client()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(client["client_secret"], "s3cr3t")

    def test_force_bypasses_cache(self):
        self.stub_http(200, GOOD_PAYLOAD)
        self.m.get_oauth_client()
        self.m.get_oauth_client(force=True)
        self.assertEqual(len(self.calls), 2)

    def test_explicit_env_path_wins_and_skips_server(self):
        path = os.path.join(self.home, "byo.json")
        with open(path, "w") as f:
            json.dump(GOOD_PAYLOAD, f)
        os.environ["MCAI_CLIENT_SECRET"] = path
        try:
            client = self.m.get_oauth_client()
        finally:
            os.environ.pop("MCAI_CLIENT_SECRET", None)
        self.assertEqual(client["client_secret"], "s3cr3t")
        self.assertEqual(self.calls, [])

    def test_explicit_env_path_wins_over_populated_cache(self):
        """A resolution-order regression test: MCAI_CLIENT_SECRET must be checked
        before the cache, not after. Populate the cache first with one client,
        then point MCAI_CLIENT_SECRET at a file holding a *different* client_id,
        and confirm the env override — not the cache — is what comes back."""
        self.stub_http(200, GOOD_PAYLOAD)
        self.m.get_oauth_client()
        self.assertTrue(os.path.exists(self.m.CLIENT_FILE))

        other_payload = {
            "installed": {
                "client_id": "999.apps.googleusercontent.com",
                "client_secret": "other-secret",
            }
        }
        path = os.path.join(self.home, "byo.json")
        with open(path, "w") as f:
            json.dump(other_payload, f)
        os.environ["MCAI_CLIENT_SECRET"] = path
        try:
            client = self.m.get_oauth_client()
        finally:
            os.environ.pop("MCAI_CLIENT_SECRET", None)
        self.assertEqual(client["client_id"], "999.apps.googleusercontent.com")
        self.assertEqual(client["client_secret"], "other-secret")
        self.assertEqual(len(self.calls), 1)  # only the initial cache-populating fetch

    def test_missing_explicit_path_dies(self):
        os.environ["MCAI_CLIENT_SECRET"] = os.path.join(self.home, "nope.json")
        try:
            with self.assertRaises(self.m.Fail) as ctx:
                self.m.get_oauth_client()
        finally:
            os.environ.pop("MCAI_CLIENT_SECRET", None)
        self.assertIn("CLIENT_SECRET_NOT_FOUND", str(ctx.exception))

    def test_401_reports_unauthorized(self):
        self.stub_http(401, {"error": "Unauthorized"})
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.get_oauth_client()
        self.assertIn("MCAI_UNAUTHORIZED", str(ctx.exception))

    def test_503_reports_not_configured(self):
        self.stub_http(503, {"error": "OAuth client not configured"})
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.get_oauth_client()
        self.assertIn("NO_OAUTH_CLIENT", str(ctx.exception))

    def test_500_reports_fetch_failed(self):
        self.stub_http(500, "boom")
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.get_oauth_client()
        self.assertIn("OAUTH_CLIENT_FETCH_FAILED", str(ctx.exception))

    def test_payload_without_client_secret_is_rejected(self):
        self.stub_http(200, {"installed": {"client_id": "x"}})
        with self.assertRaises(self.m.Fail) as ctx:
            self.m.get_oauth_client()
        self.assertIn("BAD_OAUTH_CLIENT", str(ctx.exception))

    def test_malformed_cache_is_treated_as_a_miss(self):
        """An unreadable/invalid cache is our own write, not a user override —
        it should be refetched, not a hard failure."""
        with open(self.m.CLIENT_FILE, "w") as f:
            f.write("not json")
        self.stub_http(200, GOOD_PAYLOAD)
        client = self.m.get_oauth_client()
        self.assertEqual(client["client_id"], "123.apps.googleusercontent.com")
        self.assertEqual(len(self.calls), 1)

    def test_explicit_path_with_non_dict_json_dies(self):
        """A list or a bare string is valid JSON but not a client — this must
        die() through BAD_OAUTH_CLIENT, not raise a raw AttributeError."""
        path = os.path.join(self.home, "list.json")
        with open(path, "w") as f:
            json.dump([1, 2, 3], f)
        os.environ["MCAI_CLIENT_SECRET"] = path
        try:
            with self.assertRaises(self.m.Fail) as ctx:
                self.m.get_oauth_client()
        finally:
            os.environ.pop("MCAI_CLIENT_SECRET", None)
        self.assertIn("BAD_OAUTH_CLIENT", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
