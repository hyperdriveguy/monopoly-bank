import secrets
from urllib.parse import urljoin, urlparse

from flask import (Flask, Response, redirect, render_template, request,
                   stream_with_context, flash, get_flashed_messages, abort, url_for)
from flask_login import (LoginManager, login_required, login_user,
                         logout_user, current_user)
from markupsafe import escape

from account_store import AccountManager

from property_manger import PropertyManager

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
    user_realname = current_user.name if not current_user.is_anonymous else 'Log in'
    user_id = current_user.ident if not current_user.is_anonymous else ''
    is_banker = current_user.banker if not current_user.is_anonymous else False
    return render_template(template_path, logged_in=(not current_user.is_anonymous), user_id=user_id, user_realname=user_realname, is_banker=is_banker, **kwargs)


if __name__ == '__main__':
    app = Flask(__name__)

    # Invalidate sessions when server restarts
    # This avoids permanent key storage
    app.secret_key = secrets.token_hex()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    managed_props = PropertyManager('property_set.json')

    managed_accs = AccountManager(managed_props)


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


    @app.route('/')
    def home_page():
        if not current_user.is_anonymous:
            flash(current_user)
        return render_generic('home.html.jinja')


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

        return render_generic('individual_account.html.jinja', acc=target_account, account_log=account_log)

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


    @app.route('/properties/<prop_name>')
    def individual_property_page(prop_name):
        return render_generic('individual_property.html.jinja', prop=managed_props.properties[prop_name])


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
    @app.route('/auctions')
    @app.route('/help')
    def placeholder_page():
        return render_generic('sidebar.html.jinja')


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


if __name__ == 'wsgi':
    print('Avoid running with flask run as it doesn\'t allow the db to close.')
