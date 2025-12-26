import time
import uuid
from datetime import datetime, timedelta
from threading import Timer, Lock
from enum import Enum
from credit_report import CreditReportManager, CreditRating, PaymentRecord



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
                 compounding_interval_turns=None, late_fees=0, loan_term_periods=3, missed_payments=0):
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
        self.missed_payments = missed_payments  # Number of consecutive missed payment periods
        
    @property
    def total_owed(self):
        """Calculate total amount owed including interest."""
        # Resolved loans stop accruing interest (debt has been forgiven/settled)
        if self.status == LoanStatus.RESOLVED:
            return self.amount_paid  # Return what was already paid as the settled amount
        
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
        
        # Reset missed payments counter on successful payment
        self.missed_payments = 0
        
        # Check if loan is paid off (before updating next payment due)
        if self.remaining_balance <= 0:
            self.status = LoanStatus.PAID_OFF
            return True, f"Loan paid off! Total paid: ${self.amount_paid}"
        
        # Update next payment due turn only if loan is still active
        self.next_payment_due_turn = current_turn + self.payment_interval_turns
        
        return False, f"Payment of ${amount} applied. Remaining balance: ${self.remaining_balance}"
    
    def accumulate_late_fees(self):
        """Add late fees if payment is overdue. Called each turn.
        Also checks for auto-default after 2 missed payment periods.
        """
        if self.is_overdue:
            self.late_fees += self.late_fee_per_turn
            
            # Check if we've crossed into a new missed payment period
            turns_overdue = Loan._current_turn - self.next_payment_due_turn
            periods_missed = (turns_overdue // self.payment_interval_turns) + 1
            
            if periods_missed > self.missed_payments:
                self.missed_payments = periods_missed
                
                # Auto-default after 2 missed payment periods
                if self.missed_payments >= 2:
                    self.default_loan()
            
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
            'late_fees': self.late_fees,
            'missed_payments': self.missed_payments
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
            late_fees=data.get('late_fees', 0),
            missed_payments=data.get('missed_payments', 0)
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
        self.credit_report_manager = CreditReportManager()  # Comprehensive credit system
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
        
        # Rebuild credit history from loan data
        self._rebuild_credit_history()
        
        return f'Loaded {len(self.loans)} loan{"s" if len(self.loans) != 1 else ""} from database'
    
    def _rebuild_credit_history(self):
        """
        Rebuild credit history from existing loan data and payment records.
        This ensures credit reports accurately reflect loan defaults and history.
        """
        # Clear any existing credit history to avoid double-counting
        self.credit_report_manager.payment_histories.clear()
        self.credit_report_manager.credit_reports.clear()
        
        # Group loans by borrower
        borrower_loans = {}
        for loan in self.loans.values():
            if loan.borrower_id not in borrower_loans:
                borrower_loans[loan.borrower_id] = []
            borrower_loans[loan.borrower_id].append(loan)
        
        # Rebuild credit history for each borrower
        for borrower_id, loans in borrower_loans.items():
            # Initialize account - creates fresh PaymentHistory
            self.credit_report_manager.initialize_account(borrower_id, current_turn=1)
            
            # Load payment records from database
            payment_records = self.tlog_connection.get_payment_records_for_account(borrower_id)
            for record in payment_records:
                loan_id, amount_paid, amount_owed, payment_date_turn, due_date_turn, on_time, late_by_turns, loan_amount, interest_rate = record
                
                # Recreate PaymentRecord object
                payment_record = PaymentRecord(
                    loan_id=loan_id,
                    amount_paid=amount_paid,
                    amount_owed=amount_owed,
                    payment_date_turn=payment_date_turn,
                    due_date_turn=due_date_turn,
                    on_time=bool(on_time),
                    late_by_turns=late_by_turns,
                    loan_amount=loan_amount,
                    interest_rate=interest_rate
                )
                # Add to payment history
                self.credit_report_manager.payment_histories[borrower_id].add_payment(payment_record)
            
            # Count loans by status
            for loan in loans:
                # Record loan creation
                self.credit_report_manager.record_loan_created(borrower_id)
                
                # Record loan outcome
                if loan.status == LoanStatus.PAID_OFF:
                    self.credit_report_manager.record_loan_paid_off(borrower_id)
                elif loan.status == LoanStatus.RESOLVED:
                    # Resolved loans count as BOTH defaulted AND paid off
                    # (Default happened, but player paid to resolve it)
                    self.credit_report_manager.record_loan_default(borrower_id)
                    self.credit_report_manager.record_loan_paid_off(borrower_id)
                elif loan.status == LoanStatus.DEFAULTED:
                    self.credit_report_manager.record_loan_default(borrower_id)
                
                # Note: We don't have payment history details, but defaults are the
                # most critical factor for credit scoring, so this rebuilds the
                # essential credit information
    
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
    
    def generate_credit_report(self, borrower_id, current_turn):
        """
        Generate a comprehensive credit report for a borrower.
        Returns the credit report object.
        """
        account = self.account_manager.query(borrower_id)
        if account == 'Account does not exist.':
            return None
        
        # Initialize account in credit system if not already done
        self.credit_report_manager.initialize_account(borrower_id, current_turn)
        
        # Get active and completed loans for this borrower
        all_loans_for_borrower = self.get_loans_by_borrower(borrower_id)
        active_loans = [loan for loan in all_loans_for_borrower if loan.status == LoanStatus.ACTIVE]
        completed_loans = [loan for loan in all_loans_for_borrower if loan.status == LoanStatus.PAID_OFF]
        
        # Generate and return the comprehensive credit report
        report = self.credit_report_manager.generate_report(
            borrower_id,
            current_turn,
            account.cash,
            list(account.properties),
            active_loans,
            completed_loans
        )
        
        return report
    
    def get_credit_report(self, borrower_id):
        """Get the most recent credit report for a borrower."""
        return self.credit_report_manager.get_report(borrower_id)
    
    def check_loan_eligibility(self, borrower_id, requested_amount=0):
        """
        Check if a player qualifies for a loan.
        Credit score is the primary determinant - higher scores get better terms.
        Returns (eligible: bool, reason: str, max_amount: int, interest_multiplier: float)
        """
        account = self.account_manager.query(borrower_id)
        if account == 'Account does not exist.':
            return False, "Account does not exist", 0, 1.0
        
        # Check for ACTIVE defaults (not RESOLVED)
        if self.has_active_defaulted_loans(borrower_id):
            return False, "You have an active loan default. Settle the default before applying for new loans.", 0, 1.0
        
        # Get credit report
        from loan_store import Loan
        current_turn = Loan._current_turn
        credit_report = self.generate_credit_report(borrower_id, current_turn)
        if credit_report is None:
            return False, "Cannot generate credit report", 0, 1.0
        
        credit_score = credit_report.credit_score
        
        # Simple eligibility: credit score must meet minimum threshold
        if credit_score < self.min_credit_score:
            return False, (
                f"Credit score too low ({credit_score}/850). "
                f"Need at least {self.min_credit_score} for auto-approval."
            ), 0, 1.0
        
        # Calculate interest multiplier based on credit score
        # Excellent credit (750+): 0.8x, Good (620-749): 0.9x, Fair (545-619): 1.0x, Poor: 1.25x, Very Poor: 1.5x
        score_normalized = (credit_score - 300) / 550  # Normalize to [0, 1]
        interest_multiplier = 1.5 - (score_normalized * 0.7)  # Range from 1.5 to 0.8
        interest_multiplier = max(0.8, min(1.5, interest_multiplier))  # Clamp to [0.8, 1.5]
        
        # Calculate max loan based on credit score and assets
        available_assets = self.calculate_credit_score(account)
        # Higher credit scores can borrow more (up to 120% at excellent, down to 25% at very poor)
        borrow_multiple = 0.25 + (score_normalized * 0.95)  # Range from 0.25 to 1.2
        max_loan = min(self.max_loan_amount, int(available_assets * borrow_multiple))
        
        # Reduce max loan by existing debt
        active_loans = self.get_loans_by_borrower(borrower_id, active_only=True)
        total_debt = sum(loan.remaining_balance for loan in active_loans)
        max_loan = max(0, max_loan - int(total_debt * 0.3))
        
        if max_loan <= 0:
            return False, f"Too much existing debt (${total_debt}). Pay off loans first.", 0, interest_multiplier
        
        # Check requested amount if specified
        if requested_amount > 0 and requested_amount > max_loan:
            return False, f"Requested ${requested_amount} exceeds maximum ${max_loan}", max_loan, interest_multiplier
        
        # Eligible for loan
        return True, f"Approved (Credit Score: {credit_score}/850)", max_loan, interest_multiplier
    
    def create_loan(self, borrower_id, amount, payment_interval_turns=None, approved_by_banker=False, current_turn=0, interest_compounds=True, loan_term_periods=None):
        """
        Create a new loan for a player.
        If approved_by_banker is True, bypasses credit checks.
        interest_compounds: Whether the loan uses compound interest (default True for users)
        Returns (success: bool, loan_id or error_message: str)
        """
        # Check eligibility unless banker approved
        interest_multiplier = 1.0  # Default multiplier
        if not approved_by_banker:
            eligible, reason, max_amount, interest_multiplier = self.check_loan_eligibility(borrower_id, amount)
            if not eligible:
                return False, reason
        
        account = self.account_manager.query(borrower_id)
        if account == 'Account does not exist.':
            return False, "Account does not exist"
        
        # Create loan with adjusted interest rate based on credit rating
        adjusted_interest_rate = self.loan_interest_rate * interest_multiplier
        
        loan_id = str(uuid.uuid4())[:8]
        interval = payment_interval_turns if payment_interval_turns else self.default_payment_interval_turns
        term = loan_term_periods if loan_term_periods else 12  # Default to 12 payment periods
        
        loan = Loan(
            loan_id=loan_id,
            borrower_id=borrower_id,
            principal=amount,
            interest_rate=adjusted_interest_rate,  # Use adjusted rate
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
            loan_id, borrower_id, amount, adjusted_interest_rate,  # Use adjusted rate
            interval, loan.created_at_turn, loan.next_payment_due_turn,
            interest_compounds, self.compounding_interval_turns, late_fees=0, loan_term_periods=term
        )
        
        # Record in credit system
        self.credit_report_manager.record_loan_created(borrower_id)
        
        # Deposit loan amount into account
        account.deposit(amount, log=True)
        
        return True, loan_id
    
    def make_payment(self, loan_id, amount, current_turn=0):
        """
        Make a payment on a loan (works for ACTIVE or DEFAULTED loans).
        For defaulted loans, this settles the outstanding debt.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        
        # Allow payments on ACTIVE or DEFAULTED loans only
        if loan.status not in [LoanStatus.ACTIVE, LoanStatus.DEFAULTED]:
            return False, f"Cannot make payment on {loan.status.value} loan"
        
        # Check if borrower has enough cash
        account = self.account_manager.query(loan.borrower_id)
        if account == 'Account does not exist.':
            return False, "Borrower account not found"
        
        if account.cash < amount:
            return False, f"Insufficient funds. Have ${account.cash}, need ${amount}"
        
        # Validate amount before withdrawing
        if amount <= 0:
            return False, "Payment amount must be positive"
        
        # Withdraw from account AFTER all validations
        account.withdraw(amount, log=True)
        
        # Record payment in credit system
        self.credit_report_manager.record_payment(
            loan_id=loan_id,
            account_id=loan.borrower_id,
            amount=amount,
            amount_owed=loan.total_owed,
            payment_turn=current_turn,
            due_turn=loan.next_payment_due_turn,
            loan_amount=loan.principal,
            interest_rate=loan.interest_rate
        )
        
        # Save payment record to database for persistence
        on_time = current_turn <= loan.next_payment_due_turn
        late_by = max(0, current_turn - loan.next_payment_due_turn) if not on_time else 0
        self.tlog_connection.save_payment_record(
            loan_id=loan_id,
            account_id=loan.borrower_id,
            amount_paid=amount,
            amount_owed=loan.total_owed,
            payment_date_turn=current_turn,
            due_date_turn=loan.next_payment_due_turn,
            on_time=on_time,
            late_by_turns=late_by,
            loan_amount=loan.principal,
            interest_rate=loan.interest_rate
        )
        
        # Apply payment to loan
        # For DEFAULTED loans, directly apply payment without loan.make_payment() checks
        if loan.status == LoanStatus.DEFAULTED:
            old_balance = loan.remaining_balance
            loan.amount_paid += amount
            paid_off = loan.remaining_balance <= 0
            
            if paid_off:
                loan.status = LoanStatus.RESOLVED
                message = f"Default settlement complete! Paid ${amount}. Remaining balance: ${max(0, old_balance - amount)}"
                self.credit_report_manager.record_loan_paid_off(loan.borrower_id)
            else:
                message = f"Settlement payment of ${amount} applied. Remaining debt: ${loan.remaining_balance}"
        else:
            # For ACTIVE loans, use normal payment logic
            paid_off, message = loan.make_payment(amount, current_turn)
            if paid_off:
                self.credit_report_manager.record_loan_paid_off(loan.borrower_id)
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
        )
        
        # Log payment
        self.tlog_connection.log_loan_payment(loan_id, loan.borrower_id, amount, paid_off if 'paid_off' in locals() else False)
        
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
            self.credit_report_manager.record_loan_paid_off(loan.borrower_id)
            return True, f"Loan paid off through asset liquidation. {liquidation_msg}"
        
        # If still unpaid, mark as defaulted
        loan.default_loan()
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
        )
        
        # Record default in credit system
        self.credit_report_manager.record_loan_default(loan.borrower_id)
        
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
    
    def has_active_defaulted_loans(self, borrower_id):
        """Check if a borrower has any currently DEFAULTED loans (not RESOLVED)."""
        return any(
            loan.status == LoanStatus.DEFAULTED 
            for loan in self.loans.values() 
            if loan.borrower_id == borrower_id
        )
    
    def has_defaulted_loans(self, borrower_id):
        """Deprecated: use has_active_defaulted_loans instead. Kept for backward compatibility."""
        return self.has_active_defaulted_loans(borrower_id)
    
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
    
    def restructure_loan(self, loan_id, new_payment_interval_turns=None, freeze_interest=False):
        """
        Restructure a loan to prevent default. Extends payment dates and optionally freezes interest.
        This is a banker action to help at-risk borrowers.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        
        if loan.status not in [LoanStatus.ACTIVE, LoanStatus.DEFAULTED]:
            return False, f"Cannot restructure {loan.status.value} loan"
        
        old_interval = loan.payment_interval_turns
        old_interest_rate = loan.interest_rate
        
        # Extend payment interval if specified
        if new_payment_interval_turns:
            if new_payment_interval_turns <= 0:
                return False, "Payment interval must be positive"
            loan.payment_interval_turns = new_payment_interval_turns
            # Push next payment due date further out
            loan.next_payment_due_turn = Loan._current_turn + new_payment_interval_turns
        
        # Freeze interest if requested
        if freeze_interest:
            loan.interest_rate = 0
            loan.interest_compounds = False
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
        )
        
        # Log the restructuring
        changes = []
        if new_payment_interval_turns:
            changes.append(f"payment interval: {old_interval} → {new_payment_interval_turns} turns")
        if freeze_interest:
            changes.append(f"interest rate: {old_interest_rate*100:.1f}% → 0% (frozen)")
        
        changes_str = ", ".join(changes)
        return True, f"Loan {loan_id} restructured: {changes_str}"
    
    def pause_loan_payments(self, loan_id, pause_turns):
        """
        Pause payments on a loan for a specified number of turns.
        Extends the next payment due date without accruing additional fees.
        Banker action to help at-risk borrowers.
        Returns (success: bool, message: str)
        """
        if loan_id not in self.loans:
            return False, "Loan not found"
        
        loan = self.loans[loan_id]
        
        if loan.status not in [LoanStatus.ACTIVE, LoanStatus.DEFAULTED]:
            return False, f"Cannot pause payments on {loan.status.value} loan"
        
        if pause_turns <= 0:
            return False, "Pause duration must be positive"
        
        old_due_turn = loan.next_payment_due_turn
        loan.next_payment_due_turn = Loan._current_turn + pause_turns
        
        # Update database
        self.tlog_connection.update_loan(
            loan_id, loan.amount_paid, loan.status.value, loan.next_payment_due_turn
        )
        
        return True, f"Loan {loan_id} payments paused for {pause_turns} turns (due: turn {old_due_turn} → {loan.next_payment_due_turn})"
    
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
        Returns dict of borrower_id -> accumulated late fees for that turn,
        and list of auto-defaulted loan_ids.
        """
        late_fees_charged = {}
        auto_defaulted = []
        
        for loan in self.loans.values():
            if loan.status == LoanStatus.ACTIVE:
                fee = loan.accumulate_late_fees()
                if fee > 0:
                    if loan.borrower_id not in late_fees_charged:
                        late_fees_charged[loan.borrower_id] = 0
                    late_fees_charged[loan.borrower_id] += fee
                
                # Check if loan was auto-defaulted
                if loan.status == LoanStatus.DEFAULTED:
                    auto_defaulted.append(loan.loan_id)
                    # Record default in payment history
                    self.credit_report_manager.record_loan_default(loan.borrower_id)
        
        return late_fees_charged, auto_defaulted
    
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
    
    def get_borrower_credit_summary(self, borrower_id, current_turn):
        """
        Get a detailed credit summary for a borrower suitable for display.
        Returns a dictionary with credit score, rating, factors, and loan details.
        """
        # Generate fresh credit report
        report = self.generate_credit_report(borrower_id, current_turn)
        
        if report is None:
            return {
                'error': 'Could not generate credit report',
                'borrower_id': borrower_id
            }
        
        # Get account details
        account = self.account_manager.query(borrower_id)
        if account == 'Account does not exist.':
            return {'error': 'Account not found'}
        
        # Calculate total assets
        total_assets = account.cash
        for prop in account.properties:
            if hasattr(prop, 'costs') and 'property' in prop.costs:
                if hasattr(prop, 'mortgaged') and not prop.mortgaged:
                    total_assets += prop.costs['property']
                else:
                    total_assets += prop.costs['property'] // 2
        
        # Get loan information
        active_loans = self.get_loans_by_borrower(borrower_id, active_only=True)
        total_debt = sum(loan.remaining_balance for loan in active_loans)
        
        return {
            'borrower_id': borrower_id,
            'credit_score': report.credit_score,
            'credit_rating': report.rating.value,
            'total_assets': total_assets,
            'available_cash': account.cash,
            'property_value': total_assets - account.cash,
            'total_active_debt': total_debt,
            'debt_to_assets_ratio': round(total_debt / total_assets if total_assets > 0 else 0, 2),
            'active_loans_count': len(active_loans),
            'positive_factors': report.positive_factors,
            'risk_factors': report.risk_factors,
            'payment_history': report.payment_history.__dict__ if hasattr(report, 'payment_history') else {}
        }
