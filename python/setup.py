"""Build-time hook: copy the canonical ../data/*.txt tracker lists into
link_scrub/data/ before the wheel is built, so a real (non-editable)
install is self-contained.

This is the only reason a setup.py exists alongside pyproject.toml --
everything else is declarative there. The canonical lists still live in
one place (../data/, shared with rust_core); this copies a snapshot in at
build time rather than hand-duplicating them, so "one source of truth"
(see the repo root README's Laws) still holds for anyone editing the
lists -- they edit ../data/, never link_scrub/data/.
"""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

HERE = Path(__file__).resolve().parent
SOURCE_DATA = HERE.parent / "data"
PACKAGED_DATA = HERE / "link_scrub" / "data"


class build_py(_build_py):
    def run(self):
        PACKAGED_DATA.mkdir(parents=True, exist_ok=True)
        for src in SOURCE_DATA.glob("*.txt"):
            shutil.copy2(src, PACKAGED_DATA / src.name)
        super().run()


setup(cmdclass={"build_py": build_py})
