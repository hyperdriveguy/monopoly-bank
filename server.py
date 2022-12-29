import secrets
from urllib.parse import urljoin, urlparse

from flask import (Flask, Response, redirect, render_template, request,
                   stream_with_context, flash, abort, url_for)
from flask_login import LoginManager, login_required, login_user
from markupsafe import escape

from account_store import AccountManager

URLS = {
    'Accounts': 'accounts',
    'Transfer': 'transfer',
    'Change Cash': 'change-cash',
    'Properties': 'properties',
    'Investments': 'investments',
    'Auctions': 'auctions',
    'Help': 'help'
}

def urlify(ident, reverse=False):
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
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc

if __name__ == '__main__':
    app = Flask(__name__)

    # Invalidate sessions when server restarts
    # This avoids permanent key storage
    app.secret_key = secrets.token_hex()

    login_manager = LoginManager()
    login_manager.init_app(app)

    managed_accs = AccountManager()

    @login_manager.user_loader
    def load_user(ident):
        user = managed_accs.query(ident)
        if user == 'Account does not exist.':
            return None
        return user


    def post_transfer(args):
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


    @app.route('/')
    def home_page():
        return render_template('home.html.jinja', urls=URLS)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # Here we use a class of some kind to represent and validate our
        # client-side form data. For example, WTForms is a library that will
        # handle this for us, and we use a custom LoginForm to validate.
        # form = LoginForm()
        failed_login = False
        if 'username' in request.form:
            user = managed_accs.username_exists(request.form['username'])
            if user is not None and user.is_authenticated(request.form['password']):
                # Login and validate the user.
                # user should be an instance of your `User` class
                login_user(user)

                flash('Logged in successfully.')

                next = request.args.get('next')
                # is_safe_url should check if the url is safe for redirects.
                # See http://flask.pocoo.org/snippets/62/ for an example.
                if not is_safe_url(next):
                    return abort(400)

                return redirect(next or url_for('index'))
        return render_template('login.html.jinja', urls=URLS)


    @app.route(f'/{URLS["Accounts"]}/', methods=['GET', 'POST'])
    #@login_required
    def accounts_main_page():
        managed_accs.recieved_update()
        # Show all accounts by default
        lookup = sorted(managed_accs.card_numbers.values(), key=lambda a: a.name)
        query = ''
        info = ''
        # Check if new account was created
        if 'new-acc-name' in request.form:
            new_id, new_name, new_cash = (
                request.form['new-acc-id'],
                request.form['new-acc-name'].title(),
                int(request.form['new-acc-cash'])
            )
            info = managed_accs.new(new_id, new_name, new_cash)
            if 'account-redirect' in request.form:
                return redirect(f'/{URLS["Accounts"]}/{urlify(request.form["account-redirect"])}')
            lookup = sorted(managed_accs.card_numbers.values(), key=lambda a: a.name)
        # Check if account was deleted
        elif 'del-acc-id' in request.form:
            managed_accs.delete(request.form['del-acc-id'])
            info = f'Deleted account for ID {request.form["del-acc-id"]}.'
            # This is required so the deleted account doesn't show on the page
            lookup = sorted(managed_accs.card_numbers.values(), key=lambda a: a.name)
        # Do account query as applicable
        elif 'account-lookup-query' in request.form:
            query = request.form['account-lookup-query']
            lookup = sorted(managed_accs.search(query).values(), key=lambda a: a.name)
            info = f'{len(lookup)} result{"s" if len(lookup) > 1 else ""} for search "{query}".'

        return render_template('accounts.html.jinja', urls=URLS, make_url=urlify, num_accs=len(managed_accs.card_numbers), lookup=lookup, info=info)

    @app.route(f'/{URLS["Accounts"]}/<id>', methods=['GET', 'POST'])
    def individual_account_page(id):
        managed_accs.recieved_update()
        id = urlify(id, reverse=True)
        target_account = managed_accs.query(id)
        if target_account == 'Account does not exist.':
            return render_template('no_existing_account.html.jinja', urls=URLS, id=id)
        target_account.get_transactions()
        info = ''
        # Check for money transferring
        if 'transfer-amount' in request.form:
            info = post_transfer(request.form)
        elif 'withdraw-amount' in request.form:
            amount = target_account.withdraw(int(request.form['withdraw-amount']))
            info = f'Withdrew ${amount} from account.'
        elif 'deposit-amount' in request.form:
            amount = target_account.deposit(int(request.form['deposit-amount']))
            info = f'Deposited ${amount} into account.'

        return render_template('individual_account.html.jinja', urls=URLS, acc=target_account, info=info)

    @app.route(f'/{URLS["Change Cash"]}', methods=['GET', 'POST'])
    def change_cash():
        if 'id-card' in request.form:
            return redirect(f'/{URLS["Accounts"]}/{urlify(request.form["id-card"])}')
        return render_template('change_cash.html.jinja', urls=URLS)

    @app.route(f'/{URLS["Transfer"]}', methods=['GET', 'POST'])
    def transfer():
        info = post_transfer(request.form)
        return render_template('transfer.html.jinja', urls=URLS, info=info)

    @app.route(f'/{URLS["Properties"]}')
    @app.route(f'/{URLS["Investments"]}')
    @app.route(f'/{URLS["Auctions"]}')
    @app.route(f'/{URLS["Help"]}')
    def placeholder_page():
        return render_template('sidebar.html.jinja', urls=URLS)

    @app.route('/nuke')
    def nuke():
        return managed_accs.nuke_accounts()

    @app.route('/random')
    def random_accs():
        managed_accs.make_random_accs()
        return 'AAAAAAAHAHHAHHAHAHHH'

    @app.route('/bruh')
    def bruh():
        @stream_with_context
        def signal_updates():
            while True:
                managed_accs.server_update_signal.wait()
                yield 'data: {"sync": true}\n\n'
                managed_accs.recieved_update()
        return Response(signal_updates(), mimetype='text/event-stream')
    try:
        app.run()
    finally:
        for m in managed_accs.cleanup():
            print(m)

if __name__ == 'wsgi':
    print('Avoid running with flask run as it doesn\'t allow the db to close.')
