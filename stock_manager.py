"""
Stock market manager for the Monopoly Bank app.
Handles stock prices, trading, dividends, and news events.
"""

import json
import random
import math
import uuid
from threading import Lock
import numpy as np


class Stock:
    """Represents a single stock."""
    def __init__(self, name, sector, price, volatility, dividend):
        self.name = name
        self.sector = sector
        self.price = price
        self.volatility = volatility
        self.dividend = dividend
        self.history = [price]  # Price history for charts
        self.shares_owned = {}  # {player_id: num_shares}
        self.purchase_prices = {}  # {player_id: total_cost} for calculating average price

    def to_dict(self, player_id=None):
        """Return stock as dictionary. If player_id provided, include their average purchase price."""
        result = {
            'name': self.name,
            'sector': self.sector,
            'price': round(self.price, 2),
            'volatility': self.volatility,
            'dividend': self.dividend,
            'history': self.history[-20:],  # Last 20 prices for chart
            'shares_owned': self.shares_owned
        }
        
        # Include average purchase price if player_id is provided
        if player_id and player_id in self.purchase_prices and player_id in self.shares_owned:
            total_cost = self.purchase_prices[player_id]
            shares = self.shares_owned[player_id]
            if shares > 0:
                avg_price = total_cost / shares
                result['avg_purchase_price'] = round(avg_price, 2)
        
        return result


class Sector:
    """Represents a market sector."""
    def __init__(self, name, mu=0.0):
        self.name = name
        self.mu = mu  # Expected return
        self.index_trend = 0.0


class NewsEvent:
    """Represents a market news event."""
    def __init__(self, description, impact, affected_sector=None, affected_stock=None, duration=1):
        self.description = description
        self.impact = impact  # Percentage impact (e.g., 0.1 for +10%)
        self.affected_sector = affected_sector
        self.affected_stock = affected_stock
        self.duration = duration  # Ticks remaining
        self.turn_created = None

    def to_dict(self):
        """Return news event as dictionary."""
        return {
            'description': self.description,
            'impact': self.impact,
            'affected_sector': self.affected_sector,
            'affected_stock': self.affected_stock,
            'duration': self.duration,
            'turn_created': self.turn_created
        }


