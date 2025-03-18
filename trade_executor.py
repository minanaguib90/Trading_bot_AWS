import ccxt
import time
import logging
import threading
from decimal import Decimal
from typing import Dict, Optional, List, Any
from config import AccountConfig

class BybitTradeExecutor:
    def __init__(self, account_id: str, config: AccountConfig):
        self.account_id = account_id
        self.config = config
        self.trading_enabled = True
        self.monitoring_active = config.monitoring_active
        self.trade_history: List[Dict[str, Any]] = []
        self.failed_trades: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []
        self.profit_locks: Dict[str, List[Dict[str, Any]]] = {}
        self.total_profit_locks = 0
        self.logger = logging.getLogger(f"BybitTradeExecutor_{account_id}")

        # Initialize CCXT
        self.exchange = ccxt.bybit({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear',
                'adjustForTimeDifference': True,
                'test': config.is_testnet
            }
        })

        # Start monitoring thread if enabled
        if self.monitoring_active:
            self.start_profit_monitor()

    def get_wallet_balance(self) -> float:
        """Get wallet balance in USDT"""
        try:
            balance = self.exchange.fetch_balance()
            total_balance = float(balance['USDT']['total'])
            self.logger.info(f"Current wallet balance: {total_balance} USDT")
            
            # Check balance threshold
            if total_balance < self.config.balance_threshold:
                self.logger.warning(f"Balance {total_balance} below threshold {self.config.balance_threshold}")
                self.close_all_positions()
                self.trading_enabled = False
                
            return total_balance
        except Exception as e:
            self.logger.error(f"Failed to get wallet balance: {e}")
            raise

    def close_all_positions(self) -> None:
        """Close all open positions"""
        try:
            positions = self.exchange.fetch_positions()
            for position in positions:
                if abs(float(position['contracts'])) > 0:
                    self.exchange.create_market_order(
                        symbol=position['symbol'],
                        type='market',
                        side='sell' if position['side'] == 'buy' else 'buy',
                        amount=abs(float(position['contracts'])),
                        params={'reduce_only': True}
                    )
            self.logger.info("All positions closed due to balance threshold")
        except Exception as e:
            self.logger.error(f"Failed to close all positions: {e}")

    def set_leverage(self, symbol: str) -> None:
        """Set leverage for the trading pair"""
        try:
            self.exchange.set_leverage(self.config.leverage, symbol)
            self.logger.info(f"Leverage set to {self.config.leverage}x for {symbol}")
        except Exception as e:
            if 'leverage not modified' not in str(e).lower():
                self.logger.error(f"Failed to set leverage: {e}")

    def calculate_position_size(self, symbol: str, multiply_factor: float = 1.0) -> tuple:
        """Calculate position size based on risk percentage and balance"""
        try:
            balance = self.get_wallet_balance()
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            
            # Calculate position size based on risk
            risk_amount = balance * (self.config.risk_percentage / 100) * self.config.leverage
            raw_position_size = (risk_amount / current_price) * multiply_factor
            
            # Get market precision
            market = self.exchange.market(symbol)
            amount_precision = market['precision']['amount']
            
            # Round position size according to market precision
            position_size = self.exchange.amount_to_precision(symbol, raw_position_size)
            
            return float(position_size), current_price
        except Exception as e:
            self.logger.error(f"Failed to calculate position size: {e}")
            raise

    def check_existing_position(self, symbol: str) -> Optional[Dict]:
        """Check if there's an existing position for the symbol"""
        try:
            positions = self.exchange.fetch_positions([symbol])
            for position in positions:
                if abs(float(position['contracts'])) > 0.00001:
                    return position
            return None
        except Exception as e:
            self.logger.error(f"Failed to check positions: {e}")
            raise

    def place_order(self, symbol: str, side: str, tp_order_type: str = 'limit', 
                   sl_order_type: str = 'market') -> Dict:
        """Place a market order with TP/SL"""
        try:
            if not self.trading_enabled:
                return {"status": "error", "message": "Trading is disabled"}

            # Check for existing position
            existing_position = self.check_existing_position(symbol)
            position_multiplier = 2 if existing_position and self.is_opposite_side(existing_position, side) else 1

            # Set leverage
            self.set_leverage(symbol)

            # Calculate position size
            position_size, entry_price = self.calculate_position_size(symbol, position_multiplier)

            # Calculate TP/SL prices
            tp_price = entry_price * (1 + self.config.initial_tp_percentage) if side.lower() == 'buy' \
                else entry_price * (1 - self.config.initial_tp_percentage)
            sl_price = entry_price * (1 - self.config.initial_sl_percentage) if side.lower() == 'buy' \
                else entry_price * (1 + self.config.initial_sl_percentage)

            # Place the order
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side.lower(),
                amount=position_size,
                params={
                    'takeProfit': self.exchange.price_to_precision(symbol, tp_price),
                    'stopLoss': self.exchange.price_to_precision(symbol, sl_price),
                    'tpTriggerBy': 'LastPrice',
                    'slTriggerBy': 'LastPrice',
                    'reduceOnly': False,
                }
            )

            self._log_trade({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'side': side,
                'size': position_size,
                'entry_price': entry_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'order': order
            })

            return {"status": "success", "order": order}

        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return {"status": "error", "message": str(e)}

    def start_profit_monitor(self) -> None:
        """Start the profit monitoring thread"""
        try:
            self.monitor_thread = threading.Thread(target=self.monitor_positions_profit)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            self.logger.info(f"Monitor thread started for account {self.account_id}")
        except Exception as e:
            self.logger.error(f"Failed to start monitoring thread: {e}")

    def monitor_positions_profit(self) -> None:
        """Monitor positions for profit targets and update stop losses"""
        while self.monitoring_active:
            try:
                positions = self.exchange.fetch_positions()
                
                for position in positions:
                    if abs(float(position['contracts'])) <= 0.00001:
                        continue

                    symbol = position['symbol']
                    unrealized_pnl = float(position['unrealizedPnl'])
                    entry_price = float(position['entryPrice'])
                    current_price = float(position['markPrice'])
                    position_size = abs(float(position['contracts']))

                    # Calculate profit percentage
                    profit_percentage = (unrealized_pnl / (entry_price * position_size)) * 100 * self.config.leverage

                    if profit_percentage >= self.config.profit_lock_threshold * 100:
                        self.update_stop_loss(position)
                        self._record_profit_lock(symbol, profit_percentage)

                time.sleep(5)

            except Exception as e:
                self.logger.error(f"Error in monitor: {e}")
                time.sleep(5)

    def update_stop_loss(self, position: Dict) -> None:
        """Update stop loss for a position"""
        try:
            symbol = position['symbol']
            current_price = float(position['markPrice'])
            side = position['side']

            # Calculate new stop loss (1% trailing for long, 0.1% for short)
            new_sl = current_price * 0.99 if side == 'buy' else current_price * 1.001
            
            self.exchange.create_order(
                symbol=symbol,
                type='stop',
                side='sell' if side == 'buy' else 'buy',
                amount=abs(float(position['contracts'])),
                price=self.exchange.price_to_precision(symbol, new_sl),
                params={
                    'triggerPrice': new_sl,
                    'reduceOnly': True,
                    'triggerBy': 'MarkPrice'
                }
            )
            
            self.logger.info(f"Updated stop loss for {symbol} to {new_sl}")
        except Exception as e:
            self.logger.error(f"Failed to update stop loss: {e}")

    def _record_profit_lock(self, symbol: str, profit_percentage: float) -> None:
        """Record profit lock event"""
        if symbol not in self.profit_locks:
            self.profit_locks[symbol] = []

        self.profit_locks[symbol].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'profit_percentage': profit_percentage
        })
        self.total_profit_locks += 1
        self.logger.info(f"Profit lock #{self.total_profit_locks} triggered for {symbol}")

    def _log_trade(self, trade_data: Dict) -> None:
        """Log trade details"""
        self.trade_history.append(trade_data)
        self.logger.info(f"Trade logged: {trade_data}")

    @staticmethod
    def is_opposite_side(existing_position: Dict, new_side: str) -> bool:
        """Check if new trade is opposite to existing position"""
        return (existing_position['side'] == 'buy' and new_side.lower() == 'sell') or \
               (existing_position['side'] == 'sell' and new_side.lower() == 'buy')
