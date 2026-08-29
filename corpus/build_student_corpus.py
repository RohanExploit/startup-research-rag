"""Render every registered document in corpus/render_academic.DOCS to corpus/out/.

    PYTHONUTF8=1 .venv312/Scripts/python.exe corpus/build_student_corpus.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from corpus.render_academic import DOCS, OUT  # noqa: E402


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in DOCS.items():
        doc = builder()
        path = doc.save()
        print(f"rendered {name} -> {path}")
    print(f"rendered {len(DOCS)} PDFs -> {OUT}")


if __name__ == "__main__":
    main()
