import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np
from app import create_app
from engine import SemanticEngine, calendar, normalize

DAY = "2026-10-07"
NEXT = "2026-10-08T00:00:00+02:00"

def letters(number):
    result = ""
    for _ in range(4):
        result = chr(97 + number % 26) + result
        number //= 26
    return "mot" + result

class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        path = Path(cls.fixture.name)
        words = ["amour", "école", "vie", "mort", "maison", "jardin", "ville", "mer", "soleil", "lune", "arbre", "fleur"] + [letters(i) for i in range(1100)]
        angles = np.linspace(0, np.pi, len(words))
        vectors = np.column_stack((np.cos(angles), np.sin(angles))).astype("float32")
        np.save(path / "vectors.npy", vectors)
        (path / "vocabulary.json").write_text(json.dumps([[w, "n"] for w in words]), encoding="utf-8")
        (path / "targets.txt").write_text("\n".join(words[:12]), encoding="utf-8")
        cls.engine = SemanticEngine(path)
        cls.target = cls.engine.puzzle(DAY)["target"]
        cls.other = next(w for w in words[:12] if w != cls.target)

    @classmethod
    def tearDownClass(cls):
        cls.engine.vectors._mmap.close()
        del cls.engine
        cls.fixture.cleanup()

    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.app = create_app(self.storage.name, self.engine, {"TESTING": True})
        self.client = self.app.test_client()
        self.clock = patch("app.calendar", return_value=(DAY, NEXT))
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.storage.cleanup()

    def guess(self, word, client=None, day=DAY):
        return (client or self.client).post("/api/guess", json={"word": word, "day": day})

    def test_cosine_and_unique_top_thousand(self):
        puzzle = self.engine.puzzle(DAY)
        ranks = puzzle["ranks"]
        self.assertEqual(sorted(ranks.values()), list(range(1, 1001)))
        won = self.engine.guess(DAY, self.target)
        self.assertEqual((won["temperature"], won["progress"], won["won"]), (100.0, 1000, True))
        a, b = self.engine.indices[self.other][0], self.engine.indices[self.target][0]
        expected = round(float(self.engine.vectors[a] @ self.engine.vectors[b]) * 100, 2)
        self.assertAlmostEqual(self.engine.guess(DAY, self.other)["temperature"], expected, places=2)
        self.assertEqual(len(puzzle["thresholds"]), 3)

    def test_initial_state_does_not_reveal_target(self):
        response = self.client.get("/api/game")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("target", response.json)
        self.assertNotIn("scores", response.json)
        self.assertEqual(response.json["attempts"], [])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("Expires=", response.headers["Set-Cookie"])

    def test_normalization_and_duplicate_do_not_consume_attempt(self):
        self.guess(" ÉCOLE ")
        result = self.guess("e\u0301cole").json
        self.assertTrue(result["duplicate"])
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["attempts"][0]["word"], "école")
        self.assertNotEqual(normalize("ecole"), normalize("école"))

    def test_unknown_and_invalid_words(self):
        for word in ["zzzinconnu", "deux mots", "<script>", "123", "", "a" * 65]:
            self.assertEqual(self.guess(word).status_code, 422)
        self.assertEqual(self.client.get("/api/game").json["attempts"], [])
        self.assertEqual(self.client.post("/api/guess", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/guess", json={"word": 42}).status_code, 400)

    def test_winner_order_independent_of_attempt_count(self):
        second = self.app.test_client()
        self.guess(self.other)
        first_result = self.guess(self.target).json
        second_result = self.guess(self.target, second).json
        self.assertEqual((first_result["position"], second_result["position"]), (1, 2))
        self.assertEqual(second_result["solved"], 2)
        self.assertEqual(len(first_result["attempts"]), 2)
        self.assertEqual(len(second_result["attempts"]), 1)
        again = self.guess(self.target).json
        self.assertEqual(again["position"], 1)
        self.assertEqual(again["solved"], 2)
        self.assertEqual(len(self.guess(self.other).json["attempts"]), 2)

    def test_stale_day_and_daily_reset(self):
        self.guess(self.other)
        with patch("app.calendar", return_value=("2026-10-08", "2026-10-09T00:00:00+02:00")):
            stale = self.guess(self.target)
            self.assertEqual(stale.status_code, 409)
            self.assertTrue(stale.json["refresh"])
            self.assertEqual(self.client.get("/api/game").json["attempts"], [])
        self.assertEqual(len(self.client.get("/api/game").json["attempts"]), 1)

    def test_browser_cookie_restores_saved_game_after_restart(self):
        self.guess(self.other)
        cookie = self.client.get_cookie("session")
        restarted = create_app(self.storage.name, self.engine, {"TESTING": True}).test_client()
        restarted.set_cookie("session", cookie.value)
        self.assertEqual(len(restarted.get("/api/game").json["attempts"]), 1)
        self.assertEqual(self.app.test_client().get("/api/game").json["attempts"], [])

    def test_account_keeps_guest_victory_and_restores_it_on_another_device(self):
        self.guess(self.other)
        original = self.guess(self.target).json
        token = self.client.get("/api/account").json["csrf"]
        registered = self.client.post("/api/account/register", json={"username": "Joueur", "password": "secret-test-123"}, headers={"X-CSRF-Token": token})
        self.assertEqual(registered.status_code, 201)
        self.client.post("/api/account/logout", headers={"X-CSRF-Token": registered.json["csrf"]})
        self.assertEqual(self.client.get("/api/game").json["attempts"], [])
        other = self.app.test_client()
        token = other.get("/api/account").json["csrf"]
        response = other.post("/api/account/login", json={"username": "JOUEUR", "password": "secret-test-123"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200)
        restored = other.get("/api/game").json
        self.assertEqual(restored["attempts"], original["attempts"])
        self.assertEqual(restored["position"], original["position"])
        self.assertEqual(restored["solved"], 1)

    def test_simultaneous_victories_have_unique_positions(self):
        clients = [self.app.test_client() for _ in range(6)]
        for client in clients:
            client.get("/api/game")
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda c: self.guess(self.target, c).json, clients))
        self.assertEqual(sorted(r["position"] for r in results), list(range(1, 7)))

    def test_midnight_paris_and_daylight_saving(self):
        self.assertEqual(calendar(datetime(2026, 10, 7, 22, 0, tzinfo=timezone.utc))[0], "2026-10-08")
        self.assertEqual(calendar(datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc))[1], "2026-03-30T00:00:00+02:00")
        self.assertEqual(calendar(datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc))[1], "2026-10-26T00:00:00+01:00")

    def test_missing_model_and_private_files(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = create_app(folder, test_config={"TESTING": True}).test_client()
            self.assertEqual(missing.get("/api/game").status_code, 503)
            with missing.get("/") as response:
                self.assertEqual(response.status_code, 200)
        for url in ["/data/targets.txt", "/data/secret.key", "/data/games.sqlite3", "/static/../data/secret.key"]:
            self.assertEqual(self.client.get(url).status_code, 404)

if __name__ == "__main__":
    unittest.main()
