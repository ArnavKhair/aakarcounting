"""Filesystem locations used across the app, resolved from this file so they
do not depend on the process working directory."""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_DIR = os.path.join(PROJECT_ROOT, "models", "weights")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")


def ensure_weights_dir() -> str:
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    return WEIGHTS_DIR
