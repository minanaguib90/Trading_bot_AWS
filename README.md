# Multi-Account Bybit Trading Bot

A Flask-based webhook server that handles TradingView signals and executes trades on multiple Bybit accounts with different configurations.

## Features

- Multi-account support with independent configurations
- Profit monitoring and trailing stop-loss
- Balance threshold monitoring
- Configurable risk management per account
- Trade history and statistics tracking
- REST API endpoints for monitoring and control
- Automatic log cleanup (files older than 48 hours)

## Setup

1. Clone this repository:
```bash
git clone https://github.com/yourusername/trading-bot.git
cd trading-bot
```

2. Install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Edit `config.py` to set your API keys and trading parameters.

4. Run the bot:
```bash
python app.py
```

5. For production deployment, use the provided deploy script:
```bash
chmod +x deploy.sh
./deploy.sh
```

## Webhook Endpoint

Send trade signals to:
