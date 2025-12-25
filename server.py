import secrets
from urllib.parse import urljoin, urlparse

from flask import (Flask, Response, redirect, render_template, request,
                   stream_with_context, flash, get_flashed_messages, abort, url_for)
from flask_login import (LoginManager, login_required, login_user,
                         logout_user, current_user)
from markupsafe import escape

from account_store import AccountManager

from property_manger import PropertyManager

from auction_store import AuctionManager

from loan_store import LoanManager

# TODO: Remove this
TEMP_PASSWORD = 'temp'

def urlify(ident, reverse=False):
    """
    Allow for a reversible "URLification" of characters.
    """
    replace_chars = (
        ('?', '&a'),
        ('/', '&b'),
        ('\\', '&c'),
        ('@', '&d'),
        ('^', '&e'),
        ('*', '&f'),
        ('#', '&g'),
        ('(', '&h'),
        (')', '&i'),
        ('|', '&j'),
        ('`', '&k'),
        ('~', '&l'),
        ('[', '&m'),
        (']', '&n'),
        ('{', '&o'),
        ('}', '&p'),
        ('<', '&q'),
        ('>', '&r'),
        ('\'', '&s'),
        ('"', '&t'),
        ('%', '&u'),
        ('&', '&v')
    )
    for normal_char, url_char in replace_chars:
        if reverse:
            ident = ident.replace(url_char, normal_char)
        else:
            ident = ident.replace(normal_char, url_char)
    return ident


def is_safe_url(target):
    """
    Ensure the target URL is a valid and safe URL.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


def login_redirect(username, next_url):
    """
    Preform the user login and redirect to the next URL.
    """
    login_user(username)
    flash('Logged in successfully.')
    # is_safe_url should check if the url is safe for redirects.
    # See http://flask.pocoo.org/snippets/62/ for an example.
    if not is_safe_url(next_url):
        return abort(400)
    return redirect(next_url or '/')

def render_generic(template_path, **kwargs):
    """
    Render a "generic" Jinja template that has common key arguments.
    """
    from loan_store import Loan
    # Update the Loan class with current turn for is_overdue property
    Loan._current_turn = game_state['current_turn']
    
    user_realname = current_user.name if not current_user.is_anonymous else 'Log in'
    user_id = current_user.ident if not current_user.is_anonymous else ''
    is_banker = current_user.banker if not current_user.is_anonymous else False
    return render_template(template_path, logged_in=(not current_user.is_anonymous), user_id=user_id, user_realname=user_realname, is_banker=is_banker, current_turn=game_state['current_turn'], **kwargs)


if __name__ == '__main__':
    app = Flask(__name__)

    # Invalidate sessions when server restarts
    # This avoids permanent key storage
    app.secret_key = secrets.token_hex()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    # Global game state for turn-based mechanics
    game_state = {'current_turn': 0}

    managed_props = PropertyManager('property_set.json')

    managed_accs = AccountManager(managed_props)

    managed_auctions = AuctionManager(managed_accs.tlog_connection)

    managed_loans = LoanManager(managed_accs.tlog_connection, managed_accs)

    # Load current turn from database
    saved_turn = managed_accs.tlog_connection.get_game_state('current_turn')
    if saved_turn is not None:
        game_state['current_turn'] = saved_turn

    # Global mortgage interest rate (as decimal, e.g., 0.10 = 10%)
    mortgage_interest_rate = {'value': 0.10}


    @login_manager.user_loader
    def load_user(ident):
        """
        This is required for Flask-Login.
        """
        user = managed_accs.query(ident)
        if user == 'Account does not exist.':
            return None
        return user


    def post_transfer(args):
        """
        Common code for transferring between accounts.
        """
        info = ''
        if 'transfer-amount' in args:
            account1 = args['account-1-id']
            account2 = args['account-2-id']
            amount = args['transfer-amount']
            direction = args['transfer-direction']
            if direction == 'primary':
                info = managed_accs.transfer(account1, account2, int(amount))
            else:
                info = managed_accs.transfer(account2, account1, int(amount))
        return info


    # BEGIN TARGET PAGE ROUTES
    # All functions below tie to specific site routes


    @app.route('/', methods=['GET', 'POST'])
    def home_page():
        if not current_user.is_anonymous:
            flash(current_user)
            # Banker can update mortgage interest rate
            if current_user.banker and request.method == 'POST':
                if 'mortgage-interest' in request.form:
                    new_rate = float(request.form['mortgage-interest']) / 100.0
                    mortgage_interest_rate['value'] = new_rate
                    flash(f'Mortgage interest rate updated to {int(new_rate * 100)}%')
                # Banker can update loan interest rate
                elif 'loan-interest' in request.form:
                    new_rate = float(request.form['loan-interest']) / 100.0
                    managed_loans.loan_interest_rate = new_rate
                    flash(f'Loan interest rate updated to {int(new_rate * 100)}%')
                # Banker can update minimum credit score
                elif 'min-credit-score' in request.form:
                    managed_loans.min_credit_score = int(request.form['min-credit-score'])
                    flash(f'Minimum credit score updated to ${managed_loans.min_credit_score}')
                # Banker can update maximum loan amount
                elif 'max-loan-amount' in request.form:
                    managed_loans.max_loan_amount = int(request.form['max-loan-amount'])
                    flash(f'Maximum loan amount updated to ${managed_loans.max_loan_amount}')
                # Banker can increment turn
                elif 'increment-turn' in request.form:
                    game_state['current_turn'] += 1
                    managed_accs.tlog_connection.set_game_state('current_turn', game_state['current_turn'])
                    
                    # Update Loan class to use new turn immediately for late fee calculation
                    from loan_store import Loan
                    Loan._current_turn = game_state['current_turn']
                    
                    # Apply late fees to overdue loans
                    late_fees_charged = managed_loans.apply_late_fees_all()
                    if late_fees_charged:
                        fee_messages = [f"{borrower}: ${amount}" for borrower, amount in late_fees_charged.items()]
                        flash(f'Turn incremented to {game_state["current_turn"]}. Late fees applied: {", ".join(fee_messages)}')
                    else:
                        flash(f'Turn incremented to {game_state["current_turn"]}')
                # Banker can update compounding interval
                elif 'compounding-interval' in request.form:
                    managed_loans.compounding_interval_turns = int(request.form['compounding-interval'])
                    flash(f'Compounding interval updated to every {managed_loans.compounding_interval_turns} turns')
        return render_generic('home.html.jinja', 
                            mortgage_interest_rate=mortgage_interest_rate['value'],
                            loan_interest_rate=managed_loans.loan_interest_rate,
                            min_credit_score=managed_loans.min_credit_score,
                            max_loan_amount=managed_loans.max_loan_amount,
                            compounding_interval_turns=managed_loans.compounding_interval_turns)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        failed_login = False
        if 'login-username' in request.form:
            user = managed_accs.query(request.form['login-username'])
            print(f"{request.form['login-username']}: {request.form['login-password']}")
            if user == 'Account does not exist.':
                flash(user)
            elif user.is_authenticated(request.form['login-password']):
                # Login and validate the user.
                # user should be an instance of your `User` class
                return login_redirect(user, request.args.get('next'))

            else:
                flash('Incorrect password')

        elif 'signup-username' in request.form:
            new_username = request.form['signup-username']
            new_realname = request.form['signup-realname']
            new_password = request.form['signup-password']
            if managed_accs.new(new_username, new_realname, new_password):
                user = managed_accs.query(new_username)
                return login_redirect(user, request.args.get('next'))
            else:
                flash('Username for account already exists.')

        return render_generic('login.html.jinja')


    @app.route('/logout', methods=['GET', 'POST'])
    @login_required
    def logout():
        logout_user()
        flash('Succesfully logged out')
        return redirect('/')


    @app.route('/accounts/', methods=['GET', 'POST'])
    def accounts_main_page():
        managed_accs.recieved_update()
        # Show all accounts by default
        lookup = sorted(managed_accs.accounts_storage.values(), key=lambda a: a.name)
        query = ''
        # Check if new account was created
        if 'new-acc-name' in request.form:
            if current_user.is_anonymous or not current_user.banker:
                flash('Operation only allowed for banker.')
                return redirect(url_for('accounts_main_page'))
            new_id, new_name, new_cash = (
                request.form['new-acc-id'],
                request.form['new-acc-name'].title(),
                int(request.form['new-acc-cash'])
            )
            if managed_accs.new(new_id, new_name, TEMP_PASSWORD, new_cash):
                flash('Created new account.')
                flash(f'Temporary password for new user {new_id}: "{TEMP_PASSWORD}"')
            else:
                flash('Could not create account. Does an ID for that account already exist?')
            if 'account-redirect' in request.form:
                return redirect(url_for('individual_account_page', ident=request.form["account-redirect"]))
            lookup = sorted(managed_accs.accounts_storage.values(), key=lambda a: a.name)
        # Check if account was deleted
        elif 'del-acc-id' in request.form:
            if current_user.is_anonymous or not current_user.banker:
                flash('Operation only allowed for banker.')
                return redirect(url_for('accounts_main_page'))
            managed_accs.delete(request.form['del-acc-id'])
            flash(f'Deleted account for ID {request.form["del-acc-id"]}.')
            # This is required so the deleted account doesn't show on the page
            lookup = sorted(managed_accs.accounts_storage.values(), key=lambda a: a.name)
        # Do account query as applicable
        elif 'account-lookup-query' in request.form:
            query = request.form['account-lookup-query']
            lookup = sorted(managed_accs.search(query).values(), key=lambda a: a.name)
            flash(f'{len(lookup)} result{"s" if len(lookup) > 1 else ""} for search "{query}".')

        return render_generic('accounts.html.jinja', make_url=urlify, num_accs=len(managed_accs.accounts_storage), lookup=lookup)

    @app.route('/accounts/<ident>', methods=['GET', 'POST'])
    def individual_account_page(ident):
        managed_accs.recieved_update()
        ident = urlify(ident, reverse=True)
        target_account = managed_accs.query(ident)
        if target_account == 'Account does not exist.':
            return render_generic('no_existing_account.html.jinja', id=ident) if not current_user.is_anonymous and current_user.banker else abort(404)
        account_log = target_account.get_transactions()
        # Check for money transferring
        if 'transfer-amount' in request.form:
            if current_user.is_anonymous or not current_user.banker:
                abort(403)
            flash(post_transfer(request.form))
        elif 'withdraw-amount' in request.form:
            if current_user.is_anonymous or not current_user.banker:
                abort(403)
            amount = target_account.withdraw(int(request.form['withdraw-amount']))
            flash(f'Withdrew ${amount} from account.')
        elif 'deposit-amount' in request.form:
            if current_user.is_anonymous or not current_user.banker:
                abort(403)
            amount = target_account.deposit(int(request.form['deposit-amount']))
            flash(f'Deposited ${amount} into account.')

        # Get loans for this account
        account_loans = managed_loans.get_loans_by_borrower(ident)

        return render_generic('individual_account.html.jinja', acc=target_account, account_log=account_log, loans=account_loans)

    @app.route('/change-cash', methods=['GET', 'POST'])
    @login_required
    def change_cash():
        if not current_user.banker:
            abort(403)
        if 'id-card' in request.form:
            return redirect(url_for('individual_account_page', ident=request.form["id-card"]))
        return render_generic('change_cash.html.jinja')

    @app.route('/transfer', methods=['GET', 'POST'])
    @login_required
    def transfer():
        if not current_user.banker:
            abort(403)
        flash(post_transfer(request.form))
        return render_generic('transfer.html.jinja')


    @app.route('/properties/')
    def properties_page():
        return render_generic('properties.html.jinja', property_list=managed_props.all_properties)


    @app.route('/properties/<prop_name>', methods=['GET', 'POST'])
    def individual_property_page(prop_name):
        prop = managed_props.properties[prop_name]
        
        # Handle POST requests
        if request.method == 'POST':
            # Pay rent (any logged-in player)
            if 'action' in request.form and request.form['action'] == 'pay-rent':
                if current_user.is_anonymous:
                    abort(403)
                if not prop.owner or prop.owner == current_user.ident:
                    flash('Cannot pay rent to yourself or the bank.')
                else:
                    result = managed_accs.transfer(current_user.ident, prop.owner, prop.rent)
                    flash(result)
            # Mortgage/Unmortgage (property owner only)
            elif 'action' in request.form and request.form['action'] == 'mortgage':
                if current_user.is_anonymous:
                    abort(403)
                if prop.owner != current_user.ident:
                    abort(403)
                result = managed_accs.mortgage_property(prop.owner, prop)
                flash(result)
            elif 'action' in request.form and request.form['action'] == 'unmortgage':
                if current_user.is_anonymous:
                    abort(403)
                if prop.owner != current_user.ident:
                    abort(403)
                # Use global interest rate set by banker
                result = managed_accs.unmortgage_property(prop.owner, prop, mortgage_interest_rate['value'])
                flash(result)
            # Create auction (property owner only)
            elif 'action' in request.form and request.form['action'] == 'create-auction':
                if current_user.is_anonymous:
                    abort(403)
                if prop.owner != current_user.ident:
                    abort(403)
                
                try:
                    starting_bid = int(request.form.get('starting-bid', prop.costs['property'] // 2))
                    success, result = managed_auctions.create_auction(prop.name, current_user.ident, starting_bid)
                    if success:
                        flash(f'Auction created for {prop.name} with starting bid ${starting_bid}.')
                        return redirect(url_for('individual_auction_page', auction_id=result))
                    else:
                        flash(result)
                except ValueError:
                    flash('Invalid starting bid amount.')
            # Banker operations
            elif current_user.is_anonymous or not current_user.banker:
                abort(403)
            # Sell property to player
            elif 'buyer-id' in request.form:
                buyer_id = request.form['buyer-id']
                result = managed_accs.sell_property(buyer_id, prop)
                flash(result)
            # Buy back property from player
            elif 'action' in request.form and request.form['action'] == 'buy-back':
                if prop.owner:
                    # Get fraction from form (default 50%)
                    fraction = 0.5
                    if 'fraction' in request.form:
                        fraction = float(request.form['fraction'])
                    elif 'custom-fraction' in request.form and request.form['custom-fraction']:
                        fraction = float(request.form['custom-fraction']) / 100.0
                    
                    result = managed_accs.buy_property(prop.owner, prop, fraction)
                    flash(result)
                else:
                    flash('Property is not owned by anyone.')
            # Add building (house or hotel)
            elif 'action' in request.form and request.form['action'] == 'add-building':
                # Check if owner has full color set before allowing building
                if not prop.owner_has_full_set(managed_props):
                    flash(f'Cannot add buildings to {prop.name}. Owner must have the full color set first.')
                elif prop.upgrade():
                    owner = managed_accs.query(prop.owner)
                    if owner != 'Account does not exist.':
                        # Withdraw building cost from owner
                        building_cost = prop.costs.get('houses', 0)
                        owner.withdraw(building_cost)
                        # Save property state to database
                        owner.update_property_state()
                        flash(f'Added building to {prop.name}. Now at: {prop.building_level}. Cost: ${building_cost}')
                    else:
                        flash(f'Added building to {prop.name}. Now at: {prop.building_level}')
                else:
                    flash(f'Cannot add building to {prop.name}. Already at maximum or not buildable.')
            # Remove building
            elif 'action' in request.form and request.form['action'] == 'remove-building':
                if prop.downgrade(managed_props):
                    owner = managed_accs.query(prop.owner)
                    if owner != 'Account does not exist.':
                        # Return half the building cost to owner
                        building_cost = prop.costs.get('houses', 0) // 2
                        owner.deposit(building_cost)
                        # Save property state to database
                        owner.update_property_state()
                        flash(f'Removed building from {prop.name}. Now at: {prop.building_level}. Refund: ${building_cost}')
                    else:
                        flash(f'Removed building from {prop.name}. Now at: {prop.building_level}')
                else:
                    flash(f'Cannot remove building from {prop.name}. No buildings to remove.')
        
        return render_generic('individual_property.html.jinja', prop=prop, prop_manager=managed_props, mortgage_interest_rate=mortgage_interest_rate['value'])


    @app.route('/properties/<prop_name>/api', methods=['POST'])
    def individual_property_api(prop_name):
        prop_obj = managed_props.properties[prop_name]
        if not current_user.is_anonymous:
            # Banker operations
            if current_user.banker and 'new owner' in request.json:
                acc_obj = managed_accs.query(request.json['new owner'])
                acc_obj.withdraw(prop_obj.costs['property'])
                acc_obj.add_property(prop_obj)
                return {'response': f'Made {request.json["new owner"]} new owner of {prop_name}'}
            # Property owner operations
            if current_user.ident == managed_props.properties[prop_name].owner:
                # TODO: add property owner operations
                pass
            else:
                return {'response': 'No valid request made by non-anonymous user'}

        user_name = str(current_user.ident if not current_user.is_anonymous else '')
        return {'property': managed_props.properties[prop_name].json, 'request': request.json, 'user': user_name}


    # TODO: Finish pages
    @app.route('/investments')
    @app.route('/help')
    def placeholder_page():
        return render_generic('sidebar.html.jinja')


    @app.route('/loans/')
    def loans_page():
        """
        Display all loans.
        Bankers see all loans, players see only their own.
        """
        if current_user.is_anonymous:
            abort(403)
        
        if current_user.banker:
            # Banker sees all loans
            all_loans = managed_loans.get_all_loans()
            overdue_loans = managed_loans.get_overdue_loans()
        else:
            # Player sees only their own loans
            all_loans = managed_loans.get_loans_by_borrower(current_user.ident)
            overdue_loans = [loan for loan in all_loans if loan.is_overdue]
        
        return render_generic('loans.html.jinja', 
                            loans=all_loans, 
                            overdue_loans=overdue_loans,
                            loan_interest_rate=managed_loans.loan_interest_rate)


    @app.route('/loans/apply', methods=['GET', 'POST'])
    def loan_application():
        """
        Handle loan applications.
        """
        if current_user.is_anonymous:
            abort(403)
        
        # Check if player has defaulted loans (unless they're a banker)
        if not current_user.banker and managed_loans.has_defaulted_loans(current_user.ident):
            flash('Cannot apply for loans while you have defaulted loans. Please resolve them first.')
            return redirect(url_for('loans_page'))
        
        if request.method == 'POST':
            try:
                requested_amount = int(request.form['loan-amount'])
                payment_interval = None
                loan_term_periods = None
                interest_compounds = True  # Default to compound interest
                
                # Banker can override payment interval, loan term, and interest type
                if current_user.banker and 'payment-interval' in request.form:
                    payment_interval = int(request.form['payment-interval'])
                
                if current_user.banker and 'loan-term' in request.form:
                    loan_term_periods = int(request.form['loan-term'])
                
                # Banker can choose simple interest (compound is default)
                if current_user.banker and 'simple-interest' in request.form:
                    interest_compounds = False
                
                # Get borrower ID (banker can apply for others)
                borrower_id = current_user.ident
                approved_by_banker = False
                
                if current_user.banker:
                    # Check if borrower-id is provided and not empty
                    if 'borrower-id' in request.form and request.form['borrower-id'].strip():
                        borrower_id = request.form['borrower-id'].strip()
                    
                    # Bankers always bypass credit checks (can override if needed)
                    approved_by_banker = True
                
                # Create loan
                success, result = managed_loans.create_loan(
                    borrower_id, 
                    requested_amount, 
                    payment_interval,
                    approved_by_banker,
                    game_state['current_turn'],
                    interest_compounds,
                    loan_term_periods
                )
                
                if success:
                    flash(f'Loan approved! Loan ID: {result}')
                    return redirect(url_for('individual_loan_page', loan_id=result))
                else:
                    flash(f'Loan denied: {result}')
            except ValueError:
                flash('Invalid loan amount.')
        
        # Calculate eligibility for GET request
        eligible = False
        reason = ""
        max_amount = 0
        has_defaulted_loans = False
        typical_payment = 0
        
        if not current_user.is_anonymous:
            has_defaulted_loans = managed_loans.has_defaulted_loans(current_user.ident)
            
            if current_user.banker:
                # Bankers can borrow up to the system maximum (they can bypass credit checks)
                max_amount = managed_loans.max_loan_amount
                eligible = True
                reason = "Banker - can bypass credit checks"
            elif not has_defaulted_loans:
                # Regular players are subject to credit checks
                eligible, reason, max_amount = managed_loans.check_loan_eligibility(
                    current_user.ident
                )
            
            # Calculate typical payment for max amount if eligible
            if eligible and max_amount > 0:
                # Create a temporary loan to calculate typical payment
                from loan_store import Loan, LoanStatus
                temp_loan = Loan(
                    loan_id="temp",
                    borrower_id=current_user.ident,
                    principal=max_amount,
                    interest_rate=managed_loans.loan_interest_rate,
                    payment_interval_turns=managed_loans.default_payment_interval_turns,
                    created_at_turn=game_state['current_turn'],
                    status=LoanStatus.ACTIVE,
                    interest_compounds=True,
                    compounding_interval_turns=managed_loans.compounding_interval_turns,
                    loan_term_periods=3
                )
                typical_payment = temp_loan.typical_payment
        
        return render_generic('loan_application.html.jinja',
                            eligible=eligible,
                            reason=reason,
                            max_amount=max_amount,
                            has_defaulted_loans=has_defaulted_loans,
                            loan_interest_rate=managed_loans.loan_interest_rate,
                            default_interval=managed_loans.default_payment_interval_turns,
                            default_loan_term=3,
                            typical_payment=typical_payment)


    @app.route('/loans/<loan_id>', methods=['GET', 'POST'])
    def individual_loan_page(loan_id):
        """
        Display and handle actions for a specific loan.
        """
        if current_user.is_anonymous:
            abort(403)
        
        loan = managed_loans.get_loan(loan_id)
        if not loan:
            flash('Loan not found.')
            return redirect(url_for('loans_page'))
        
        # Check authorization
        if not current_user.banker and loan.borrower_id != current_user.ident:
            abort(403)
        
        borrower = managed_accs.query(loan.borrower_id)
        
        if request.method == 'POST':
            # Make payment
            if 'payment-amount' in request.form:
                if current_user.banker or loan.borrower_id == current_user.ident:
                    try:
                        payment_amount = int(request.form['payment-amount'])
                        success, message = managed_loans.make_payment(loan_id, payment_amount, game_state['current_turn'])
                        flash(message)
                        
                        # Reload loan to get updated data
                        loan = managed_loans.get_loan(loan_id)
                    except ValueError:
                        flash('Invalid payment amount.')
                else:
                    abort(403)
            
            # Resolve defaulted loan (borrower can settle)
            elif 'action' in request.form and request.form['action'] == 'resolve-default':
                if loan.borrower_id != current_user.ident and not current_user.banker:
                    abort(403)
                
                if loan.status.value != 'defaulted':
                    flash('This loan is not in default status.')
                else:
                    try:
                        settlement_amount = int(request.form.get('settlement-amount', loan.remaining_balance))
                        
                        # Check if player has sufficient funds
                        if borrower.cash < settlement_amount:
                            flash(f'Insufficient funds. You have ${borrower.cash}, need ${settlement_amount}.')
                        else:
                            # Process settlement payment
                            success, message = managed_loans.make_payment(loan_id, settlement_amount, game_state['current_turn'])
                            flash(message)
                            
                            # If loan is paid off, forgive the default and notify
                            updated_loan = managed_loans.get_loan(loan_id)
                            if updated_loan.status.value == 'paid_off':
                                forgive_success, forgive_message = managed_loans.forgive_default(loan_id)
                                if forgive_success:
                                    flash(forgive_message)
                                flash('🎉 Congratulations! Your loan has been fully paid off and your default has been resolved.')
                            
                            loan = managed_loans.get_loan(loan_id)
                    except ValueError:
                        flash('Invalid settlement amount.')
            
            # Default loan (banker only)
            elif 'action' in request.form and request.form['action'] == 'default':
                if not current_user.banker:
                    abort(403)
                success, message = managed_loans.default_loan(loan_id)
                flash(message)
                loan = managed_loans.get_loan(loan_id)
            
            # Send payment notification (banker only)
            elif 'action' in request.form and request.form['action'] == 'notify':
                if not current_user.banker:
                    abort(403)
                success, message = managed_loans.send_payment_notification(loan_id)
                flash(message)
            
            # Schedule payment notification (banker only)
            elif 'action' in request.form and request.form['action'] == 'schedule':
                if not current_user.banker:
                    abort(403)
                delay = None
                if 'delay-seconds' in request.form and request.form['delay-seconds']:
                    delay = int(request.form['delay-seconds'])
                success, message = managed_loans.schedule_payment_notification(loan_id, delay)
                flash(message)
            
            # Cancel scheduled notification (banker only)
            elif 'action' in request.form and request.form['action'] == 'cancel-notification':
                if not current_user.banker:
                    abort(403)
                success, message = managed_loans.cancel_payment_notification(loan_id)
                flash(message)
            
            # Erase loan debt (banker only - complete forgiveness)
            elif 'action' in request.form and request.form['action'] == 'erase':
                if not current_user.banker:
                    abort(403)
                success, message = managed_loans.erase_loan(loan_id)
                flash(message)
                if success:
                    return redirect(url_for('loans_page'))
        
        return render_generic('individual_loan.html.jinja', 
                            loan=loan, 
                            borrower=borrower,
                            has_scheduled_notification=(loan_id in managed_loans.payment_timers))


    @app.route('/auctions/')
    def auctions_page():
        """
        Display all active auctions.
        """
        active_auctions = managed_auctions.get_active_auctions()
        # Enrich auction data with property information
        auction_data = []
        for auction in active_auctions:
            prop = managed_props.properties.get(auction.property_name)
            if prop:
                auction_data.append({
                    'auction': auction,
                    'property': prop
                })
        
        return render_generic('auctions.html.jinja', auctions=auction_data)


    @app.route('/auctions/<auction_id>', methods=['GET', 'POST'])
    def individual_auction_page(auction_id):
        """
        Display and handle actions for a specific auction.
        """
        auction = managed_auctions.get_auction(auction_id)
        if not auction:
            flash('Auction not found.')
            return redirect(url_for('auctions_page'))
        
        prop = managed_props.properties.get(auction.property_name)
        if not prop:
            flash('Property not found.')
            return redirect(url_for('auctions_page'))
        
        if request.method == 'POST':
            # Place a bid
            if 'bid-amount' in request.form:
                if current_user.is_anonymous:
                    abort(403)
                
                try:
                    bid_amount = int(request.form['bid-amount'])
                    success, message = managed_auctions.place_bid(auction_id, current_user.ident, bid_amount)
                    flash(message)
                except ValueError:
                    flash('Invalid bid amount.')
            
            # Complete auction (seller or banker only)
            elif 'action' in request.form and request.form['action'] == 'complete':
                if current_user.is_anonymous:
                    abort(403)
                if auction.seller_id != current_user.ident and not current_user.banker:
                    abort(403)
                
                winner_id, winning_bid = managed_auctions.complete_auction(auction_id)
                
                if winner_id:
                    # Transfer property from seller to winner
                    # Remove property from seller
                    seller = managed_accs.query(auction.seller_id)
                    if seller != 'Account does not exist.':
                        seller.remove_property(prop)
                    
                    # Transfer money from winner to seller
                    result = managed_accs.transfer(winner_id, auction.seller_id, winning_bid)
                    flash(result)
                    
                    # Give property to winner
                    winner = managed_accs.query(winner_id)
                    if winner != 'Account does not exist.':
                        winner.add_property(prop)
                    
                    flash(f'Auction completed! {prop.name} sold to {winner_id} for ${winning_bid}.')
                else:
                    flash('Auction completed with no bids.')
                
                return redirect(url_for('auctions_page'))
            
            # Cancel auction (seller only, no bids)
            elif 'action' in request.form and request.form['action'] == 'cancel':
                if current_user.is_anonymous:
                    abort(403)
                if auction.seller_id != current_user.ident and not current_user.banker:
                    abort(403)
                
                success, message = managed_auctions.cancel_auction(auction_id, current_user.ident)
                flash(message)
                if success:
                    return redirect(url_for('auctions_page'))
        
        return render_generic('individual_auction.html.jinja', auction=auction, prop=prop)


    # Error handlers
    @app.errorhandler(404)
    def not_found_page(e):
        return render_generic('sidebar.html.jinja'), 404

    @app.errorhandler(403)
    def unauthorized_page(e):
        return render_generic('unauthorized_access.html.jinja'), 403


    # Event stream that triggers on any change
    # TODO: Make this trigger with more specific changes
    @app.route('/bruh')
    def bruh():
        @stream_with_context
        def signal_updates():
            while True:
                managed_accs.server_update_signal.wait()
                print("Sending update...")
                yield 'data: {"sync": true}\n\n'
                managed_accs.recieved_update()
        return Response(signal_updates(), mimetype='text/event-stream')


    # Run the application until stopped or encountering an error
    try:
        app.run()
    # Clean up the application and close the TLog
    finally:
        for m in managed_accs.cleanup():
            print(m)
        for m in managed_auctions.cleanup():
            print(m)
        for m in managed_loans.cleanup():
            print(m)


if __name__ == 'wsgi':
    print('Avoid running with flask run as it doesn\'t allow the db to close.')
