from flask import Flask, render_template, request
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

@app.route('/')
def home_page():
    return render_template('home.html.jinja', urls=URLS)

@app.route(f'/{URLS["Accounts"]}/', methods=['GET', 'POST'])
def accounts_main_page():
    # Do account query as applicable
    if 'account-lookup-query' in request.form:
        query = request.form['account-lookup-query']
    else:
        query = ''
    lookup = managed_accs.search(query)
    num_results = len(lookup)
    return render_template('accounts.html.jinja', urls=URLS, lookup=lookup, query=query, num_results=num_results)

@app.route(f'/{URLS["Accounts"]}/<id>')
def individual_account_page(id):
    return str(managed_accs.query(id))

@app.route(f'/{URLS["Transfer"]}')
@app.route(f'/{URLS["Change Cash"]}')
@app.route(f'/{URLS["Properties"]}')
@app.route(f'/{URLS["Investments"]}')
@app.route(f'/{URLS["Auctions"]}')
@app.route(f'/{URLS["Help"]}')
def placeholder_page():
    return render_template('sidebar.html.jinja', urls=URLS)


if __name__ == 'wsgi':
    managed_accs = AccountManager()
    managed_accs.new('id_num', 'card_holder')
    managed_accs.new('asdf', 'Carson')
    for i in range(100):
        managed_accs.new(str(random.randint(0,1000000000000000000000000000)), f'{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}')
    print('Server is ready!')

if __name__ == '__main__':
    print('Do not run this file directly with the Python interpreter. Use "flask run" instead.')
