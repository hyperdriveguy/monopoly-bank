from flask import Flask, render_template
from markupsafe import escape

from account_store import AccountManager

app = Flask(__name__)

@app.route('/hello/')
@app.route("/hello/<name>")
def hello_world(name=None):
    # return f"<p>Hello, {escape(name)}!</p>"
    return render_template('hello.html.jinja', name=name)
