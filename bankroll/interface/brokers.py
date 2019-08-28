try:
    import bankroll.brokers.ibkr as ibkr
except ImportError:
    ibkr = None  # type: ignore

try:
    import bankroll.brokers.schwab as schwab
except ImportError:
    schwab = None  # type: ignore

try:
    import bankroll.brokers.fidelity as fidelity
except ImportError:
    fidelity = None  # type: ignore

try:
    import bankroll.brokers.vanguard as vanguard
except ImportError:
    vanguard = None  # type: ignore