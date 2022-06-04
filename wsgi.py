from flask import Flask, render_template, request, Response, stream_with_context, redirect
from markupsafe import escape
import random

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

app = Flask(__name__)

def urlify(id, reverse=False):
    replace_chars = (
        ('?', '&question'),
        ('/', '&slash'),
        ('\\', '&backslash'),
        ('@', '&at'),
        ('^', '&caret'),
        ('*', '&glob'),
        ('#', '&hash'),
        ('(', '&pareno'),
        (')', '&parenc'),
        ('|', '&pipe'),
        ('`', '&backtick'),
        ('~', '&tilde'),
        ('[', '&bracko'),
        (']', '&brackc'),
        ('{', '&braceo'),
        ('}', '&bracec'),
        ('<', '&lt'),
        ('>', '&gt'),
        ('\'', '&sinquot'),
        ('"', '&quot'),
        ('%', '&percent')
    )
    for normal_char, url_char in replace_chars:
        if reverse:
            id = id.replace(url_char, normal_char)
        else:
            id = id.replace(normal_char, url_char)
    return id

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

@app.route(f'/{URLS["Accounts"]}/', methods=['GET', 'POST'])
def accounts_main_page():
    managed_accs.sync()
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
    managed_accs.sync()
    id = urlify(id, reverse=True)
    print(id)
    target_account = managed_accs.query(id)
    if target_account == 'Account does not exist.':
        return render_template('no_existing_account.html.jinja', urls=URLS, id=id)
    # Check for money transferring
    info = post_transfer(request.form)
    if 'withdraw-amount' in request.form:
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

@app.route('/bruh')
def bruh():
    @stream_with_context
    def poll_updates():
        while True:
            managed_accs.sync_event.wait()
            yield 'data: {"sync": true}\n\n'
            managed_accs.sync()
    return Response(poll_updates(), mimetype='text/event-stream')


if __name__ == 'wsgi':
    managed_accs = AccountManager()
    print('Server is ready!')

if __name__ == '__main__':
    print('Do not run this file directly with the Python interpreter. Use "flask run" instead.')
