from setuptools import setup

setup(
    name='bankroll',
    version='0.1.0',
    author='Justin Spahr-Summers',
    author_email='justin@jspahrsummers.com',
    description=
    'Ingest portfolio and other data from multiple brokerages, and analyze it',
    license='MIT',
    url='https://github.com/jspahrsummers/bankroll',
    packages=['bankroll'],
    entry_points={'console_scripts': ['bankroll = bankroll.__main__:main']})