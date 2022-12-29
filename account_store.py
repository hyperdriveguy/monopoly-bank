import hashlib
import hmac
import os
import random
from threading import Event, Lock

from tlog import TransactionLog


def hash_new_password(password: str):
    """
    Hash the provided password with a randomly-generated salt and return the
    salt and hash to store in the database.
    """
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt, pw_hash


def verify_password(salt: bytes, pw_hash: bytes, password: str):
    """
    Given a previously-stored salt and hash, and a password provided by a user
    trying to log in, check whether the password is correct.
    """
    return hmac.compare_digest(
        pw_hash,
        hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    )


class Account:

    def __init__(self, ident, name, username, pw_salt, pw_hash, starting_cash:int, properties, update_event, log_connection):
        self.ident = ident
        self.name = name.capitalize()
        self.username = username
        self.pw_salt = pw_salt
        self.pw_hash = pw_hash
        self.cash = starting_cash
        self.properties = properties
        self.account_update_trigger = update_event
        # Prevent race conditions by using a mutex on sections that write or change data.
        self.write_lock = Lock()
        self.tlog_connection = log_connection

    def __str__(self):
        return f'{self.name}:\n\tID: {self.ident}\n\tBalance: ${self.cash}'

    def is_authenticated(self, try_pw):
        return verify_password(self.pw_salt, self.pw_hash, try_pw)

    def is_active(self):
        return self.username != ''

    def is_anonymous(self):
        return False

    # Note: this isn't the internal ID, but the one the user uses
    def get_id(self):
        return self.ident

    def withdraw(self, amount, log=True):
        self.write_lock.acquire()
        if amount > self.cash:
            amount = self.cash
            self.cash = 0
        else:
            self.cash -= amount
        self.write_lock.release()
        self.tlog_connection.update_account(self.ident, self.cash)
        self.account_update_trigger.set()
        if log:
            self.tlog_connection.log_account_withdraw(self.ident, amount)
        return amount

    def deposit(self, amount, log=True):
        if amount > 0:
            self.write_lock.acquire()
            self.cash += amount
            self.write_lock.release()
            self.tlog_connection.update_account(self.ident, self.cash)
            self.account_update_trigger.set()
            if log:
                self.tlog_connection.log_account_deposit(self.ident, amount)
        else:
            amount = 0
        return amount

    def get_transactions(self):
        print(self.tlog_connection.log_get_by_id(self.ident))


class AccountManager:

    def __init__(self):
        self.card_numbers = dict()
        self.server_update_signal = Event()
        # Prevent race conditions by locking sections that write or change data.
        self.write_lock = Lock()
        self.tlog_connection = TransactionLog('tlog.db')
        self.tlog_connection.log_server_started()
        self.load_saved()

    def load_saved(self):
        account_tuples = self.tlog_connection.get_all_accounts()
        self.write_lock.acquire()
        self.card_numbers = dict()
        for acc in account_tuples:
            try:
                self.card_numbers[acc[0]] = Account(*acc, self.server_update_signal, self.tlog_connection)
            except TypeError as ex:
                print(ex)
                print(acc)
                continue
        self.write_lock.release()
        self.server_update_signal.set()
        self.tlog_connection.log_accounts_reloaded()
        return f'Loaded {len(self.card_numbers)} account{"s" if len(self.card_numbers) != 1 else ""} from database'

    def nuke_accounts(self):
        self.card_numbers = dict()
        self.tlog_connection.nuke_tables()
        return 'Deleted all account and transaction information.'

    def new(self, id_num, card_holder, starting_amount:int=0):
        """
        Create a new account
        """
        self.write_lock.acquire()
        if self.exists(id_num):
            self.write_lock.release()
            return f'ID "{id_num}" already associated with an account!'
        self.card_numbers[id_num] = Account(id_num, card_holder, '', bytes(), bytes(), starting_amount, [], self.server_update_signal, self.tlog_connection)
        self.write_lock.release()
        self.tlog_connection.create_account(id_num, card_holder, starting_amount)
        self.server_update_signal.set()
        self.tlog_connection.log_account_created(id_num, starting_amount)
        return f'Created new account for {card_holder}.'

    def delete(self, id_num):
        self.write_lock.acquire()
        self.card_numbers.pop(id_num)
        self.write_lock.release()
        self.tlog_connection.delete_account(id_num)
        self.server_update_signal.set()
        self.tlog_connection.log_account_deleted(id_num)

    def exists(self, id_num):
        return id_num in self.card_numbers
    
    def username_exists(self, username):
        for acc in self.card_numbers.values():
            if acc.username == username:
                return acc
        return None

    @property
    def num_accounts(self):
        return len(self.card_numbers)

    def query(self, id_num):
        if self.exists(id_num):
            return self.card_numbers[id_num]
        return 'Account does not exist.'

    def search(self, query):

        def match_in_query(acc):
            name_match = query.lower() in acc.name.lower()
            id_match = query.lower() in acc.id.lower()
            return name_match or id_match

        if query.lower() in ('all', ''):
            return self.card_numbers
        return { u:a for u, a in self.card_numbers.items() if match_in_query(a)}

    def transfer(self, payer, payee, amount: int):
        self.write_lock.acquire()
        paying_account = self.query(payer)
        if paying_account == 'Account does not exist.':
            self.write_lock.release()
            return f'Account for payer ID {payer} does not exist.'
        if paying_account.cash < amount:
            self.write_lock.release()
            return f'{paying_account.name} does not have enough funds to complete the transaction.'
        payee_account = self.query(payee)
        if payee_account == 'Account does not exist.':
            self.write_lock.release()
            return f'Account for payer ID {payee_account} does not exist.'
        paying_account.withdraw(amount, log=False)
        payee_account.deposit(amount, log=False)
        info = f'{paying_account.name} (${paying_account.cash}) paid {payee_account.name} (${payee_account.cash}) ${amount}.'
        self.write_lock.release()
        self.tlog_connection.update_account(payer, paying_account.cash)
        self.tlog_connection.update_account(payee, payee_account.cash)
        self.server_update_signal.set()
        self.tlog_connection.log_account_transfer(payer, payee, info)
        return info

    def recieved_update(self):
        self.server_update_signal.clear()

    def cleanup(self):
        yield '\nStarting cleanup'
        yield from self.tlog_connection.stop_db()

    def make_random_accs(self):
        """
        Make a large amount of random accounts for testing purposes.
        """
        self.new('id_num', 'card_holder')
        self.new('asdf', 'Carson')
        print('start randomness')
        for i in range(10000):
            print('Starting acc', i)
            self.new(str(random.randint(0,1000000000000000000000000000)), f'{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}{chr((i + random.randint(0, 63)) % 62 + 64)}', random.randint(0, 1000))