class StockManager:
    """Manages all stock market operations."""

    def __init__(self, stock_data_file, tlog_connection=None):
        """Initialize stock manager from JSON data file."""
        self.data_lock = Lock()
        self.tlog = tlog_connection  # Transaction log for recording transactions
        
        # Load stock data from JSON
        with open(stock_data_file, 'r') as f:
            data = json.load(f)
        
        # Initialize sectors
        self.sectors = {}
        for sector_data in data.get('sectors', []):
            sector = Sector(sector_data['name'], sector_data.get('mu', 0.0))
            self.sectors[sector.name] = sector
        
        # Initialize stocks
        self.stocks = {}
        for stock_data in data.get('stocks', []):
            stock = Stock(
                stock_data['name'],
                stock_data['sector'],
                stock_data['price'],
                stock_data['volatility'],
                stock_data['dividend']
            )
            if 'history' in stock_data:
                stock.history = stock_data['history']
            self.stocks[stock.name] = stock
        
        # Load predefined news events
        self.predefined_news = []
        for event_data in data.get('news_events', []):
            event = NewsEvent(
                event_data['description'],
                event_data['impact'],
                affected_sector=event_data.get('affected_sector'),
                affected_stock=event_data.get('affected_stock'),
                duration=event_data.get('duration', 1)
            )
            self.predefined_news.append(event)
        
        # Sector correlation matrix (Tech, Defense, Finance, Energy, Retail)
        self.sector_corr = np.array([
            [1.0, 0.2, 0.3, 0.15, 0.4],   # Tech
            [0.2, 1.0, 0.25, 0.1, 0.2],    # Defense
            [0.3, 0.25, 1.0, 0.35, 0.3],   # Finance
            [0.15, 0.1, 0.35, 1.0, 0.2],   # Energy
            [0.4, 0.2, 0.3, 0.2, 1.0]      # Retail
        ])
        
        self.sector_names = list(self.sectors.keys())
        self.active_news_events = []
        self.dividend_paid_this_turn = {}  # {player_id: paid} to prevent double-payment

    def generate_correlated_noise(self):
        """Generate correlated random noise per sector using multivariate normal."""
        mean = [0] * len(self.sector_names)
        cov = self.sector_corr
        return np.random.multivariate_normal(mean, cov)

    def update_stock_prices(self, tick_fraction=0.1):
        """Update all stock prices for this tick using GBM + sector trend + noise."""
        with self.data_lock:
            # Generate correlated noise for sectors
            noise = self.generate_correlated_noise()
            
            # Update sector trends
            for i, sector_name in enumerate(self.sector_names):
                sector = self.sectors[sector_name]
                sector.index_trend = sector.mu + noise[i] * 0.01  # Scale correlated noise
            
            # Update stock prices using geometric Brownian motion
            for stock in self.stocks.values():
                sector = self.sectors[stock.sector]
                Z = random.gauss(0, 1)
                
                # GBM formula: dS = mu*S*dt + sigma*S*sqrt(dt)*dZ
                drift = (sector.index_trend - 0.5 * stock.volatility ** 2) * tick_fraction
                diffusion = stock.volatility * math.sqrt(tick_fraction) * Z
                
                stock.price *= math.exp(drift + diffusion)
                stock.price = max(stock.price, 0.01)  # Prevent prices from going to zero
                
                # Record price in history
                stock.history.append(round(stock.price, 2))
                # Keep only last 100 prices
                if len(stock.history) > 100:
                    stock.history = stock.history[-100:]

    def generate_news_event(self, current_turn):
        """Randomly generate news events with various impact levels."""
        roll = random.random()
        
        if roll < 0.05:
            # Major catastrophic event
            sector = random.choice(self.sector_names)
            impact = -random.uniform(0.1, 0.3)
            event = NewsEvent(
                f"CATASTROPHE: {sector} sector collapse!",
                impact,
                affected_sector=sector,
                duration=3
            )
            event.turn_created = current_turn
            return event
        elif roll < 0.15:
            # Major booming event
            sector = random.choice(self.sector_names)
            impact = random.uniform(0.1, 0.3)
            event = NewsEvent(
                f"BOOM: {sector} sector surges!",
                impact,
                affected_sector=sector,
                duration=3
            )
            event.turn_created = current_turn
            return event
        elif roll < 0.3:
            # Minor sector event
            sector = random.choice(self.sector_names)
            impact = random.uniform(-0.05, 0.05)
            event = NewsEvent(
                f"Minor {sector} sector movement",
                impact,
                affected_sector=sector,
                duration=1
            )
            event.turn_created = current_turn
            return event
        elif roll < 0.4:
            # Individual stock event
            stock = random.choice(list(self.stocks.values()))
            impact = random.uniform(-0.1, 0.15)
            event = NewsEvent(
                f"{stock.name} stock-specific event",
                impact,
                affected_stock=stock.name,
                duration=2
            )
            event.turn_created = current_turn
            return event
        
        return None

    def apply_news_events(self):
        """Apply active news events to stocks and decrement duration."""
        with self.data_lock:
            for event in self.active_news_events[:]:
                if event.affected_stock:
                    stock = self.stocks.get(event.affected_stock)
                    if stock:
                        stock.price *= (1 + event.impact)
                        stock.price = max(stock.price, 0.01)
                elif event.affected_sector:
                    for stock in self.stocks.values():
                        if stock.sector == event.affected_sector:
                            stock.price *= (1 + event.impact)
                            stock.price = max(stock.price, 0.01)
                
                event.duration -= 1
                if event.duration <= 0:
                    self.active_news_events.remove(event)

    def market_index(self):
        """Get average stock price as market index."""
        if not self.stocks:
            return 0
        return sum(stock.price for stock in self.stocks.values()) / len(self.stocks)

    def buy_stock(self, player_id, stock_name, num_shares, account_manager):
        """Buy shares of a stock. Returns (success, message)."""
        with self.data_lock:
            if stock_name not in self.stocks:
                return False, f"Stock '{stock_name}' not found."
            
            stock = self.stocks[stock_name]
            total_cost = num_shares * stock.price
            
            # Check if player has enough cash
            player = account_manager.query(player_id)
            if player == 'Account does not exist.':
                return False, "Player account not found."
            
            if player.cash < total_cost:
                return False, f"Insufficient funds. Need ${total_cost:.2f}, have ${player.cash}."
            
            # Update shares owned while holding lock
            if player_id not in stock.shares_owned:
                stock.shares_owned[player_id] = 0
            stock.shares_owned[player_id] += num_shares
            
            # Track purchase price for average calculation
            if player_id not in stock.purchase_prices:
                stock.purchase_prices[player_id] = 0
            stock.purchase_prices[player_id] += total_cost
        
        # Perform transaction OUTSIDE the data_lock to avoid deadlock
        # player.withdraw handles its own locking, so we don't need to acquire write_lock here
        player.withdraw(int(total_cost))
        
        # Log the transaction
        if self.tlog:
            self.tlog.log_stock_buy(player_id, stock_name, num_shares, stock.price, total_cost)
        
        return True, f"Bought {num_shares} shares of {stock_name} for ${total_cost:.2f}."

    def sell_stock(self, player_id, stock_name, num_shares, account_manager):
        """Sell shares of a stock. Returns (success, message)."""
        with self.data_lock:
            if stock_name not in self.stocks:
                return False, f"Stock '{stock_name}' not found."
            
            stock = self.stocks[stock_name]
            
            # Check if player owns shares
            if player_id not in stock.shares_owned or stock.shares_owned[player_id] < num_shares:
                owned = stock.shares_owned.get(player_id, 0)
                return False, f"You own {owned} shares, cannot sell {num_shares}."
            
            # Calculate sale proceeds
            total_proceeds = num_shares * stock.price
            
            # Calculate average purchase price for this sale (proportional)
            if player_id in stock.purchase_prices:
                total_shares = stock.shares_owned[player_id]
                avg_purchase_price = stock.purchase_prices[player_id] / total_shares
                cost_of_sold_shares = num_shares * avg_purchase_price
                stock.purchase_prices[player_id] -= cost_of_sold_shares
            
            # Update shares owned
            stock.shares_owned[player_id] -= num_shares
            if stock.shares_owned[player_id] == 0:
                del stock.shares_owned[player_id]
                # Clean up purchase price tracking if no shares left
                if player_id in stock.purchase_prices:
                    del stock.purchase_prices[player_id]
            
            # Get player account while holding lock
            player = account_manager.query(player_id)
            if player == 'Account does not exist.':
                return False, "Player account not found."
        
        # Deposit to player account OUTSIDE the data_lock to avoid deadlock
        # player.deposit handles its own locking, so we don't need to acquire write_lock here
        player.deposit(int(total_proceeds))
        
        # Log the transaction
        if self.tlog:
            self.tlog.log_stock_sell(player_id, stock_name, num_shares, stock.price, total_proceeds)
        
        return True, f"Sold {num_shares} shares of {stock_name} for ${total_proceeds:.2f}."

    def get_player_portfolio(self, player_id):
        """Get portfolio for a player. Returns list of {stock_name, shares, price, value, avg_purchase_price}."""
        with self.data_lock:
            portfolio = []
            for stock_name, stock in self.stocks.items():
                if player_id in stock.shares_owned:
                    shares = stock.shares_owned[player_id]
                    value = shares * stock.price
                    
                    # Calculate average purchase price
                    avg_price = None
                    if player_id in stock.purchase_prices and shares > 0:
                        avg_price = round(stock.purchase_prices[player_id] / shares, 2)
                    
                    portfolio.append({
                        'name': stock_name,
                        'shares': shares,
                        'price': round(stock.price, 2),
                        'value': round(value, 2),
                        'sector': stock.sector,
                        'dividend': stock.dividend,
                        'avg_purchase_price': avg_price
                    })
            return portfolio

    def distribute_dividends(self, player_id, account_manager):
        """Distribute dividend payments for stocks owned by player."""
        total_dividend = 0
        dividends_received = []
        
        with self.data_lock:
            for stock_name, stock in self.stocks.items():
                if player_id in stock.shares_owned:
                    shares = stock.shares_owned[player_id]
                    dividend_amount = int(shares * stock.dividend)
                    if dividend_amount > 0:
                        total_dividend += dividend_amount
                        dividends_received.append({
                            'stock': stock_name,
                            'shares': shares,
                            'per_share': stock.dividend,
                            'amount': dividend_amount
                        })
            
        # Deposit dividends to account
        if total_dividend > 0:
            player = account_manager.query(player_id)
            if player != 'Account does not exist.':
                # player.deposit handles its own locking
                player.deposit(total_dividend)
                
                # Log the dividend payment
                if self.tlog:
                    self.tlog.log_dividend_payment(player_id, total_dividend, dividends_received)
        
        return total_dividend, dividends_received

    def process_turn(self, current_turn, account_manager):
        """Process stock market updates for a turn."""
        # Generate news event
        event = self.generate_news_event(current_turn)
        if event:
            self.active_news_events.append(event)
        
        # Apply news events
        self.apply_news_events()
        
        # Update stock prices
        self.update_stock_prices()
        
        # Distribute dividends to all players
        self.dividend_paid_this_turn = {}
        if hasattr(account_manager, 'accounts_storage'):
            for player_id in account_manager.accounts_storage.keys():
                total, dividends = self.distribute_dividends(player_id, account_manager)
                if total > 0:
                    self.dividend_paid_this_turn[player_id] = {
                        'total': total,
                        'dividends': dividends
                    }

    def get_all_stocks(self):
        """Get all stocks as dictionary."""
        with self.data_lock:
            return {name: stock.to_dict() for name, stock in self.stocks.items()}

    def get_active_news(self):
        """Get active news events."""
        with self.data_lock:
            return [event.to_dict() for event in self.active_news_events]

    def cleanup(self):
        """Cleanup resources."""
        return ["Stock manager cleaned up."]
