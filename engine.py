import hashlib
import json
import re
import threading
import unicodedata
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np

PARIS = ZoneInfo("Europe/Paris")
WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)

def normalize(word):
    return unicodedata.normalize("NFC", word.strip().lower())

def calendar(now=None):
    now = now or datetime.now(PARIS)
    local = now.astimezone(PARIS)
    tomorrow = datetime.combine(local.date() + timedelta(days=1), time(), PARIS)
    return local.date().isoformat(), tomorrow.isoformat()

class SemanticEngine:
    def __init__(self, data: Path):
        self.vectors = np.load(data / "vectors.npy", mmap_mode="r")
        self.entries = json.loads((data / "vocabulary.json").read_text(encoding="utf-8"))
        self.indices = {}
        for index, (word, pos) in enumerate(self.entries):
            self.indices.setdefault(word, []).append(index)
        targets = (data / "targets.txt").read_text(encoding="utf-8").splitlines()
        self.targets = sorted({normalize(w) for w in targets if normalize(w) in self.indices and any(self.entries[i][1] in {"n", "a"} for i in self.indices[normalize(w)])})
        if len(self.targets) < 10:
            raise ValueError("Le modèle contient trop peu de mots secrets admissibles.")
        self.lock = threading.Lock()
        self.cached = None

    def puzzle(self, day):
        with self.lock:
            if self.cached and self.cached[0] == day:
                return self.cached[1]
            choice = int.from_bytes(hashlib.sha256(("cementix-v1:" + day).encode()).digest()[:8], "big") % len(self.targets)
            target = self.targets[choice]
            senses = [i for i in self.indices[target] if self.entries[i][1] in {"n", "a"}]
            scores = np.full(len(self.entries), -1.0, dtype="float32")
            for sense in senses:
                np.maximum(scores, self.vectors @ self.vectors[sense], out=scores)
            by_word = {word: float(np.max(scores[indices])) for word, indices in self.indices.items()}
            near = sorted(((w, s) for w, s in by_word.items() if w != target), key=lambda x: (-x[1], x[0]))[:999]
            ranks = {word: 999 - i for i, (word, _) in enumerate(near)}
            ranks[target] = 1000
            thresholds = {str(rank): round(near[999 - rank][1] * 100, 2) for rank in (1, 900, 990) if 999 - rank < len(near)}
            puzzle = {"target": target, "scores": by_word, "ranks": ranks, "thresholds": thresholds}
            self.cached = (day, puzzle)
            return puzzle

    def guess(self, day, word):
        if len(word) > 64 or not WORD_RE.fullmatch(word):
            raise ValueError("Proposez un seul mot français, sans chiffre ni espace.")
        if word not in self.indices:
            raise ValueError("Ce mot n’est pas dans le vocabulaire. Vérifiez l’orthographe et les accents.")
        puzzle = self.puzzle(day)
        won = word == puzzle["target"]
        return {"word": word, "temperature": 100.0 if won else min(99.99, round(puzzle["scores"][word] * 100, 2)), "progress": puzzle["ranks"].get(word), "won": won}
