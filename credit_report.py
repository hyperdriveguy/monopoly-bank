"""
Comprehensive Credit Report System

This module provides a real-world-inspired credit scoring system for the Monopoly Bank
with a mathematically-grounded foundation. All scoring is based on normalized factors (0-1)
that are combined using weighted averages.

It evaluates creditworthiness based on:
- Payment history (punctuality, defaults, late payments)
- Current assets (cash and property values)
- Debt utilization (current debt vs. credit limit)
- Account age and activity
- Payment consistency
- A small random factor for realism

Board assumptions:
- Total fully-upgraded board value: $28,670
- Hard credit cap: 75% of board value (~$21,500)
"""

import math
import random
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict


# -------------------------
# Global economic constants
# -------------------------

BOARD_VALUE_MAX = 28_670  # Total fully-upgraded board value
HARD_CREDIT_CAP = 0.75 * BOARD_VALUE_MAX  # Absolute lending ceiling (~$21,500)
MIN_SCORE = 300
MAX_SCORE = 850


class CreditRating(Enum):
    """Credit ratings based on credit score."""
    EXCELLENT = "Excellent"      # 750+
    GOOD = "Good"                 # 620-749
    FAIR = "Fair"                 # 545-619
    POOR = "Poor"                 # 500-544
    VERY_POOR = "Very Poor"       # <500


@dataclass
class PaymentRecord:
    """Record of a single payment."""
    loan_id: str
    amount_paid: float
    amount_owed: float
    payment_date_turn: int
    due_date_turn: int
    on_time: bool = True
    late_by_turns: int = 0
    loan_amount: float = 0
    interest_rate: float = 0


@dataclass
class PaymentHistory:
    """Tracks all payment activity for an account."""
    account_id: str
    payments: List[PaymentRecord] = field(default_factory=list)
    total_payments_made: int = 0
    total_loans_created: int = 0
    total_loans_paid_off: int = 0
    total_loans_defaulted: int = 0
    on_time_payments: int = 0
    late_payments: int = 0
    consecutive_on_time_payments: int = 0
    account_created_turn: int = 0
    last_payment_turn: int = 0  # For stability scoring
    
    def add_payment(self, record: PaymentRecord):
        """Add a payment record and update stats."""
        self.payments.append(record)
        self.total_payments_made += 1
        self.last_payment_turn = record.payment_date_turn
        
        if record.on_time:
            self.on_time_payments += 1
            self.consecutive_on_time_payments += 1
        else:
            self.late_payments += 1
            self.consecutive_on_time_payments = 0
    
    def mark_loan_created(self):
        """Record a new loan creation."""
        self.total_loans_created += 1
    
    def mark_loan_paid_off(self):
        """Record a loan being paid off."""
        self.total_loans_paid_off += 1
    
    def mark_loan_defaulted(self):
        """Record a loan default."""
        self.total_loans_defaulted += 1
    
    @property
    def payment_success_rate(self) -> float:
        """Percentage of payments made on time."""
        if self.total_payments_made == 0:
            return 0.0  # No payments made yet, show 0% not 100%
        return self.on_time_payments / self.total_payments_made
    
    @property
    def has_recent_default(self) -> bool:
        """Check if there's been a default in recent history."""
        return self.total_loans_defaulted > 0


