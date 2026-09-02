from setuptools import setup, find_packages

setup(
    name="mygit",
    version="0.1.0",
    packages=find_packages(exclude=["tests*"]),
    entry_points={
        "console_scripts": [
            "mygit=mygit.cli:main",
        ],
    },
    python_requires=">=3.8",
)
