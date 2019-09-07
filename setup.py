from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="bankroll",
    version="0.4.1",
    author="Justin Spahr-Summers",
    author_email="justin@jspahrsummers.com",
    description="Ingest portfolio and other data from multiple brokerages, and analyze it",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/bankroll-py/bankroll",
    packages=["bankroll.analysis", "bankroll.interface"],
    package_data={
        "bankroll.analysis": ["py.typed"],
        "bankroll.interface": ["bankroll.default.ini", "py.typed"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Framework :: Jupyter",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3",
        "Topic :: Office/Business :: Financial :: Investment",
        "Typing :: Typed",
    ],
    install_requires=[
        "bankroll_marketdata ~= 0.4.0",
        "bankroll_model ~= 0.4.0",
        "bankroll_broker ~= 0.4.1",
        "numpy ~= 1.17.0",
        "progress ~= 1.5",
        "pyfolio >= 0.9.2",
    ],
    extras_require={
        "ibkr": ["bankroll_broker_ibkr ~= 0.4.0"],
        "schwab": ["bankroll_broker_schwab ~= 0.4.0"],
        "fidelity": ["bankroll_broker_fidelity ~= 0.4.0"],
        "vanguard": ["bankroll_broker_vanguard ~= 0.4.0"],
    },
    keywords="trading investing finance portfolio",
    entry_points={"console_scripts": ["bankroll = bankroll.interface.__main__:main"]},
)