class CreditReport:
    """
    Comprehensive credit report for an account.
    Uses mathematically-grounded normalized factors (0-1 range) combined with weighted averaging.
    """
    
    # Credit score calculation weights (sum to 1.0 excluding random)
    PAYMENT_HISTORY_WEIGHT = 0.35  # Payment record - most important
    ASSET_WEIGHT = 0.20            # Current assets
    DEBT_WEIGHT = 0.15             # Debt utilization
    HISTORY_WEIGHT = 0.10          # Account age
    CONSISTENCY_WEIGHT = 0.10      # Payment consistency
    LIQUIDITY_WEIGHT = 0.10        # Cash reserves
    
    # Score ranges
    MIN_SCORE = MIN_SCORE
    MAX_SCORE = MAX_SCORE
    
    def __init__(self, account_id: str, payment_history: PaymentHistory):
        self.account_id = account_id
        self.payment_history = payment_history
        self.credit_score = self.MIN_SCORE
        self.rating = CreditRating.VERY_POOR
        self.generated_turn = 0
        self.risk_factors: List[str] = []
        self.positive_factors: List[str] = []
    
    def calculate(self, current_turn: int, account_cash: float, 
                  account_properties: List, active_loans: List, 
                  completed_loans: List) -> int:
        """
        Calculate comprehensive credit score using normalized factors.
        
        Args:
            current_turn: Current game turn
            account_cash: Cash available
            account_properties: List of properties owned
            active_loans: List of active loans
            completed_loans: List of completed/paid off loans
        
        Returns:
            Credit score (300-850)
        """
        self.generated_turn = current_turn
        self.risk_factors = []
        self.positive_factors = []
        
        # Calculate total property value
        property_value = self._calculate_property_value(account_properties)
        
        # Calculate current debt
        current_debt = sum(
            loan.remaining_balance for loan in active_loans
            if hasattr(loan, 'remaining_balance')
        )
        
        # Calculate credit limit based on previous score (or default for new accounts)
        current_credit_limit = self._compute_credit_limit(self.credit_score)
        
        # Calculate payment delay standard deviation
        payment_delay_std = self._calculate_payment_delay_std(current_turn)
        
        # Calculate normalized factors (0-1 range)
        payment_factor = self._payment_history_factor()
        asset_factor = self._asset_factor(account_cash, property_value)
        debt_factor = self._debt_factor(current_debt, current_credit_limit)
        history_factor = self._history_factor(current_turn)
        consistency_factor = self._consistency_factor(payment_delay_std)
        liquidity_factor = self._liquidity_factor(account_cash, property_value)
        
        # Deterministic random factor for realism (±5%)
        # Use seeded random based on account ID and turn so same account+turn produces same score
        rng = random.Random(hash(f"{self.account_id}_{current_turn}"))
        random_factor = rng.uniform(-0.05, 0.05)
        
        # Weighted calculation
        weighted = (
            self.PAYMENT_HISTORY_WEIGHT * payment_factor +
            self.ASSET_WEIGHT * asset_factor +
            self.DEBT_WEIGHT * debt_factor +
            self.HISTORY_WEIGHT * history_factor +
            self.CONSISTENCY_WEIGHT * consistency_factor +
            self.LIQUIDITY_WEIGHT * liquidity_factor +
            random_factor
        )
        
        # Clamp to [0, 1] and map to score range
        weighted = min(1.0, max(0.0, weighted))
        self.credit_score = MIN_SCORE + int(weighted * (MAX_SCORE - MIN_SCORE))
        self.rating = self._get_rating(self.credit_score)
        
        return self.credit_score
    
    def _calculate_property_value(self, account_properties: List) -> float:
        """Calculate total property value."""
        property_value = 0
        for prop in account_properties:
            if hasattr(prop, 'costs') and 'property' in prop.costs:
                if hasattr(prop, 'mortgaged') and not prop.mortgaged:
                    property_value += prop.costs['property']
                else:
                    # Mortgaged properties worth half
                    property_value += prop.costs['property'] // 2
        return property_value
    
    def _calculate_payment_delay_std(self, current_turn: int) -> float:
        """Calculate standard deviation of payment delays."""
        if self.payment_history.total_payments_made == 0:
            return 0.0
        
        delays = []
        for payment in self.payment_history.payments:
            delay = max(0, payment.payment_date_turn - payment.due_date_turn)
            delays.append(delay)
        
        if not delays:
            return 0.0
        
        mean_delay = sum(delays) / len(delays)
        variance = sum((d - mean_delay) ** 2 for d in delays) / len(delays)
        return math.sqrt(variance)
    
    def _payment_history_factor(self) -> float:
        """
        Evaluates payment history with recovery potential.
        Penalizes late payments and defaults, but allows recovery through consistent on-time payments.
        Returns normalized score in [0, 1].
        """
        late = self.payment_history.late_payments
        defaults = self.payment_history.total_loans_defaulted
        on_time = self.payment_history.on_time_payments
        consecutive_on_time = self.payment_history.consecutive_on_time_payments
        total_payments = self.payment_history.total_payments_made
        
        # Base penalty for defaults and late payments
        base_penalty = -(0.3 * late + 1.5 * defaults)
        
        # Recovery bonus: recent consecutive on-time payments can partially offset defaults
        # Each 3 consecutive on-time payments reduces default penalty by 0.5
        recovery_bonus = 0.0
        if consecutive_on_time > 0:
            recovery_bonus = min(0.5 * defaults, (consecutive_on_time / 3) * 0.5 * defaults)
        
        factor = math.exp(base_penalty + recovery_bonus)
        
        # Track risk/positive factors
        if defaults > 0 and consecutive_on_time < 3:
            self.risk_factors.append(f"LOAN DEFAULT: {defaults} loan(s) - Demonstrate {3 - consecutive_on_time} more on-time payments to recover")
        elif defaults > 0 and consecutive_on_time >= 3:
            self.positive_factors.append(f"Recovering from default: {consecutive_on_time} consecutive on-time payments")
        
        if late > 0:
            self.risk_factors.append(f"{late} late payment(s)")
        
        if late == 0 and defaults == 0 and total_payments > 0:
            self.positive_factors.append("Perfect payment history")
        elif total_payments > 0 and on_time == total_payments:
            self.positive_factors.append("All recent payments on-time")
        
        return factor
    
    def _asset_factor(self, cash: float, property_value: float) -> float:
        """
        Normalizes current assets against total board value.
        Returns normalized score in [0, 1].
        """
        total_assets = cash + property_value
        factor = min(1.0, total_assets / BOARD_VALUE_MAX)
        
        # Track positive factors
        if total_assets >= 12000:
            self.positive_factors.append("Exceptional asset portfolio (near board control)")
        elif total_assets >= 8000:
            self.positive_factors.append("Strong asset portfolio")
        elif total_assets >= 5000:
            self.positive_factors.append("Good asset base")
        elif total_assets >= 3000:
            self.positive_factors.append("Established asset position")
        elif total_assets < 500:
            self.risk_factors.append("Low asset base")
        
        return factor
    
    def _debt_factor(self, current_debt: float, credit_limit: float) -> float:
        """
        Measures debt utilization relative to allowed credit.
        Returns normalized score in [0, 1].
        """
        if credit_limit <= 0:
            if current_debt > 0:
                self.risk_factors.append("Debt without established credit limit")
                return 0.0
            return 1.0  # No debt, no limit = perfect
        
        utilization = current_debt / credit_limit
        factor = max(0.0, 1.0 - utilization)
        
        # Track risk/positive factors
        if utilization <= 0.1:
            self.positive_factors.append("Very low credit utilization")
        elif utilization <= 0.3:
            self.positive_factors.append("Low credit utilization")
        elif utilization <= 0.5:
            self.positive_factors.append("Moderate credit utilization")
        elif utilization <= 1.0:
            self.risk_factors.append(f"High credit utilization ({utilization*100:.0f}%)")
        else:
            self.risk_factors.append(f"Credit utilization exceeds limit ({utilization*100:.0f}%)")
        
        return factor
    
    def _history_factor(self, current_turn: int, reference_turns: int = 50) -> float:
        """
        Rewards long-standing credit activity.
        Returns normalized score in [0, 1].
        """
        if self.payment_history.account_created_turn == 0:
            return 0.5  # New accounts get neutral score
        
        turns_active = current_turn - self.payment_history.account_created_turn
        factor = min(1.0, turns_active / reference_turns)
        
        # Track positive factors
        if turns_active >= reference_turns:
            self.positive_factors.append("Established credit history")
        elif turns_active >= reference_turns // 2:
            self.positive_factors.append("Growing credit history")
        
        return factor
    
    def _consistency_factor(self, payment_delay_std: float) -> float:
        """
        Penalizes erratic payment behavior.
        Returns normalized score in [0, 1].
        """
        factor = math.exp(-0.5 * payment_delay_std)
        
        # Track risk/positive factors
        if payment_delay_std == 0 and self.payment_history.total_payments_made > 0:
            self.positive_factors.append("Consistent payment behavior")
        elif payment_delay_std > 3.0:
            self.risk_factors.append("Inconsistent payment timing")
        
        return factor
    
    def _liquidity_factor(self, cash: float, property_value: float) -> float:
        """
        Measures proportion of liquid assets (cash) vs locked assets.
        Returns normalized score in [0, 1].
        """
        total_assets = cash + property_value
        
        if total_assets == 0:
            return 0.5  # Neutral for accounts with no assets
        
        liquidity_ratio = cash / total_assets
        
        # Moderate liquidity is ideal (30-70%)
        # Too much cash = not investing, too little = can't pay debts
        if liquidity_ratio >= 0.3 and liquidity_ratio <= 0.7:
            factor = 1.0
            self.positive_factors.append("Good liquidity balance")
        elif liquidity_ratio > 0.7:
            factor = 0.8
            if liquidity_ratio >= 0.95:
                self.positive_factors.append("High cash reserves (underutilized)")
            else:
                self.positive_factors.append("Strong cash reserves")
        else:
            # Low liquidity
            factor = 0.5 + (liquidity_ratio / 0.3) * 0.5
            if liquidity_ratio < 0.1:
                self.risk_factors.append("Low liquidity (assets locked in properties)")
        
        return factor
    
    def _compute_credit_limit(self, score: int) -> float:
        """
        Converts a credit score into a maximum allowable loan amount.
        Uses a superlinear curve to reflect Monopoly's snowball economy.
        
        Args:
            score: Credit score in [300, 850].
        
        Returns:
            Credit limit in Monopoly dollars.
        """
        normalized = (score - MIN_SCORE) / (MAX_SCORE - MIN_SCORE)
        normalized = min(1.0, max(0.0, normalized))
        return HARD_CREDIT_CAP * (normalized ** 1.5)
    
    def get_credit_limit(self) -> float:
        """Get the current credit limit based on credit score."""
        return self._compute_credit_limit(self.credit_score)
    
    def _get_rating(self, score: int) -> CreditRating:
        """Convert score to rating aligned with lending thresholds."""
        if score >= 750:
            return CreditRating.EXCELLENT  # Elite borrowers
        elif score >= 620:
            return CreditRating.GOOD       # Automatic approval
        elif score >= 545:
            return CreditRating.FAIR       # Conditional approval
        elif score >= 500:
            return CreditRating.POOR       # Manual review needed
        else:
            return CreditRating.VERY_POOR  # High risk
    
    def to_dict(self) -> Dict:
        """Convert credit report to dictionary."""
        return {
            'account_id': self.account_id,
            'credit_score': self.credit_score,
            'rating': self.rating.value,
            'generated_turn': self.generated_turn,
            'risk_factors': self.risk_factors,
            'positive_factors': self.positive_factors,
            'payment_history': {
                'total_payments_made': self.payment_history.total_payments_made,
                'total_loans_created': self.payment_history.total_loans_created,
                'total_loans_paid_off': self.payment_history.total_loans_paid_off,
                'total_loans_defaulted': self.payment_history.total_loans_defaulted,
                'on_time_payments': self.payment_history.on_time_payments,
                'late_payments': self.payment_history.late_payments,
                'consecutive_on_time_payments': self.payment_history.consecutive_on_time_payments,
                'payment_success_rate': f"{self.payment_history.payment_success_rate * 100:.1f}%"
            }
        }
    
    def __str__(self) -> str:
        """Human-readable credit report."""
        report = f"\n{'='*50}\n"
        report += f"CREDIT REPORT - {self.account_id}\n"
        report += f"{'='*50}\n"
        report += f"Credit Score: {self.credit_score}/850\n"
        report += f"Rating: {self.rating.value}\n"
        report += f"Generated: Turn {self.generated_turn}\n\n"
        
        report += f"PAYMENT HISTORY\n"
        report += f"  Total Payments: {self.payment_history.total_payments_made}\n"
        report += f"  On-Time: {self.payment_history.on_time_payments} "
        report += f"({self.payment_history.payment_success_rate * 100:.1f}%)\n"
        report += f"  Late: {self.payment_history.late_payments}\n"
        report += f"  Consecutive On-Time: {self.payment_history.consecutive_on_time_payments}\n"
        report += f"  Total Loans: {self.payment_history.total_loans_created}\n"
        report += f"  Paid Off: {self.payment_history.total_loans_paid_off}\n"
        report += f"  Defaulted: {self.payment_history.total_loans_defaulted}\n\n"
        
        if self.positive_factors:
            report += f"POSITIVE FACTORS\n"
            for factor in self.positive_factors:
                report += f"  ✓ {factor}\n"
            report += "\n"
        
        if self.risk_factors:
            report += f"RISK FACTORS\n"
            for factor in self.risk_factors:
                report += f"  ✗ {factor}\n"
            report += "\n"
        
        report += f"{'='*50}\n"
        return report


