from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    readme = f.read()

with open("LICENSE", encoding="utf-8") as f:
    license = f.read()

setup(
    name="utun",
    version="0.1.0",
    description="A small tool for tunneling UDP over TCP",
    long_description=readme,
    author="tama@ttk1",
    author_email="tama@ttk1.net",
    url="https://github.com/ttk1/utun",
    license=license,
    packages=find_packages(exclude=("test",)),
    entry_points={
        "console_scripts": [
            "utun-frontend = utun.command:frontend",
            "utun-backend = utun.command:backend",
        ]
    },
)
