# from threading import Event, Semaphore, Lock, Thread
from multiprocessing import Process, Queue
# from queue import Queue
import sqlite3
from datetime import datetime

SIG_STOP = 'done'


class TransactionLog:

    def __init__(self, filename, exec_queue=Queue(200), recv_queue=Queue(100)):
        self.filename = filename
        self.exec_queue = exec_queue
        self.receive_data = recv_queue
        self.listener_thread = Process(target=self._queue_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        # listener_thread.join()

    def _queue_listener(self):
        db = sqlite3.connect(self.filename)
        # Create TLog table and Accounts table if they doesn't exist
        db.execute(
            """CREATE TABLE IF NOT EXISTS TLog(
                time TEXT,
                type TEXT,
                account TEXT,
                info TEXT)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS Accounts(
                id TEXT PRIMARY KEY,
                name TEXT,
                salt BLOB,
                password_hash BLOB,
                cash INTEGER,
                properties TEXT,
                is_banker BOOL)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS Auctions(
                auction_id TEXT PRIMARY KEY,
                property_name TEXT,
                seller_id TEXT,
                starting_bid INTEGER,
                current_bid INTEGER,
                current_bidder TEXT,
                created_at REAL,
                active BOOL)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS AuctionBids(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id TEXT,
                bidder_id TEXT,
                amount INTEGER,
                timestamp REAL,
                FOREIGN KEY (auction_id) REFERENCES Auctions(auction_id))
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS Loans(
                loan_id TEXT PRIMARY KEY,
                borrower_id TEXT,
                principal INTEGER,
                interest_rate REAL,
                payment_interval_turns INTEGER,
                created_at_turn INTEGER,
                status TEXT,
                amount_paid INTEGER,
                next_payment_due_turn INTEGER,
                interest_compounds BOOLEAN DEFAULT 1,
                compounding_interval_turns INTEGER DEFAULT 3,
                late_fees INTEGER DEFAULT 0,
                loan_term_periods INTEGER DEFAULT 12)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS GameState(
                key TEXT PRIMARY KEY,
                value INTEGER)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS PaymentRecords(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id TEXT,
                account_id TEXT,
                amount_paid REAL,
                amount_owed REAL,
                payment_date_turn INTEGER,
                due_date_turn INTEGER,
                on_time BOOLEAN,
                late_by_turns INTEGER,
                loan_amount REAL,
                interest_rate REAL,
                FOREIGN KEY (loan_id) REFERENCES Loans(loan_id),
                FOREIGN KEY (account_id) REFERENCES Accounts(id))
            """
        )
        while True:
            try:
                next_command = self.exec_queue.get()
            except KeyboardInterrupt:
                pass
            if next_command == SIG_STOP:
                break
            update, com, args = next_command
            if update:
                if args is not None:
                    db.execute(com, args)
                else:
                    db.execute(com)
                db.commit()
            else:
                if args is not None:
                    self.receive_data.put(db.execute(com, args).fetchall())
                else:
                    self.receive_data.put(db.execute(com).fetchall())
        db.commit()
        db.close()


    def _send_transaction_to_listener(self, trans_type, account, info):
        timestamp = datetime.now()
        self.exec_queue.put((
            True,
            "INSERT INTO TLog VALUES (?, ?, ?, ?)",
            (
                timestamp,
                trans_type,
                account,
                info
            )
        ))

    def log_account_created(self, ident, cash):
        trans_type = 'Create'
        info = f'Started with ${cash}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_deleted(self, ident):
        trans_type = 'Delete'
        self._send_transaction_to_listener(trans_type, ident, None)

    def log_account_deposit(self, ident, amount):
        trans_type = 'Deposit'
        info = f'${amount}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_withdraw(self, ident, amount):
        trans_type = 'Withdraw'
        info = f'${amount}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_transfer(self, payer, payee, info):
        trans_type = 'Transfer'
        self._send_transaction_to_listener(trans_type, payer, info)
        self._send_transaction_to_listener(trans_type, payee, info)

    def log_server_started(self):
        trans_type = 'Server Start'
        id_num = None
        info = 'Server has started'
        self._send_transaction_to_listener(trans_type, id_num, info)

    def log_accounts_reloaded(self):
        trans_type = 'Reload'
        id_num = None
        info = 'Reloaded all accounts'
        self._send_transaction_to_listener(trans_type, id_num, info)

    def log_get_by_id(self, ident):
        self.exec_queue.put((
            False,
            "SELECT * FROM TLog WHERE account=? ORDER BY time",
            (ident,)
        ))
        return self.receive_data.get()

    def purge_logs(self):
        self.exec_queue.put((
            True,
            "DELETE FROM TLog",
            None
        ))

    def create_account(self, ident, name, pw_salt, pw_hash, cash, is_banker):
        self.exec_queue.put((
            True,
            "INSERT INTO Accounts VALUES (?, ?, ?, ?, ?, '{}', ?)",
            (ident, name, pw_salt, pw_hash, cash, is_banker)
        ))

    def update_account(self, ident, cash):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET cash=? WHERE id=?",
            (cash, ident)
        ))

    def update_properties(self, ident, properties):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET properties=? WHERE id=?",
            (properties, ident)
        ))

    def delete_account(self, ident):
        self.exec_queue.put((
            True,
            "DELETE FROM Accounts WHERE id=?",
            (ident,)
        ))

    def get_all_accounts(self):
        self.exec_queue.put((
            False,
            "SELECT * FROM Accounts",
            None
        ))
        return self.receive_data.get()

    def set_account_password(self, ident, salt, hashed_pass):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET salt=? password_hash=? WHERE id=?",
            (salt, hashed_pass, ident)
        ))

    def retrieve_hashed_password(self, ident):
        self.exec_queue.put((
            False,
            "SELECT salt, password_hash FROM Accounts WHERE id=?",
            (ident,)
        ))
        return self.receive_data.get()

    def nuke_tables(self):
        self.exec_queue.put((
            True,
            "DELETE FROM Accounts",
            None
        ))
        trans_type = 'Nuke Data'
        id_num = None
        info = 'Accounts and TLog were purged'
        self._send_transaction_to_listener(trans_type, id_num, info)
        self.purge_logs()

    def stop_db(self):
        trans_type = 'Server Stop'
        id_num = None
        info = 'Server has stopped'
        self._send_transaction_to_listener(trans_type, id_num, info)
        yield 'Logged server stop'
        self.exec_queue.put(SIG_STOP)
        yield 'Signaled db listener close'
        self.listener_thread.join()
        yield 'Stopped TLog'

    # Auction methods
    def create_auction(self, auction_id, property_name, seller_id, starting_bid, created_at):
        self.exec_queue.put((
            True,
            "INSERT INTO Auctions VALUES (?, ?, ?, ?, ?, NULL, ?, 1)",
            (auction_id, property_name, seller_id, starting_bid, starting_bid, created_at)
        ))
        trans_type = 'Auction Created'
        info = f'Property: {property_name}, Starting bid: ${starting_bid}'
        self._send_transaction_to_listener(trans_type, seller_id, info)

    def get_all_auctions(self):
        self.exec_queue.put((
            False,
            "SELECT * FROM Auctions",
            None
        ))
        return self.receive_data.get()

    def get_auction_bids(self, auction_id):
        self.exec_queue.put((
            False,
            "SELECT bidder_id, amount, timestamp FROM AuctionBids WHERE auction_id=? ORDER BY timestamp",
            (auction_id,)
        ))
        return self.receive_data.get()

    def place_bid(self, auction_id, bidder_id, amount, timestamp):
        # Insert bid into history
        self.exec_queue.put((
            True,
            "INSERT INTO AuctionBids (auction_id, bidder_id, amount, timestamp) VALUES (?, ?, ?, ?)",
            (auction_id, bidder_id, amount, timestamp)
        ))
        # Update current bid on auction
        self.exec_queue.put((
            True,
            "UPDATE Auctions SET current_bid=?, current_bidder=? WHERE auction_id=?",
            (amount, bidder_id, auction_id)
        ))
        trans_type = 'Bid Placed'
        info = f'Auction: {auction_id}, Amount: ${amount}'
        self._send_transaction_to_listener(trans_type, bidder_id, info)

    def complete_auction(self, auction_id):
        self.exec_queue.put((
            True,
            "UPDATE Auctions SET active=0 WHERE auction_id=?",
            (auction_id,)
        ))
        trans_type = 'Auction Completed'
        info = f'Auction: {auction_id}'
        self._send_transaction_to_listener(trans_type, None, info)

    def cancel_auction(self, auction_id, seller_id):
        self.exec_queue.put((
            True,
            "UPDATE Auctions SET active=0 WHERE auction_id=?",
            (auction_id,)
        ))
        trans_type = 'Auction Cancelled'
        info = f'Auction: {auction_id}'
        self._send_transaction_to_listener(trans_type, seller_id, info)

    # Loan methods
    def create_loan(self, loan_id, borrower_id, principal, interest_rate, payment_interval_turns, created_at_turn, next_payment_due_turn, interest_compounds=True, compounding_interval_turns=3, late_fees=0, loan_term_periods=3):
        self.exec_queue.put((
            True,
            "INSERT INTO Loans VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?, ?, ?, ?, ?)",
            (loan_id, borrower_id, principal, interest_rate, payment_interval_turns, created_at_turn, next_payment_due_turn, interest_compounds, compounding_interval_turns, late_fees, loan_term_periods)
        ))
        trans_type = 'Loan Created'
        info = f'Loan ID: {loan_id}, Amount: ${principal}, Interest: {int(interest_rate * 100)}%'
        self._send_transaction_to_listener(trans_type, borrower_id, info)

    def get_all_loans(self):
        self.exec_queue.put((
            False,
            "SELECT * FROM Loans",
            None
        ))
        return self.receive_data.get()

    def update_loan(self, loan_id, amount_paid, status, next_payment_due_turn):
        self.exec_queue.put((
            True,
            "UPDATE Loans SET amount_paid=?, status=?, next_payment_due_turn=? WHERE loan_id=?",
            (amount_paid, status, next_payment_due_turn, loan_id)
        ))

    def log_loan_payment(self, loan_id, borrower_id, amount, paid_off):
        trans_type = 'Loan Payment'
        status = ' - PAID OFF' if paid_off else ''
        info = f'Loan ID: {loan_id}, Payment: ${amount}{status}'
        self._send_transaction_to_listener(trans_type, borrower_id, info)

    def log_loan_default(self, loan_id, borrower_id):
        trans_type = 'Loan Default'
        info = f'Loan ID: {loan_id} - DEFAULTED'
        self._send_transaction_to_listener(trans_type, borrower_id, info)

    def log_payment_notification(self, loan_id, borrower_id, minimum_payment, remaining_balance):
        trans_type = 'Payment Due'
        info = f'Loan ID: {loan_id}, Minimum: ${minimum_payment}, Balance: ${remaining_balance}'
        self._send_transaction_to_listener(trans_type, borrower_id, info)

    # Game state methods
    def get_game_state(self, key):
        """Retrieve a game state value from the database."""
        self.exec_queue.put((
            False,
            "SELECT value FROM GameState WHERE key=?",
            (key,)
        ))
        result = self.receive_data.get()
        if result:
            return result[0][0]
        return None

    def set_game_state(self, key, value):
        """Save a game state value to the database."""
        self.exec_queue.put((
            True,
            "INSERT OR REPLACE INTO GameState (key, value) VALUES (?, ?)",
            (key, value)
        ))

    # Payment Record methods
    def save_payment_record(self, loan_id, account_id, amount_paid, amount_owed, 
                           payment_date_turn, due_date_turn, on_time, late_by_turns, 
                           loan_amount, interest_rate):
        """Save a payment record to the database."""
        self.exec_queue.put((
            True,
            "INSERT INTO PaymentRecords (loan_id, account_id, amount_paid, amount_owed, payment_date_turn, due_date_turn, on_time, late_by_turns, loan_amount, interest_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (loan_id, account_id, amount_paid, amount_owed, payment_date_turn, due_date_turn, on_time, late_by_turns, loan_amount, interest_rate)
        ))

    def get_payment_records_for_account(self, account_id):
        """Retrieve all payment records for an account."""
        self.exec_queue.put((
            False,
            "SELECT loan_id, amount_paid, amount_owed, payment_date_turn, due_date_turn, on_time, late_by_turns, loan_amount, interest_rate FROM PaymentRecords WHERE account_id=? ORDER BY payment_date_turn",
            (account_id,)
        ))
        return self.receive_data.get()

    def delete_payment_records_for_account(self, account_id):
        """Delete all payment records for an account (used when rebuilding)."""
        self.exec_queue.put((
            True,
            "DELETE FROM PaymentRecords WHERE account_id=?",
            (account_id,)
        ))


        trans_type = 'Loan Erased'
        info = f'Loan ID: {loan_id} - ERASED, Forgave: ${amount}'
        self._send_transaction_to_listener(trans_type, borrower_id, info)
