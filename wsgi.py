from flask import Flask, render_template
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

app = Flask(__name__)


@app.route('/')
def home_page():
    return render_template('home.html.jinja', urls=URLS)

@app.route(f'/{URLS["Accounts"]}')
@app.route(f'/{URLS["Transfer"]}')
@app.route(f'/{URLS["Change Cash"]}')
@app.route(f'/{URLS["Properties"]}')
@app.route(f'/{URLS["Investments"]}')
@app.route(f'/{URLS["Auctions"]}')
@app.route(f'/{URLS["Help"]}')
def placeholder_page():
    return render_template('sidebar.html.jinja', urls=URLS)
