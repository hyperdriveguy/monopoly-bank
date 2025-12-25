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
    # Class variable to track current turn for all loan instances
    _current_turn = 0
    
    def __init__(self, loan_id, borrower_id, principal, interest_rate, 
                 payment_interval_turns, created_at_turn=0, status=LoanStatus.ACTIVE,
                 amount_paid=0, next_payment_due_turn=None, interest_compounds=True,
                 compounding_interval_turns=None, late_fees=0, loan_term_periods=3):
        self.loan_id = loan_id
        self.borrower_id = borrower_id
        self.principal = principal  # Original loan amount
        self.interest_rate = interest_rate  # Interest rate when loan was created (locked in)
        self.payment_interval_turns = payment_interval_turns  # In turns (e.g., 3 for every 3 turns)
        self.created_at_turn = created_at_turn  # Turn when loan was created
        self.status = status
        self.amount_paid = amount_paid
        self.next_payment_due_turn = next_payment_due_turn if next_payment_due_turn is not None else (self.created_at_turn + payment_interval_turns)
        self.interest_compounds = interest_compounds  # Whether interest compounds (default True)
        # Default compounding interval is the payment interval
        self.compounding_interval_turns = compounding_interval_turns if compounding_interval_turns is not None else payment_interval_turns
        self.late_fees = late_fees  # Accumulated late fees
        self.late_fee_per_turn = 25  # $25 per turn for being overdue
        self.loan_term_periods = loan_term_periods  # Number of payment periods to pay off loan (default 12)
        
    @property
    def total_owed(self):
        """Calculate total amount owed including interest."""
        if self.interest_compounds:
            # Compound interest: principal * (1 + rate) ^ (periods elapsed / compounding interval)
            # Default compounding interval is set when loan was created
            # Use Loan._current_turn to track periods
            periods_elapsed = Loan._current_turn - self.created_at_turn
            if periods_elapsed < 0:
                periods_elapsed = 0  # Don't go negative if current turn is before creation
            # Number of compounding periods that have passed
            # This is set per loan when it's created (stored in the Loan object)
            compounding_periods = periods_elapsed / max(1, self.compounding_interval_turns)
            total = self.principal * ((1 + self.interest_rate) ** compounding_periods)
            return int(total)
        else:
            # Simple interest: principal * (1 + rate)
            return int(self.principal * (1 + self.interest_rate))
    
    @property
    def remaining_balance(self):
        """Calculate remaining balance after payments and late fees."""
        return self.total_owed + self.late_fees - self.amount_paid
    
    @property
    def minimum_payment(self):
        """Calculate minimum payment required."""
        # Minimum payment is 10% of total owed or remaining balance, whichever is smaller
        min_pct = int(self.total_owed * 0.1)
        return min(min_pct, self.remaining_balance)
    
    @property
    def typical_payment(self):
        """Calculate amortized payment using standard loan formula.
        M = P * r(1+r)^N / ((1+r)^N - 1)
        Where:
        - P = principal (locked in at creation)
        - r = periodic interest rate (interest_rate per compounding_interval)
        - N = total number of payment periods (loan_term_periods)
        
        This ensures consistent payments that will pay off the loan over its lifetime.
        Rounded up to nearest dollar to ensure full payoff.
        """
        if self.principal <= 0 or self.loan_term_periods <= 0:
            return 0
        
        # Get periodic interest rate
        # The interest_rate applies per compounding_interval_turns
        # We need the effective rate per payment_interval_turns
        periods_per_payment = self.payment_interval_turns / max(1, self.compounding_interval_turns)
        
        if self.interest_compounds and self.interest_rate > 0:
            # Effective periodic rate for payment interval
            # (1 + r_compound)^(periods_per_payment) - 1
            periodic_rate = (1 + self.interest_rate) ** periods_per_payment - 1
            
            # Amortized payment formula: M = P * r(1+r)^N / ((1+r)^N - 1)
            if periodic_rate > 0:
                numerator = self.principal * periodic_rate * ((1 + periodic_rate) ** self.loan_term_periods)
                denominator = ((1 + periodic_rate) ** self.loan_term_periods) - 1
                # Round up to nearest dollar to ensure full payoff without remainder
                import math
                return math.ceil(numerator / denominator)
            else:
                # No interest, divide evenly and round up
                import math
                return math.ceil(self.principal / self.loan_term_periods)
        else:
            # Simple interest: divide principal evenly over periods, round up
            import math
            return math.ceil(self.principal / self.loan_term_periods)
    
    @property
    def is_overdue(self):
        """Check if payment is overdue (AFTER the due turn, not on the due turn)."""
        return self.status == LoanStatus.ACTIVE and Loan._current_turn > self.next_payment_due_turn
    
    @property
    def is_due_this_turn(self):
        """Check if payment is due this turn (payment can still be made without penalty)."""
        return self.status == LoanStatus.ACTIVE and Loan._current_turn == self.next_payment_due_turn
    
    def make_payment(self, amount, current_turn):
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
        
        # Check if loan is paid off (before updating next payment due)
        if self.remaining_balance <= 0:
            self.status = LoanStatus.PAID_OFF
            return True, f"Loan paid off! Total paid: ${self.amount_paid}"
        
        # Update next payment due turn only if loan is still active
        self.next_payment_due_turn = current_turn + self.payment_interval_turns
        
        return False, f"Payment of ${amount} applied. Remaining balance: ${self.remaining_balance}"
    
    def accumulate_late_fees(self):
        """Add late fees if payment is overdue. Called each turn."""
        if self.is_overdue:
            self.late_fees += self.late_fee_per_turn
            return self.late_fee_per_turn
        return 0
    
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
            'payment_interval_turns': self.payment_interval_turns,
            'created_at_turn': self.created_at_turn,
            'status': self.status.value,
            'amount_paid': self.amount_paid,
            'next_payment_due_turn': self.next_payment_due_turn,
            'interest_compounds': self.interest_compounds,
            'compounding_interval_turns': self.compounding_interval_turns,
            'late_fees': self.late_fees
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create loan from dictionary."""
        return cls(
            loan_id=data['loan_id'],
            borrower_id=data['borrower_id'],
            principal=data['principal'],
            interest_rate=data['interest_rate'],
            payment_interval_turns=data['payment_interval_turns'],
            created_at_turn=data['created_at_turn'],
            status=LoanStatus(data['status']),
            amount_paid=data['amount_paid'],
            next_payment_due_turn=data['next_payment_due_turn'],
            interest_compounds=data.get('interest_compounds', True),
            compounding_interval_turns=data.get('compounding_interval_turns', None),
            late_fees=data.get('late_fees', 0)
        )


class LoanManager:
    """
    Manages all loans in the game.
    Handles loan qualification, creation, payments, and notifications.
    Uses turn-based payment intervals instead of time-based.
    """
    
    def __init__(self, tlog_connection, account_manager):
        self.loans = {}  # loan_id -> Loan
        self.tlog_connection = tlog_connection
        self.account_manager = account_manager
        self.write_lock = Lock()
        self.payment_timers = {}  # loan_id -> Timer (kept for compatibility but not used for payment intervals)
        self.loan_interest_rate = 0.15  # Default 15% interest rate for new loans
        self.min_credit_score = 500  # Minimum "cash + property value" for loan eligibility
        self.max_loan_amount = 1000  # Maximum loan amount
        self.default_payment_interval_turns = 3  # Default 3 turns between payments
        self.compounding_interval_turns = 3  # Default: compound interest every payment period (3 turns)
        self.load_saved()
    
    def load_saved(self):
        """Load all loans from the database."""
        loan_data = self.tlog_connection.get_all_loans()
        self.write_lock.acquire()
        self.loans = {}
        for loan_row in loan_data:
            # Handle both old schema and new schema with additional columns
            interest_compounds = loan_row[9] if len(loan_row) > 9 else True
            compounding_interval_turns = loan_row[10] if len(loan_row) > 10 else None
            late_fees = loan_row[11] if len(loan_row) > 11 else 0
            loan = Loan(
                loan_id=loan_row[0],
                borrower_id=loan_row[1],
                principal=loan_row[2],
                interest_rate=loan_row[3],
                payment_interval_turns=loan_row[4],
                created_at_turn=loan_row[5],
                status=LoanStatus(loan_row[6]),
                amount_paid=loan_row[7],
                next_payment_due_turn=loan_row[8],
                interest_compounds=interest_compounds,
                compounding_interval_turns=compounding_interval_turns,
                late_fees=late_fees,
                loan_term_periods=3  # Default to 3 payment periods
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
    
    def check_loan_eligibility(self, borrower_id, requested_amount=0):
        """
        Check if a player qualifies for a loan.
        If requested_amount is 0 or not provided, just checks general eligibility.
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
        
        # Only check against requested amount if a specific amount was provided
        if requested_amount > 0 and requested_amount > max_loan:
            return False, f"Requested ${requested_amount} exceeds maximum ${max_loan}", max_loan
        
        return True, "Qualified for loan", max_loan
    
    def create_loan(self, borrower_id, amount, payment_interval_turns=None, approved_by_banker=False, current_turn=0, interest_compounds=True, loan_term_periods=None):
        """
        Create a new loan for a player.
        If approved_by_banker is True, bypasses credit checks.
        interest_compounds: Whether the loan uses compound interest (default True for users)
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
        interval = payment_interval_turns if payment_interval_turns else self.default_payment_interval_turns
        term = loan_term_periods if loan_term_periods else 12  # Default to 12 payment periods
        
        loan = Loan(
            loan_id=loan_id,
            borrower_id=borrower_id,
            principal=amount,
            interest_rate=self.loan_interest_rate,
            payment_interval_turns=interval,
            created_at_turn=current_turn,
            status=LoanStatus.ACTIVE,
            interest_compounds=interest_compounds,
            compounding_interval_turns=self.compounding_interval_turns,
            loan_term_periods=term
        )
        
        self.write_lock.acquire()
        self.loans[loan_id] = loan
        self.write_lock.release()
        
        # Save to database
        self.tlog_connection.create_loan(
            loan_id, borrower_id, amount, self.loan_interest_rate,
            interval, loan.created_at_turn, loan.next_payment_due_turn,
            interest_compounds, self.compounding_interval_turns, late_fees=0, loan_term_periods=term
        )
        
        # Deposit loan amount into account
        account.deposit(amount, log=True)
        
        return True, loan_id
    
    def make_payment(self, loan_id, amount, current_turn=0):
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
        paid_off, message = loan.make_payment(amount, current_turn)
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
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
                loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
            )
            self.tlog_connection.log_loan_payment(
                loan_id, loan.borrower_id, loan.amount_paid, True
            )
            return True, f"Loan paid off through asset liquidation. {liquidation_msg}"
        
        # If still unpaid, mark as defaulted
        loan.default_loan()
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
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
            loan.make_payment(cash_payment, 0)  # Use turn 0 for liquidation
            total_liquidated += cash_payment
            liquidated_items.append(f"${cash_payment} cash")
            
            self.tlog_connection.update_loan(
                loan.loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
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
                loan.make_payment(payment, 0)  # Use turn 0 for liquidation
                
                total_liquidated += payment
                liquidated_items.append(f"{prop.name} (${payment})")
                
                self.tlog_connection.update_loan(
                    loan.loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
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
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
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
    
    def apply_late_fees_all(self):
        """
        Apply late fees to all overdue loans.
        Called at the start of each turn.
        Returns dict of borrower_id -> accumulated late fees for that turn.
        """
        late_fees_charged = {}
        for loan in self.loans.values():
            if loan.status == LoanStatus.ACTIVE:
                fee = loan.accumulate_late_fees()
                if fee > 0:
                    if loan.borrower_id not in late_fees_charged:
                        late_fees_charged[loan.borrower_id] = 0
                    late_fees_charged[loan.borrower_id] += fee
        return late_fees_charged
    
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
    
    def schedule_payment_notification(self, loan_id, delay_turns=None):
        """
        Schedule a payment notification to be sent after a delay.
        If delay_turns is None, uses the loan's payment interval.
        Note: This method is kept for compatibility but payment intervals are now turn-based.
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        delay = delay_turns if delay_turns is not None else loan.payment_interval_turns
        
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
