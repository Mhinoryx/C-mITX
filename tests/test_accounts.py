import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app import create_app, connect_db


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.app = create_app(self.storage.name, test_config={"TESTING": True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.storage.cleanup()

    def post(self, action, username="Élodie", password="mot-de-passe-test", client=None):
        client = client or self.client
        token = client.get("/api/account").json["csrf"]
        return client.post("/api/account/" + action, json={"username": username, "password": password}, headers={"X-CSRF-Token": token})

    def test_registration_hash_login_and_logout(self):
        with self.client.session_transaction() as session:
            session["player"] = "existing-guest"
        self.assertEqual(self.post("register").status_code, 201)
        with connect_db(Path(self.storage.name) / "games.sqlite3") as db:
            identity, hashed = db.execute("SELECT id, password_hash FROM users").fetchone()
        self.assertEqual(identity, "existing-guest")
        self.assertNotIn("mot-de-passe-test", hashed)
        self.assertEqual(self.post("logout").json["user"], None)
        self.assertEqual(self.client.get("/api/account").json["user"], None)
        other = self.app.test_client()
        self.assertEqual(self.post("login", username="E\u0301LODIE", client=other).status_code, 200)
        with other.session_transaction() as session:
            self.assertEqual(session["user_id"], identity)
        self.assertEqual(self.post("login", password="wrong-password").status_code, 401)

    def test_unique_normalized_pseudo_concurrently(self):
        def register(name):
            return self.post("register", username=name, client=self.app.test_client()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(register, ["Élodie", "e\u0301LODIE"])), [201, 409])

    def test_validation_and_csrf(self):
        self.assertEqual(self.client.post("/api/account/register", json={}).status_code, 403)
        for name in ["ab", "a" * 25, "<script>", "deux mots"]:
            self.assertEqual(self.post("register", username=name).status_code, 400)
        for password in ["short", "a" * 129]:
            self.assertEqual(self.post("register", password=password).status_code, 400)

    def test_account_persists_after_restart_and_limits_attempts(self):
        self.post("register")
        restarted = create_app(self.storage.name, test_config={"TESTING": True}).test_client()
        self.assertEqual(self.post("login", client=restarted).status_code, 200)
        stranger = self.app.test_client()
        for _ in range(10):
            self.assertEqual(self.post("login", password="wrong-password", client=stranger).status_code, 401)
        self.assertEqual(self.post("login", client=stranger).status_code, 429)


if __name__ == "__main__":
    unittest.main()
