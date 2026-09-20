"""Include the authoritative top-level data directory in built wheels."""
from pathlib import Path
from shutil import copytree
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithData(build_py):
    def run(self):
        super().run()
        copytree(Path(__file__).parent / "data", Path(self.build_lib) / "whowouldwin" / "data", dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildWithData})
