from setuptools import setup, find_packages


def read_requirements():
    with open("requirements.txt") as req:
        install_requires = req.read().splitlines()
    return install_requires


setup(
    name="pyjourney",
    version="0.1",
    packages=find_packages(),
    install_requires=read_requirements(),
)
