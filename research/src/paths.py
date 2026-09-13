"""Project paths and small shared helpers."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ROOT)
DATA = os.path.join(REPO, "datasets")
RAW = os.path.join(DATA, "raw")
ANNOTATIONS = os.path.join(DATA, "annotations")
PROCESSED = os.path.join(DATA, "processed")
RESULTS = os.path.join(ROOT, "results")
EXPLORATORY = os.path.join(RESULTS, "exploratory")
FINAL = os.path.join(RESULTS, "final")
FIGURES = os.path.join(ROOT, "figures")
DOCS = os.path.join(REPO, "docs")
CACHE = os.path.join(DATA, "cache")

TB2_PARQUET = os.path.join(RAW, "tb2", "train-00000-of-00002.parquet")
NEBIUS_DIR = os.path.join(RAW, "nebius")

for _d in (PROCESSED, RESULTS, EXPLORATORY, FINAL, FIGURES, DOCS, CACHE):
    os.makedirs(_d, exist_ok=True)
