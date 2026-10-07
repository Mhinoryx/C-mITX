"""Download and normalize Fauconnier's original binary word2vec model."""
import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
import numpy as np

DATA = Path(__file__).resolve().parent / "data"
NAME = "frWac_postag_no_phrase_700_skip_cut50.bin"
URL = "https://embeddings.net/embeddings/" + NAME
MD5 = "0695f811c5f76a51bc335633213d2aa8"

def checksum(path):
    digest = hashlib.md5()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def download(path):
    temporary = path.with_suffix(".part")
    print("Téléchargement du modèle frWac (~577 Mo)...", flush=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "CemITX/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as target:
        total = int(response.headers.get("Content-Length", 0))
        received, last = 0, 0
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
            received += len(chunk)
            if received - last >= 25 * 1024 * 1024:
                print(f"  {received / 1024**2:.0f} Mo" + (f" / {total / 1024**2:.0f} Mo" if total else ""), flush=True)
                last = received
    if checksum(temporary) != MD5:
        raise ValueError("Somme MD5 incorrecte : relancez le téléchargement.")
    temporary.replace(path)

def convert(source):
    vocabulary = []
    cache = DATA / "vectors.tmp.npy"
    with source.open("rb") as stream:
        count, dimensions = map(int, stream.readline().split())
        vectors = np.lib.format.open_memmap(cache, mode="w+", dtype="float32", shape=(count, dimensions))
        kept = 0
        for index in range(count):
            token = bytearray()
            while True:
                char = stream.read(1)
                if not char:
                    raise ValueError("Modèle tronqué (mot).")
                if char == b" ":
                    break
                if char not in (b"\n", b"\r"):
                    token.extend(char)
            raw = stream.read(dimensions * 4)
            if len(raw) != dimensions * 4:
                raise ValueError("Modèle tronqué (vecteur).")
            try:
                text = token.decode("utf-8")
            except UnicodeDecodeError:
                continue
            word, separator, pos = text.rpartition("_")
            if not separator or pos not in {"n", "a", "v", "adv"}:
                continue
            if word != word.lower() or not re.fullmatch(r"[^\W\d_]+(?:-[^\W\d_]+)*", word, re.UNICODE):
                continue
            vector = np.frombuffer(raw, dtype="<f4")
            norm = float(np.linalg.norm(vector))
            if not np.isfinite(norm) or norm <= 0:
                continue
            vectors[kept] = vector / norm
            vocabulary.append([word, pos])
            kept += 1
            if (index + 1) % 25000 == 0:
                print(f"  Lecture : {index + 1}/{count}", flush=True)
        output = np.lib.format.open_memmap(DATA / "vectors.new.npy", mode="w+", dtype="float32", shape=(kept, dimensions))
        for start in range(0, kept, 4096):
            end = min(start + 4096, kept)
            output[start:end] = vectors[start:end]
        output.flush()
        del output, vectors
    (DATA / "vectors.new.npy").replace(DATA / "vectors.npy")
    cache.unlink()
    temporary = DATA / "vocabulary.tmp.json"
    temporary.write_text(json.dumps(vocabulary, ensure_ascii=False), encoding="utf-8")
    temporary.replace(DATA / "vocabulary.json")
    print(f"Prêt : {kept:,} vecteurs de {dimensions} dimensions.", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Modèle officiel déjà téléchargé")
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    path = args.source or DATA / NAME
    if not path.exists():
        if args.source:
            parser.error("Le fichier --source n'existe pas.")
        download(path)
    elif checksum(path) != MD5:
        raise ValueError("Le modèle ne correspond pas au MD5 publié par l'auteur.")
    convert(path)
