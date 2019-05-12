from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='bankroll',
    version='0.2.0',
    author='Justin Spahr-Summers',
    author_email='justin@jspahrsummers.com',
    description=
    'Ingest portfolio and other data from multiple brokerages, and analyze it',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    url='https://github.com/jspahrsummers/bankroll',
    packages=find_packages(),
    package_data={'bankroll': ['bankroll.default.ini']},
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
        'ib-insync>=0.9.47',
        'progress>=1.5',
        'backoff>=1.8',
        'pyfolio>=0.9.0',
    ],
    keywords=
    'trading investing finance portfolio ib ibkr tws schwab fidelity vanguard',
    entry_points={'console_scripts': ['bankroll = bankroll.__main__:main']})