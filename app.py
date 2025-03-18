import os
import logging
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from config import ACCOUNT_CONFIGS, FLASK_CONFIG, LOGGING_CONFIG
from trade_executor import BybitTradeExecutor
import threading

def cleanup_logs():
    """Delete log files older than 48 hours"""
    while True:
        try:
            current_time = datetime.now()
            log_dir = os.path.dirname(LOGGING_CONFIG['log_file'])
            
            for filename in os.listdir(log_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(log_dir, filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if current_time - file_modified > timedelta(hours=LOGGING_CONFIG['retention_hours']):
                        os.remove(file_path)
                        logger.info(f"Deleted old log file: {filename}")
            
            # Sleep before next cleanup
            time.sleep(LOGGING_CONFIG['cleanup_interval'])
            
        except Exception as e:
            logger.error(f"Error in log cleanup: {e}")
            time.sleep(LOGGING_CONFIG['cleanup_interval'])  # Still sleep on error

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
handler = RotatingFileHandler(
    LOGGING_CONFIG['log_file'],
    maxBytes=LOGGING_CONFIG['max_bytes'],
    backupCount=LOGGING_CONFIG['backup_count']
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOGGING_CONFIG['log_level']))
logger.addHandler(handler)

# Also add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Initialize Flask app
app = Flask(__name__)

# Initialize trade executors for each account
trade_executors = {
    account_id: BybitTradeExecutor(account_id, config)
    for account_id, config in ACCOUNT_CONFIGS.items()
}

# Start log cleanup thread
cleanup_thread = threading.Thread(target=cleanup_logs, daemon=True)
cleanup_thread.start()
logger.info("Log cleanup thread started")

# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        # Log incoming webhook
        logger.info(f"Received webhook: {data}")
        
        # Validate required fields
        required_fields = ['side', 'symbol']
        if not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {required_fields}"
            }), 400

        # Process the signal for each account
        responses = {}
        for account_id, executor in trade_executors.items():
            try:
                if not executor.trading_enabled:
                    responses[account_id] = {
                        "status": "error",
                        "message": f"Trading is disabled for account {account_id}"
                    }
                    continue

                # Place the order
                response = executor.place_order(
                    symbol=data['symbol'],
                    side=data['side'],
                    tp_order_type=data.get('tpOrderType', 'limit'),
                    sl_order_type=data.get('slOrderType', 'market')
                )
                
                responses[account_id] = response
                
            except Exception as e:
                logger.error(f"Error processing order for account {account_id}: {e}")
                responses[account_id] = {
                    "status": "error",
                    "message": str(e)
                }

        return jsonify({
            "status": "success",
            "responses": responses
        })

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/account/<account_id>/status', methods=['GET'])
def get_account_status(account_id):
    """Get status for a specific account"""
    if account_id not in trade_executors:
        return jsonify({
            "status": "error",
            "message": f"Account {account_id} not found"
        }), 404

    executor = trade_executors[account_id]
    try:
        return jsonify({
            "status": "success",
            "data": {
                "trading_enabled": executor.trading_enabled,
                "monitoring_active": executor.monitoring_active,
                "total_trades": len(executor.trade_history),
                "failed_trades": len(executor.failed_trades),
                "total_profit_locks": executor.total_profit_locks,
                "balance": executor.get_wallet_balance()
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/account/<account_id>/trades', methods=['GET'])
def get_account_trades(account_id):
    """Get trade history for a specific account"""
    if account_id not in trade_executors:
        return jsonify({
            "status": "error",
            "message": f"Account {account_id} not found"
        }), 404

    executor = trade_executors[account_id]
    return jsonify({
        "status": "success",
        "data": {
            "trade_history": executor.trade_history,
            "failed_trades": executor.failed_trades
        }
    })

@app.route('/account/<account_id>/profit-locks', methods=['GET'])
def get_profit_locks(account_id):
    """Get profit lock history for a specific account"""
    if account_id not in trade_executors:
        return jsonify({
            "status": "error",
            "message": f"Account {account_id} not found"
        }), 404

    executor = trade_executors[account_id]
    return jsonify({
        "status": "success",
        "data": {
            "total_profit_locks": executor.total_profit_locks,
            "profit_locks": executor.profit_locks
        }
    })

@app.route('/account/<account_id>/control', methods=['POST'])
def control_account(account_id):
    """Control trading status for a specific account"""
    if account_id not in trade_executors:
        return jsonify({
            "status": "error",
            "message": f"Account {account_id} not found"
        }), 404

    try:
        data = request.get_json()
        action = data.get('action')
        executor = trade_executors[account_id]

        if action == 'pause':
            executor.trading_enabled = False
            message = "Trading paused"
        elif action == 'resume':
            executor.trading_enabled = True
            message = "Trading resumed"
        elif action == 'toggle_monitor':
            executor.monitoring_active = not executor.monitoring_active
            message = f"Monitoring {'enabled' if executor.monitoring_active else 'disabled'}"
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid action"
            }), 400

        return jsonify({
            "status": "success",
            "message": message,
            "account_id": account_id
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/accounts', methods=['GET'])
def list_accounts():
    """List all accounts and their basic status"""
    try:
        accounts_status = {}
        for account_id, executor in trade_executors.items():
            accounts_status[account_id] = {
                "trading_enabled": executor.trading_enabled,
                "monitoring_active": executor.monitoring_active,
                "total_trades": len(executor.trade_history),
                "total_profit_locks": executor.total_profit_locks
            }
        
        return jsonify({
            "status": "success",
            "accounts": accounts_status
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(
        host=FLASK_CONFIG['host'],
        port=FLASK_CONFIG['port'],
        debug=FLASK_CONFIG['debug']
    )
