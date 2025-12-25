import time
from threading import Lock


class Auction:
    """
    Represents an auction for a Monopoly property.
    """
    def __init__(self, auction_id: str, property_name: str, seller_id: str, starting_bid: int, current_bid=None, current_bidder=None, created_at=None):
        self.auction_id = auction_id
        self.property_name = property_name
        self.seller_id = seller_id
        self.starting_bid = starting_bid
        self.current_bid = current_bid if current_bid is not None else starting_bid
        self.current_bidder = current_bidder
        self.created_at = created_at if created_at is not None else time.time()
        self.bid_history = []  # List of (bidder_id, amount, timestamp) tuples
        self.active = True

    def place_bid(self, bidder_id: str, amount: int):
        """
        Place a bid on the auction.
        Returns (success, message) tuple.
        """
        if not self.active:
            return False, "Auction is no longer active."
        
        if bidder_id == self.seller_id:
            return False, "You cannot bid on your own auction."
        
        if amount <= self.current_bid:
            return False, f"Bid must be higher than current bid of ${self.current_bid}."
        
        # Record the bid
        self.bid_history.append((bidder_id, amount, time.time()))
        self.current_bid = amount
        self.current_bidder = bidder_id
        
        return True, f"Bid placed successfully for ${amount}."

    def complete_auction(self):
        """
        Mark the auction as complete.
        Returns the winning bidder and amount, or (None, None) if no bids.
        """
        self.active = False
        if self.current_bidder:
            return self.current_bidder, self.current_bid
        return None, None

    def cancel_auction(self):
        """
        Cancel the auction (seller-initiated).
        """
        self.active = False

    def get_time_elapsed(self):
        """
        Get time elapsed since auction creation in human-readable format.
        """
        elapsed = time.time() - self.created_at
        if elapsed < 60:
            return f"{int(elapsed)} seconds ago"
        elif elapsed < 3600:
            return f"{int(elapsed / 60)} minutes ago"
        elif elapsed < 86400:
            return f"{int(elapsed / 3600)} hours ago"
        else:
            return f"{int(elapsed / 86400)} days ago"


class AuctionManager:
    """
    Manages all auctions in the Monopoly banking system via TLog.
    """
    def __init__(self, tlog_connection):
        self.tlog = tlog_connection
        self.auctions = {}  # auction_id -> Auction
        self.write_lock = Lock()
        self.load_auctions()

    def load_auctions(self):
        """
        Load auctions from the database.
        """
        auction_rows = self.tlog.get_all_auctions()
        
        for row in auction_rows:
            auction_id, property_name, seller_id, starting_bid, current_bid, current_bidder, created_at, active = row
            
            auction = Auction(
                auction_id=auction_id,
                property_name=property_name,
                seller_id=seller_id,
                starting_bid=starting_bid,
                current_bid=current_bid,
                current_bidder=current_bidder,
                created_at=created_at
            )
            auction.active = bool(active)
            
            # Load bid history
            bid_rows = self.tlog.get_auction_bids(auction_id)
            auction.bid_history = [(bidder, amount, ts) for bidder, amount, ts in bid_rows]
            
            self.auctions[auction_id] = auction

    def create_auction(self, property_name: str, seller_id: str, starting_bid: int):
        """
        Create a new auction for a property.
        Returns (success, auction_id or error_message).
        """
        # Generate auction ID
        auction_id = f"{property_name}_{int(time.time())}"
        
        # Check if property already has an active auction
        for auction in self.auctions.values():
            if auction.property_name == property_name and auction.active:
                return False, "This property already has an active auction."
        
        # Create the auction
        created_at = time.time()
        auction = Auction(auction_id, property_name, seller_id, starting_bid, created_at=created_at)
        
        with self.write_lock:
            self.auctions[auction_id] = auction
            self.tlog.create_auction(auction_id, property_name, seller_id, starting_bid, created_at)
        
        return True, auction_id

    def get_auction(self, auction_id: str):
        """
        Get an auction by ID.
        """
        return self.auctions.get(auction_id)

    def get_active_auctions(self):
        """
        Get all active auctions, sorted by creation time (newest first).
        """
        active = [a for a in self.auctions.values() if a.active]
        return sorted(active, key=lambda a: a.created_at, reverse=True)

    def get_user_auctions(self, user_id: str):
        """
        Get all auctions created by a specific user.
        """
        return [a for a in self.auctions.values() if a.seller_id == user_id]

    def place_bid(self, auction_id: str, bidder_id: str, amount: int):
        """
        Place a bid on an auction.
        Returns (success, message) tuple.
        """
        auction = self.get_auction(auction_id)
        if not auction:
            return False, "Auction not found."
        
        success, message = auction.place_bid(bidder_id, amount)
        if success:
            # Save to database
            timestamp = time.time()
            self.tlog.place_bid(auction_id, bidder_id, amount, timestamp)
        
        return success, message

    def complete_auction(self, auction_id: str):
        """
        Complete an auction and return the winner.
        Returns (winner_id, winning_bid) or (None, None).
        """
        auction = self.get_auction(auction_id)
        if not auction:
            return None, None
        
        winner, amount = auction.complete_auction()
        self.tlog.complete_auction(auction_id)
        
        return winner, amount

    def cancel_auction(self, auction_id: str, user_id: str):
        """
        Cancel an auction (only by seller or banker).
        Returns (success, message).
        """
        auction = self.get_auction(auction_id)
        if not auction:
            return False, "Auction not found."
        
        if auction.seller_id != user_id:
            return False, "Only the seller can cancel this auction."
        
        if auction.current_bidder:
            return False, "Cannot cancel auction with existing bids. Complete the auction instead."
        
        auction.cancel_auction()
        self.tlog.cancel_auction(auction_id, user_id)
        
        return True, "Auction cancelled successfully."

    def cleanup(self):
        """
        TLog handles cleanup, nothing needed here.
        """
        return ["Auction data saved via TLog."]
