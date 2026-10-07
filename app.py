import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, session
from engine import SemanticEngine, calendar, normalize

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

@contextmanager
def connect_db(path):
    db = sqlite3.connect(path, timeout=30)
    try:
        with db:
            yield db
    finally:
        db.close()

def create_app(data_dir=DATA, semantic_engine=None, test_config=None):
    app = Flask(__name__, static_folder=None)
    data_dir = Path(data_dir)
    data_dir.mkdir(exist_ok=True, parents=True)
    key_path = data_dir / "secret.key"
    if not key_path.exists():
        try:
            with key_path.open("x", encoding="utf-8") as key:
                key.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    app.config.update(SECRET_KEY=os.environ.get("CEMENTIX_SECRET") or key_path.read_text(encoding="utf-8"), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(days=365), MAX_CONTENT_LENGTH=2048)
    if test_config:
        app.config.update(test_config)
    database = data_dir / "games.sqlite3"
    with connect_db(database) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS attempts (
            player TEXT NOT NULL, day TEXT NOT NULL, word TEXT NOT NULL,
            number INTEGER NOT NULL, temperature REAL NOT NULL,
            progress INTEGER, won INTEGER NOT NULL,
            PRIMARY KEY(player, day, word));
        CREATE TABLE IF NOT EXISTS winners (
            player TEXT NOT NULL, day TEXT NOT NULL, position INTEGER NOT NULL,
            PRIMARY KEY(player, day), UNIQUE(day, position));
        """)
    engine_lock = threading.Lock()
    engine = semantic_engine

    def get_engine():
        nonlocal engine
        with engine_lock:
            if engine is None:
                if not (data_dir / "vectors.npy").exists() or not (data_dir / "vocabulary.json").exists():
                    return None
                engine = SemanticEngine(data_dir)
        return engine

    def player():
        if "player" not in session:
            session["player"] = secrets.token_urlsafe(24)
            session.permanent = True
        return session["player"]

    def state(db, identity, day, next_at):
        db.row_factory = sqlite3.Row
        attempts = [dict(row) for row in db.execute("SELECT word, number, temperature, progress, won FROM attempts WHERE player=? AND day=? ORDER BY number", (identity, day))]
        for item in attempts:
            item["won"] = bool(item["won"])
        winner = db.execute("SELECT position FROM winners WHERE player=? AND day=?", (identity, day)).fetchone()
        solved = db.execute("SELECT COUNT(*) FROM winners WHERE day=?", (day,)).fetchone()[0]
        return {"day": day, "next_at": next_at, "attempts": attempts, "won": bool(winner), "position": winner[0] if winner else None, "solved": solved}

    @app.get("/")
    def index():
        return send_from_directory(ROOT / "static", "index.html")

    @app.get("/static/<path:filename>")
    def assets(filename):
        return send_from_directory(ROOT / "static", filename)

    @app.get("/api/game")
    def game():
        semantic = get_engine()
        if semantic is None:
            return jsonify(error="Le modèle sémantique n’est pas installé. Exécutez python prepare_data.py puis rechargez cette page."), 503
        day, next_at = calendar()
        puzzle = semantic.puzzle(day)
        with connect_db(database) as db:
            result = state(db, player(), day, next_at)
        result["thresholds"] = puzzle["thresholds"]
        return jsonify(result)

    @app.post("/api/guess")
    def guess():
        semantic = get_engine()
        if semantic is None:
            return jsonify(error="Le modèle sémantique n’est pas encore prêt."), 503
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("word"), str):
            return jsonify(error="Un mot est requis."), 400
        identity = player()
        day, next_at = calendar()
        if payload.get("day") != day:
            return jsonify(error="Un nouveau mot est arrivé. La partie a été actualisée.", refresh=True), 409
        word = normalize(payload["word"])
        try:
            evaluation = semantic.guess(day, word)
        except ValueError as exc:
            return jsonify(error=str(exc)), 422
        with connect_db(database) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT 1 FROM attempts WHERE player=? AND day=? AND word=?", (identity, day, word)).fetchone()
            winner = db.execute("SELECT 1 FROM winners WHERE player=? AND day=?", (identity, day)).fetchone()
            if not existing and not winner:
                number = db.execute("SELECT COUNT(*) FROM attempts WHERE player=? AND day=?", (identity, day)).fetchone()[0] + 1
                db.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)", (identity, day, word, number, evaluation["temperature"], evaluation["progress"], int(evaluation["won"])))
                if evaluation["won"]:
                    position = db.execute("SELECT COUNT(*) FROM winners WHERE day=?", (day,)).fetchone()[0] + 1
                    db.execute("INSERT INTO winners VALUES (?, ?, ?)", (identity, day, position))
            result = state(db, identity, day, next_at)
        result.update(duplicate=bool(existing), last_word=word)
        return jsonify(result)

    @app.after_request
    def headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    return app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
