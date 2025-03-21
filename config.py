from typing import Dict, Optional

class AccountConfig:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        risk_percentage: float = 1.0,
        leverage: int = 5,
        profit_lock_threshold: float = 0.1,
        monitoring_active: bool = True,
        initial_sl_percentage: float = 0.05,
        initial_tp_percentage: float = 0.3,
        balance_threshold: float = 100,  # Minimum balance in USDT
        is_testnet: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.risk_percentage = risk_percentage
        self.leverage = leverage
        self.profit_lock_threshold = profit_lock_threshold
        self.monitoring_active = monitoring_active
        self.initial_sl_percentage = initial_sl_percentage
        self.initial_tp_percentage = initial_tp_percentage
        self.balance_threshold = balance_threshold
        self.is_testnet = is_testnet

# Example configuration for multiple accounts
ACCOUNT_CONFIGS: Dict[str, AccountConfig] = {
    "account1": AccountConfig(
        api_key="V16KsyDK3O6llAdj4T",
        api_secret="kAKNU7nqs0XGeAjyiB8SMJj4zsJPYpcqqPaq",
        risk_percentage=1.0,
        leverage=5,
        profit_lock_threshold=0.1,
        monitoring_active=True,
        initial_sl_percentage=0.05,
        initial_tp_percentage=0.3,
        balance_threshold=100,
        is_testnet=True
    ),
    "account2": AccountConfig(
        api_key="Jdf9kBtmhuCRhTXkOb",
        api_secret="WtL1aoywRgzXnINyv0oTEF4WwxJVX5v0ACYm",
        risk_percentage=2.0,
        leverage=10,
        profit_lock_threshold=0.15,
        monitoring_active=True,
        initial_sl_percentage=0.08,
        initial_tp_percentage=0.4,
        balance_threshold=200,
        is_testnet=True
    ),
    # Add more accounts as needed
}

# Flask server configuration
FLASK_CONFIG = {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": False
}

# Logging configuration
LOGGING_CONFIG = {
    "log_file": "logs/trading_bot.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
    "log_level": "INFO",
    "retention_hours": 48,  # Keep logs for 48 hours
    "cleanup_interval": 3600  # Check for old logs every hour
}
