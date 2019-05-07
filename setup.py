from setuptools import setup, find_packages

setup(
    name='bankroll',
    version='0.1.0',
    author='Justin Spahr-Summers',
    author_email='justin@jspahrsummers.com',
    description=
    'Ingest portfolio and other data from multiple brokerages, and analyze it',
    license='MIT',
    url='https://github.com/jspahrsummers/bankroll',
    packages=find_packages(),
    entry_points={'console_scripts': ['bankroll = bankroll.__main__:main']})