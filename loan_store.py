import time
import uuid
from datetime import datetime, timedelta
from threading import Timer, Lock
from enum import Enum


class LoanStatus(Enum):
    """Status of a loan."""
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    DEFAULTED = "defaulted"
    RESOLVED = "resolved"  # Default was forgiven/settled


class Loan:
    """
    Represents a loan given to a player.
    Stores the interest rate at time of creation and tracks payments.
    """
    def __init__(self, loan_id, borrower_id, principal, interest_rate, 
                 payment_interval, created_at=None, status=LoanStatus.ACTIVE,
                 amount_paid=0, next_payment_due=None):
        self.loan_id = loan_id
        self.borrower_id = borrower_id
        self.principal = principal  # Original loan amount
        self.interest_rate = interest_rate  # Interest rate when loan was created
        self.payment_interval = payment_interval  # In seconds (e.g., 300 for 5 minutes)
        self.created_at = created_at or time.time()
        self.status = status
        self.amount_paid = amount_paid
        self.next_payment_due = next_payment_due or (self.created_at + payment_interval)
        
    @property
    def total_owed(self):
        """Calculate total amount owed including interest."""
        return int(self.principal * (1 + self.interest_rate))
    
    @property
    def remaining_balance(self):
        """Calculate remaining balance after payments."""
        return self.total_owed - self.amount_paid
    
    @property
    def minimum_payment(self):
        """Calculate minimum payment required."""
        # Minimum payment is 10% of total owed or remaining balance, whichever is smaller
        min_pct = int(self.total_owed * 0.1)
        return min(min_pct, self.remaining_balance)
    
    @property
    def is_overdue(self):
        """Check if payment is overdue."""
        return self.status == LoanStatus.ACTIVE and time.time() > self.next_payment_due
    
    def make_payment(self, amount):
        """
        Make a payment towards the loan.
        Returns True if loan is paid off, False otherwise.
        """
        if self.status != LoanStatus.ACTIVE:
            return False, "Loan is not active"
        
        if amount <= 0:
            return False, "Payment amount must be positive"
        
        if amount > self.remaining_balance:
            amount = self.remaining_balance
        
        self.amount_paid += amount
        
        # Check if loan is paid off
        if self.remaining_balance <= 0:
            self.status = LoanStatus.PAID_OFF
            return True, f"Loan paid off! Total paid: ${self.amount_paid}"
        
        # Update next payment due date
        self.next_payment_due = time.time() + self.payment_interval
        
        return False, f"Payment of ${amount} applied. Remaining balance: ${self.remaining_balance}"
    
    def default_loan(self):
        """Mark the loan as defaulted."""
        self.status = LoanStatus.DEFAULTED
    
    def to_dict(self):
        """Convert loan to dictionary for storage."""
        return {
            'loan_id': self.loan_id,
            'borrower_id': self.borrower_id,
            'principal': self.principal,
            'interest_rate': self.interest_rate,
            'payment_interval': self.payment_interval,
            'created_at': self.created_at,
            'status': self.status.value,
            'amount_paid': self.amount_paid,
            'next_payment_due': self.next_payment_due
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create loan from dictionary."""
        return cls(
            loan_id=data['loan_id'],
            borrower_id=data['borrower_id'],
            principal=data['principal'],
            interest_rate=data['interest_rate'],
            payment_interval=data['payment_interval'],
            created_at=data['created_at'],
            status=LoanStatus(data['status']),
            amount_paid=data['amount_paid'],
            next_payment_due=data['next_payment_due']
        )


class LoanManager:
    """
    Manages all loans in the game.
    Handles loan qualification, creation, payments, and notifications.
    """
    
    def __init__(self, tlog_connection, account_manager):
        self.loans = {}  # loan_id -> Loan
        self.tlog_connection = tlog_connection
        self.account_manager = account_manager
        self.write_lock = Lock()
        self.payment_timers = {}  # loan_id -> Timer
        self.loan_interest_rate = 0.15  # Default 15% interest rate for new loans
        self.min_credit_score = 500  # Minimum "cash + property value" for loan eligibility
        self.max_loan_amount = 1000  # Maximum loan amount
        self.default_payment_interval = 300  # Default 5 minutes in seconds
        self.load_saved()
    
    def load_saved(self):
        """Load all loans from the database."""
        loan_data = self.tlog_connection.get_all_loans()
        self.write_lock.acquire()
        self.loans = {}
        for loan_row in loan_data:
            loan = Loan(
                loan_id=loan_row[0],
                borrower_id=loan_row[1],
                principal=loan_row[2],
                interest_rate=loan_row[3],
                payment_interval=loan_row[4],
                created_at=loan_row[5],
                status=LoanStatus(loan_row[6]),
                amount_paid=loan_row[7],
                next_payment_due=loan_row[8]
            )
            self.loans[loan.loan_id] = loan
        self.write_lock.release()
        return f'Loaded {len(self.loans)} loan{"s" if len(self.loans) != 1 else ""} from database'
    
    def calculate_credit_score(self, account):
        """
        Calculate a simple credit score for an account.
        Based on: cash balance + property values.
        """
        if account == 'Account does not exist.':
            return 0
        
        # Cash balance
        score = account.cash
        
        # Add property values (unmortgaged properties count more)
        for prop in account.properties:
            if hasattr(prop, 'costs') and 'property' in prop.costs:
                if hasattr(prop, 'mortgaged') and not prop.mortgaged:
                    score += prop.costs['property']
                else:
                    score += prop.costs['property'] // 2
        
        return score
    
    def check_loan_eligibility(self, borrower_id, requested_amount):
        """
        Check if a player qualifies for a loan.
        Returns (eligible: bool, reason: str, max_amount: int)
        """
        account = self.account_manager.query(borrower_id)
        
        if account == 'Account does not exist.':
            return False, "Account does not exist", 0
        
        # Calculate credit score
        credit_score = self.calculate_credit_score(account)
        
        if credit_score < self.min_credit_score:
            return False, f"Insufficient credit. Need at least ${self.min_credit_score} in assets, have ${credit_score}", 0
        
        # Check existing loans
        active_loans = self.get_loans_by_borrower(borrower_id, active_only=True)
        total_debt = sum(loan.remaining_balance for loan in active_loans)
        
        # Maximum loan is based on credit score minus existing debt
        max_loan = min(self.max_loan_amount, int(credit_score * 0.5) - total_debt)
        
        if max_loan <= 0:
            return False, f"Too much existing debt (${total_debt}). Pay off loans first.", 0
        
        if requested_amount > max_loan:
            return False, f"Requested ${requested_amount} exceeds maximum ${max_loan}", max_loan
        
        return True, "Qualified for loan", max_loan
    
    def create_loan(self, borrower_id, amount, payment_interval=None, approved_by_banker=False):
        """
        Create a new loan for a player.
        If approved_by_banker is True, bypasses credit checks.
        Returns (success: bool, loan_id or error_message: str)
        """
        # Check eligibility unless banker approved
        if not approved_by_banker:
            eligible, reason, max_amount = self.check_loan_eligibility(borrower_id, amount)
            if not eligible:
                return False, reason
        
        account = self.account_manager.query(borrower_id)
        if account == 'Account does not exist.':
            return False, "Account does not exist"
        
        # Create loan
        loan_id = str(uuid.uuid4())[:8]
        interval = payment_interval if payment_interval else self.default_payment_interval
        
        loan = Loan(
            loan_id=loan_id,
            borrower_id=borrower_id,
            principal=amount,
            interest_rate=self.loan_interest_rate,
            payment_interval=interval,
            created_at=time.time(),
            status=LoanStatus.ACTIVE
        )
        
        self.write_lock.acquire()
        self.loans[loan_id] = loan
        self.write_lock.release()
        
        # Save to database
        self.tlog_connection.create_loan(
            loan_id, borrower_id, amount, self.loan_interest_rate,
            interval, loan.created_at, loan.next_payment_due
        )
        
        # Deposit loan amount into account
        account.deposit(amount, log=True)
        
        return True, loan_id
    
    def make_payment(self, loan_id, amount):
        """
        Make a payment on a loan.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        
        # Check if borrower has enough cash
        account = self.account_manager.query(loan.borrower_id)
        if account == 'Account does not exist.':
            return False, "Borrower account not found"
        
        if account.cash < amount:
            return False, f"Insufficient funds. Have ${account.cash}, need ${amount}"
        
        # Withdraw from account
        account.withdraw(amount, log=True)
        
        # Apply payment to loan
        paid_off, message = loan.make_payment(amount)
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
        )
        
        # Log payment
        self.tlog_connection.log_loan_payment(loan_id, loan.borrower_id, amount, paid_off)
        
        return True, message
    
    def default_loan(self, loan_id):
        """
        Mark a loan as defaulted.
        Attempts to liquidate assets to pay off the loan first.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        account = self.account_manager.query(loan.borrower_id)
        
        if account == 'Account does not exist.':
            return False, "Borrower account not found"
        
        # Attempt asset liquidation
        liquidation_msg = self._attempt_liquidation(loan, account)
        
        # Check if loan was paid off through liquidation
        if loan.remaining_balance <= 0:
            loan.status = LoanStatus.PAID_OFF
            self.tlog_connection.update_loan(
                loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
            )
            self.tlog_connection.log_loan_payment(
                loan_id, loan.borrower_id, loan.amount_paid, True
            )
            return True, f"Loan paid off through asset liquidation. {liquidation_msg}"
        
        # If still unpaid, mark as defaulted
        loan.default_loan()
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
        )
        
        # Log default
        self.tlog_connection.log_loan_default(loan_id, loan.borrower_id)
        
        return True, f"Loan marked as defaulted. {liquidation_msg}"
    
    def _attempt_liquidation(self, loan, account):
        """
        Attempt to liquidate player assets to pay off loan.
        Returns a message describing what was liquidated.
        """
        liquidated_items = []
        total_liquidated = 0
        
        # First, use available cash
        if account.cash > 0:
            cash_payment = min(account.cash, loan.remaining_balance)
            account.withdraw(cash_payment, log=True)
            loan.make_payment(cash_payment)
            total_liquidated += cash_payment
            liquidated_items.append(f"${cash_payment} cash")
            
            self.tlog_connection.update_loan(
                loan.loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
            )
        
        # If still unpaid, sell properties
        if loan.remaining_balance > 0 and len(account.properties) > 0:
            properties_to_sell = list(account.properties)
            
            for prop in properties_to_sell:
                if loan.remaining_balance <= 0:
                    break
                
                # Calculate property value (50% of purchase price, standard bank buyback)
                prop_value = prop.costs.get('property', 0) // 2
                
                # If mortgaged, value is reduced
                if hasattr(prop, 'mortgaged') and prop.mortgaged:
                    prop_value = prop_value // 2
                
                # Sell property back to bank
                account.deposit(prop_value, log=False)
                account.remove_property(prop)
                
                # Apply to loan
                payment = min(prop_value, loan.remaining_balance)
                account.withdraw(payment, log=False)
                loan.make_payment(payment)
                
                total_liquidated += payment
                liquidated_items.append(f"{prop.name} (${payment})")
                
                self.tlog_connection.update_loan(
                    loan.loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
                )
        
        if total_liquidated > 0:
            items_str = ", ".join(liquidated_items)
            return f"Liquidated: {items_str}. Total: ${total_liquidated}. Remaining debt: ${loan.remaining_balance}"
        else:
            return f"No assets to liquidate. Outstanding debt: ${loan.remaining_balance}"
    
    def has_defaulted_loans(self, borrower_id):
        """Check if a borrower has any defaulted loans."""
        return any(
            loan.status == LoanStatus.DEFAULTED 
            for loan in self.loans.values() 
            if loan.borrower_id == borrower_id
        )
    
    def forgive_default(self, loan_id):
        """
        Forgive a default on a loan, allowing the borrower to apply for new loans.
        Should be called after a defaulted loan is fully paid/settled.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        if loan.status != LoanStatus.DEFAULTED:
            return False, "Loan is not in default status"
        
        loan.status = LoanStatus.RESOLVED
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due
        )
        
        return True, f"Default on loan {loan_id} has been forgiven. Account can now borrow again."
    
    def erase_loan(self, loan_id):
        """
        Erase/forgive a loan completely (banker only action).
        Removes the loan from the system.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        borrower_id = loan.borrower_id
        erased_amount = loan.remaining_balance
        
        # Remove the loan
        del self.loans[loan_id]
        
        # Log the erasure
        self.tlog_connection.log_loan_erased(loan_id, borrower_id, erased_amount)
        
        return True, f"Loan {loan_id} erased. Forgave ${erased_amount} debt for {borrower_id}"
    
    def get_loan(self, loan_id):
        """Get a specific loan by ID."""
        return self.loans.get(loan_id)
    
    def get_loans_by_borrower(self, borrower_id, active_only=False):
        """Get all loans for a specific borrower."""
        loans = [loan for loan in self.loans.values() if loan.borrower_id == borrower_id]
        if active_only:
            loans = [loan for loan in loans if loan.status == LoanStatus.ACTIVE]
        return loans
    
    def get_all_loans(self, active_only=False):
        """Get all loans in the system."""
        if active_only:
            return [loan for loan in self.loans.values() if loan.status == LoanStatus.ACTIVE]
        return list(self.loans.values())
    
    def get_overdue_loans(self):
        """Get all loans that are overdue for payment."""
        return [loan for loan in self.loans.values() if loan.is_overdue]
    
    def send_payment_notification(self, loan_id):
        """
        Send a payment notification for a loan.
        This adds a notification to the transaction log.
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        self.tlog_connection.log_payment_notification(
            loan_id, loan.borrower_id, loan.minimum_payment, loan.remaining_balance
        )
        
        return True, f"Notification sent for loan {loan_id}"
    
    def schedule_payment_notification(self, loan_id, delay_seconds=None):
        """
        Schedule a payment notification to be sent after a delay.
        If delay_seconds is None, uses the loan's payment interval.
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        delay = delay_seconds if delay_seconds is not None else loan.payment_interval
        
        # Cancel existing timer if any
        if loan_id in self.payment_timers:
            self.payment_timers[loan_id].cancel()
        
        # Create new timer
        timer = Timer(delay, self.send_payment_notification, args=(loan_id,))
        timer.daemon = True
        timer.start()
        
        self.payment_timers[loan_id] = timer
        
        return True, f"Payment notification scheduled for {delay} seconds"
    
    def cancel_payment_notification(self, loan_id):
        """Cancel a scheduled payment notification."""
        if loan_id in self.payment_timers:
            self.payment_timers[loan_id].cancel()
            del self.payment_timers[loan_id]
            return True, f"Cancelled notification for loan {loan_id}"
        return False, "No scheduled notification found"
    
    def cleanup(self):
        """Clean up resources."""
        # Cancel all timers
        for timer in self.payment_timers.values():
            timer.cancel()
        self.payment_timers.clear()
        yield 'Cancelled all payment notification timers'
