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

    def __init__(self, ident, name, pw_salt, pw_hash, starting_cash:int, properties, banker, update_event, log_connection):
        self.ident = ident
        self.name = name.capitalize()
        self.pw_salt = pw_salt
        self.pw_hash = pw_hash
        self.cash = starting_cash
        self.properties = properties
        self.banker = banker
        self.account_update_trigger = update_event
        # Prevent race conditions by using a mutex on sections that write or change data.
        self.write_lock = Lock()
        self.tlog_connection = log_connection

    def __str__(self):
        return f'{self.name}:\n\tID: {self.ident}\n\tBalance: ${self.cash}'

    def is_authenticated(self, try_pw):
        return verify_password(self.pw_salt, self.pw_hash, try_pw)

    def is_active(self):
        return self.cash > 0

    @property
    def is_anonymous(self):
        return False

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
        print(f'Event trigger from account {self.ident} withdraw')
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
            print(f'Event trigger from account {self.ident} deposit')
            if log:
                self.tlog_connection.log_account_deposit(self.ident, amount)
        else:
            amount = 0
        return amount

    def get_transactions(self):
        return self.tlog_connection.log_get_by_id(self.ident)


class AccountManager:

    def __init__(self):
        self.accounts_storage = dict()
        self.server_update_signal = Event()
        # Prevent race conditions by locking sections that write or change data.
        self.write_lock = Lock()
        self.tlog_connection = TransactionLog('tlog.db')
        self.tlog_connection.log_server_started()
        self.load_saved()
        # Ensure update signal starts cleared
        self.recieved_update()

    def load_saved(self):
        account_tuples = self.tlog_connection.get_all_accounts()
        self.write_lock.acquire()
        self.accounts_storage = dict()
        for acc in account_tuples:
            self.accounts_storage[acc[0]] = Account(*acc, self.server_update_signal, self.tlog_connection)
        self.write_lock.release()
        self.server_update_signal.set()
        print('Event trigger from load_saved')
        self.tlog_connection.log_accounts_reloaded()
        return f'Loaded {len(self.accounts_storage)} account{"s" if len(self.accounts_storage) != 1 else ""} from database'

    def nuke_accounts(self):
        self.accounts_storage = dict()
        self.tlog_connection.nuke_tables()
        return 'Deleted all account and transaction information.'

    def new(self, user_id, card_holder, password, starting_amount:int=1000) -> bool:
        """
        Create a new account

        If no accounts exist, the first player to make a new account is the banker.
        """
        pass_salt, pass_hash = hash_new_password(password)
        self.write_lock.acquire()
        if self.exists(user_id):
            self.write_lock.release()
            # f'ID "{user_id}" already associated with an account!'
            return False
        is_banker = len(self.accounts_storage) == 0
        self.accounts_storage[user_id] = Account(user_id, card_holder, pass_salt, pass_hash, starting_amount, set(), is_banker,  self.server_update_signal, self.tlog_connection)
        self.write_lock.release()
        self.tlog_connection.create_account(user_id, card_holder, pass_salt, pass_hash, starting_amount, is_banker)
        self.server_update_signal.set()
        print('Event trigger from new account')
        self.tlog_connection.log_account_created(user_id, starting_amount)
        # f'Created new account for {card_holder}.'
        return True

    def delete(self, user_id):
        self.write_lock.acquire()
        self.accounts_storage.pop(user_id)
        self.write_lock.release()
        self.tlog_connection.delete_account(user_id)
        self.server_update_signal.set()
        print('Event trigger from delete account')
        self.tlog_connection.log_account_deleted(user_id)

    def exists(self, user_id):
        return user_id in self.accounts_storage

    @property
    def num_accounts(self):
        return len(self.accounts_storage)

    def query(self, user_id):
        if self.exists(user_id):
            return self.accounts_storage[user_id]
        return 'Account does not exist.'

    def search(self, query):

        def match_in_query(acc):
            name_match = query.lower() in acc.name.lower()
            id_match = query.lower() in acc.ident.lower()
            return name_match or id_match

        if query.lower() in ('all', ''):
            return self.accounts_storage
        return { u:a for u, a in self.accounts_storage.items() if match_in_query(a)}

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
        print('Event trigger from transfer')
        self.tlog_connection.log_account_transfer(payer, payee, info)
        return info

    def recieved_update(self):
        self.server_update_signal.clear()

    def cleanup(self):
        yield '\nStarting cleanup'
        yield from self.tlog_connection.stop_db()
