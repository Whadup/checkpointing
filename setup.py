# autogenerated setup.py for this project
from setuptools import setup, find_packages

setup(
    name="checkpointing",
    version="0.1",
    description="Checkpoint and resume long-running computations",
    author="Lukas Pfahler",
    author_email="lukas@lukaspfahler.de ",
    packages=find_packages(),
    install_requires=["dill"],
    include_package_data=True,
    zip_safe=False
)