from setuptools import setup, find_packages

with open('requirements.txt', encoding='utf-8') as f:
    required = f.read().splitlines()

setup(
    name="hey-aura",
    version="0.1",
    packages=find_packages(),
    install_requires=required,
    python_requires='>=3.10',
)
