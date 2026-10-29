"""Root-level build hook, mirroring python/setup.py's logic but for
pyproject.toml (this file's sibling), the config used when something
installs this repo from its ROOT -- pre-commit's `language: python` hooks
being the real-world case that made this necessary (see pyproject.toml's
own header comment and round 18 of docs/CRITIQUE_LEDGER.md).

Copies the canonical data/*.txt into python/link_scrub/data/ at build
time, same destination python/setup.py's hook uses, so the two never
disagree about where the packaged snapshot lives.
"""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

HERE = Path(__file__).resolve().parent
SOURCE_DATA = HERE / "data"
PACKAGED_DATA = HERE / "python" / "link_scrub" / "data"


class build_py(_build_py):
    def run(self):
        PACKAGED_DATA.mkdir(parents=True, exist_ok=True)
        for src in SOURCE_DATA.glob("*.txt"):
            shutil.copy2(src, PACKAGED_DATA / src.name)
        super().run()


setup(cmdclass={"build_py": build_py})
