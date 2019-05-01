# bankroll [![CircleCI](https://circleci.com/gh/jspahrsummers/bankroll.svg?style=svg&circle-token=c2eceb857210b420215d7fdba4aa480e72c57fc3)](https://circleci.com/gh/jspahrsummers/bankroll)
Ingest portfolio and other data from multiple brokerages, and analyze it.

**Table of contents:**

1. [Getting started](#getting-started)
1. [Connecting to brokers](#connecting-to-brokers)
   1. [Interactive Brokers](#interactive-brokers)
   1. [Charles Schwab](#charles-schwab)
   1. [Fidelity](#fidelity)
   1. [Vanguard](#vanguard)
1. [Extending `bankroll`](#extending-bankroll)

# Getting started

The included bootstrap script will set up a Python virtual environment and install the necessary dependencies, including the [Interactive Brokers API](http://interactivebrokers.github.io):

```
script/bootstrap
```

After bootstrapping, confirm that the environment works by running the included test suite:

```
script/test
```

# Connecting to brokers

After being set up, `bankroll` can be used from the command line to bring together data from multiple brokerages.

For example, to show all positions held in both Interactive Brokers and Charles Schwab:

```
python3 bankroll.py \
  --twsport 7496 \
  --schwabpositions ~/Positions-2019-01-01.CSV \
  --schwabtransactions ~/Transactions_20190101.CSV \
  positions
```

Run with `-h` to see all options:

```
python3 bankroll.py -h
```

## Interactive Brokers

[Interactive Brokers](http://interactivebrokers.com) (sometimes abbreviated as IB or IBKR) offers a well-supported [API](https://interactivebrokers.github.io/), which—along with [ib_insync](https://github.com/erdewit/ib_insync)—makes it possible to load up-to-date portfolio data and request real-time information about particular securities.

Because this integration is so useful, **some generic functionality in `bankroll` will require an IB account.**

Unfortunately, [one of IB's trading applications](https://interactivebrokers.github.io/tws-api/initial_setup.html)—Trader Workstation or IB Gateway—must be running and logged-in to accept API connections. You may wish to use [IBC](https://github.com/IbcAlpha/IBC) to automate the startup and login of these applications.

Once Trader Workstation or IB Gateway is running, and [API connections are enabled](https://interactivebrokers.github.io/tws-api/initial_setup.html#enable_api), provide the local port number to `bankroll` like so:

```
python3 bankroll.py \
  --twsport 7496 \
  [command]
```

### Querying trade history

IB's [Trader Workstation API](https://interactivebrokers.github.io/tws-api/) does not support retrieving information about an account's historical trades, so `bankroll` must use their [Flex Web Service](https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm).

To set this up, log in to [Account Management](https://www.interactivebrokers.com/portal), then browse to _Settings_ → _Account Settings_ in the sidebar:

<img width="312" alt="Account Settings" src="https://user-images.githubusercontent.com/432536/55676482-17f5c200-58ce-11e9-8560-a42fe755752b.png">

In the _Reporting_ section of this page, click the gear to configure _Flex Web Service_:

<img width="444" alt="Flex Web Service" src="https://user-images.githubusercontent.com/432536/55676518-b124d880-58ce-11e9-802c-842d1e17dd42.png">

**Once configured, copy the _Current Token_ for use on the command line.**

Then, you must save a query for `bankroll` to use. Back in the sidebar, browse to _Reports_ → _Flex Queries_:

<img width="309" alt="Flex Queries" src="https://user-images.githubusercontent.com/432536/55676496-4ffd0500-58ce-11e9-9a2b-d530b2d0c5c9.png">

Click the gear to configure _Custom Flex Queries_:

<img width="445" alt="Custom Flex Queries" src="https://user-images.githubusercontent.com/432536/55676519-b124d880-58ce-11e9-901d-0482d2e0e1cf.png">

Create a new Trade Confirmation Flex Query Template:

<img width="496" alt="Trade Confirmation Flex Query Templates" src="https://user-images.githubusercontent.com/432536/55676520-b124d880-58ce-11e9-9c2b-17b41e8a2fff.png">

Pick a name of your choosing, then make sure the _Date Period_ reflects the historical period you care about (e.g., _Last 365 Calendar Days_):

<img width="781" alt="Trade Confirmation Flex Query Details" src="https://user-images.githubusercontent.com/432536/55676521-b124d880-58ce-11e9-8b15-0232fd7ba795.png">

Under _Sections_, click _Trade Confirmations_ and enable everything in the dialog which appears:

<img width="175" alt="Trade Confirmation button" src="https://user-images.githubusercontent.com/432536/55676522-b124d880-58ce-11e9-997b-2129101cdd08.png">
<img width="808" alt="Trade Confirmation options" src="https://user-images.githubusercontent.com/432536/55676517-b124d880-58ce-11e9-93d0-dbee91862c04.png">

**After saving your query, expand it in the list to view and copy the _Query ID_ for use on the command line.**

With the token and the query ID from your account, historical trades can be downloaded:

```
python3 bankroll.py \
  --flextoken [token] \
  --flexquery [query ID] \
  trades
```

## Charles Schwab

[Charles Schwab](https://www.schwab.com) does not offer an API, but it does provide [CSV](https://en.wikipedia.org/wiki/Comma-separated_values) files for export, which `bankroll` can then import.

Browse to the "Positions" and/or "Transactions" screen:

<img width="559" alt="Positions and Transactions" src="https://user-images.githubusercontent.com/432536/55676591-dfef7e80-58cf-11e9-91e1-845caf625e85.png">

Click the "Export" link in the top-right:

<img width="219" alt="Export" src="https://user-images.githubusercontent.com/432536/55676579-825b3200-58cf-11e9-8626-793d1d465e70.png">

Then provide the paths of either or both these downloaded files to `bankroll`:

```
python3 bankroll.py \
  --schwabpositions ~/path/to/Positions.CSV \
  --schwabtransactions ~/path/to/Transactions.CSV \
  [command]
```

## Fidelity

[Fidelity](https://www.fidelity.com) is supported through a similar facility as [Schwab](#charles-schwab). More detailed instructions have yet to be written—[contributions welcome](CONTRIBUTING.md)!

## Vanguard

[Vanguard](https://investor.vanguard.com) is a **work in progress**, and may not be as fully-featured as the other brokerages listed here. [Contributions welcome](CONTRIBUTING.md)!

# Extending `bankroll`

Although the command-line interface exposes a basic set of functionality, it will never be able to capture the full set of possible use cases. For much greater flexibility, you can write Python code to use `bankroll` directly, and build on top of its APIs for your own purposes.

For some examples, [see the included notebooks](notebooks/).
