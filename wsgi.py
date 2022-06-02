from flask import Flask, render_template
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

@app.route(f'/{URLS["Accounts"]}')
def account_main_page():
    return render_template('accounts.html.jinja', urls=URLS, accs=managed_accs)

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
    for _ in range(1000):
        managed_accs.new(str(random.randint(0,10000)), 'Another Carson')

if __name__ == '__main__':
    print('Do not run this file directly with the Python interpreter. Use "flask run" instead.')
