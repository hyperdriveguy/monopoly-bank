# Turn-Based Payment System Implementation

## Overview
Payment intervals have been converted from real-time (seconds) to turn-based mechanics. The banker now has a turn incrementer on the main page, and the current turn number is displayed to all players.

## Changes Made

### 1. **server.py** - Core Server Logic
- **Added global game state**: `game_state = {'current_turn': 0}` to track the current game turn
- **Updated render_generic()**: Added `current_turn=game_state['current_turn']` to all template renderings
- **Updated home_page()**: 
  - Removed `payment_interval` form field and display
  - Added 'increment-turn' form handling for bankers
  - Added turn increment logic
- **Updated loan routes**:
  - `loans_page()`: Pass `game_state['current_turn']` to `get_overdue_loans()` and `is_overdue()` calls
  - `loan_application()`: Pass `game_state['current_turn']` to `create_loan()`
  - `individual_loan_page()`: Pass `game_state['current_turn']` to `make_payment()` calls

### 2. **loan_store.py** - Loan Management System
- **Updated Loan class**:
  - Changed `payment_interval` → `payment_interval_turns` (now an integer)
  - Changed `created_at` → `created_at_turn` (now an integer)
  - Changed `next_payment_due` → `next_payment_due_turn` (now an integer)
  - Updated `is_overdue` property to accept `current_turn` parameter
  - Updated `make_payment()` to accept `current_turn` parameter

- **Updated LoanManager class**:
  - Changed `default_payment_interval` → `default_payment_interval_turns` (default: 3 turns)
  - Updated all methods to use turn-based parameters:
    - `load_saved()`: Load turn-based values from database
    - `create_loan()`: Accept and use `current_turn` parameter
    - `make_payment()`: Accept and use `current_turn` parameter
    - `get_overdue_loans()`: Accept `current_turn` parameter
    - `_attempt_liquidation()`: Update to use turn-based payment calls
    - `schedule_payment_notification()`: Updated parameter names (kept for compatibility)

### 3. **tlog.py** - Transaction Log / Database
- **Updated Loans table schema**:
  - `payment_interval INTEGER` → `payment_interval_turns INTEGER`
  - `created_at REAL` → `created_at_turn INTEGER`
  - `next_payment_due REAL` → `next_payment_due_turn INTEGER`
- **Updated database methods**:
  - `create_loan()`: Parameters updated to use turn-based values
  - `update_loan()`: Parameters updated for `next_payment_due_turn`

### 4. **templates/home.html.jinja** - Home Page UI
- **Added Game Status section** (visible to all users):
  - Displays current turn prominently: `<p><strong>Current Turn: {{ current_turn }}</strong></p>`
  - Shows "Increment Turn" button for bankers only
- **Removed Payment Interval settings**: Deleted the banker-only form for updating payment intervals in seconds
- **Button styling**: Styled the increment turn button with green background

### 5. **templates/individual_loan.html.jinja** - Loan Details Page
- **Updated loan display**:
  - Changed "Payment Interval: X seconds" → "Payment Interval: X turns"
  - Changed "Next Payment Due: [timestamp]" → "Next Payment Due: Turn [number]"
  - Updated `is_overdue` property calls to pass `current_turn` parameter

### 6. **templates/loans.html.jinja** - Loans List Page
- **Updated is_overdue check**: Changed `loan.is_overdue` to `loan.is_overdue(current_turn)`

## How It Works

### Turn Mechanics
- Banker manually increments the turn counter by clicking "Increment Turn" on the home page
- Each loan has a `next_payment_due_turn` value that indicates when payment is due
- When current turn reaches or exceeds a loan's `next_payment_due_turn`, the loan is marked as overdue
- Payment intervals are now specified in turns (e.g., 3 means payment is due every 3 turns)

### Payment Intervals
- Default payment interval: 3 turns
- Customizable when creating loans (banker can set specific intervals)
- Next payment due automatically updates when a payment is made: `next_payment_due_turn = current_turn + payment_interval_turns`

### Database Persistence
- Loans with turn-based values are stored in the SQLite database
- Old timestamp-based data is no longer used
- New loans created will use turn-based intervals

## Backward Compatibility
- The `payment_timers` dictionary in LoanManager is maintained for future use but is not required for turn-based mechanics
- The `schedule_payment_notification()` method is kept for compatibility but now works with turns instead of seconds

## Example Usage

**Creating a Loan:**
```python
managed_loans.create_loan(
    borrower_id="player1",
    amount=500,
    payment_interval_turns=3,  # Payment due every 3 turns
    current_turn=game_state['current_turn']
)
```

**Making a Payment:**
```python
managed_loans.make_payment(
    loan_id="loan123",
    amount=50,
    current_turn=game_state['current_turn']
)
```

**Checking Overdue Loans:**
```python
overdue = managed_loans.get_overdue_loans(game_state['current_turn'])
```
