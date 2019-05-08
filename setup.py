from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='bankroll',
    version='0.1.0',
    author='Justin Spahr-Summers',
    author_email='justin@jspahrsummers.com',
    description=
    'Ingest portfolio and other data from multiple brokerages, and analyze it',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    url='https://github.com/jspahrsummers/bankroll',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # ibapi is also a required package, but has no automated installation
    install_requires=[
        'ib-insync>=0.9',
        'progress>=1.5',
        'backoff>=1.8',
    ],
    entry_points={'console_scripts': ['bankroll = bankroll.__main__:main']})