class CreditReportManager:
    """
    Manages credit reports and payment history for all accounts.
    """
    
    def __init__(self):
        self.payment_histories: Dict[str, PaymentHistory] = {}
        self.credit_reports: Dict[str, CreditReport] = {}
    
    def initialize_account(self, account_id: str, current_turn: int):
        """Initialize credit tracking for a new account."""
        if account_id not in self.payment_histories:
            history = PaymentHistory(account_id=account_id, account_created_turn=current_turn)
            self.payment_histories[account_id] = history
            self.credit_reports[account_id] = CreditReport(account_id, history)
    
    def record_payment(self, loan_id: str, account_id: str, amount: float,
                      amount_owed: float, payment_turn: int, due_turn: int,
                      loan_amount: float = 0, interest_rate: float = 0):
        """Record a loan payment."""
        if account_id not in self.payment_histories:
            return
        
        on_time = payment_turn <= due_turn
        late_by = max(0, payment_turn - due_turn) if not on_time else 0
        
        record = PaymentRecord(
            loan_id=loan_id,
            amount_paid=amount,
            amount_owed=amount_owed,
            payment_date_turn=payment_turn,
            due_date_turn=due_turn,
            on_time=on_time,
            late_by_turns=late_by,
            loan_amount=loan_amount,
            interest_rate=interest_rate
        )
        
        self.payment_histories[account_id].add_payment(record)
    
    def record_loan_created(self, account_id: str):
        """Record a new loan creation."""
        if account_id not in self.payment_histories:
            return
        self.payment_histories[account_id].mark_loan_created()
    
    def record_loan_paid_off(self, account_id: str):
        """Record a loan being paid off."""
        if account_id not in self.payment_histories:
            return
        self.payment_histories[account_id].mark_loan_paid_off()
    
    def record_loan_default(self, account_id: str):
        """Record a loan default."""
        if account_id not in self.payment_histories:
            return
        self.payment_histories[account_id].mark_loan_defaulted()
    
    def generate_report(self, account_id: str, current_turn: int,
                       account_cash: float, account_properties: List,
                       active_loans: List, completed_loans: Optional[List] = None) -> CreditReport:
        """Generate/update a credit report for an account."""
        if account_id not in self.payment_histories:
            self.initialize_account(account_id, current_turn)
        
        if completed_loans is None:
            completed_loans = []
        
        report = self.credit_reports[account_id]
        report.calculate(current_turn, account_cash, account_properties, 
                        active_loans, completed_loans)
        return report
    
    def get_report(self, account_id: str) -> Optional[CreditReport]:
        """Get the most recent credit report for an account."""
        return self.credit_reports.get(account_id)
    
    def get_history(self, account_id: str) -> Optional[PaymentHistory]:
        """Get payment history for an account."""
        return self.payment_histories.get(account_id)
