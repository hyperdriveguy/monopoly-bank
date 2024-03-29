# from threading import Event, Semaphore, Lock, Thread
from multiprocessing import Process, Queue
# from queue import Queue
import sqlite3
from datetime import datetime

SIG_STOP = 'done'


class TransactionLog:

    def __init__(self, filename, exec_queue=Queue(200), recv_queue=Queue(100)):
        self.filename = filename
        self.exec_queue = exec_queue
        self.receive_data = recv_queue
        self.listener_thread = Process(target=self._queue_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        # listener_thread.join()

    def _queue_listener(self):
        db = sqlite3.connect(self.filename)
        # Create TLog table and Accounts table if they doesn't exist
        db.execute(
            """CREATE TABLE IF NOT EXISTS TLog(
                time TEXT,
                type TEXT,
                account TEXT,
                info TEXT)
            """
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS Accounts(
                id TEXT PRIMARY KEY,
                name TEXT,
                salt BLOB,
                password_hash BLOB,
                cash INTEGER,
                properties TEXT,
                is_banker BOOL)
            """
        )
        while True:
            try:
                next_command = self.exec_queue.get()
            except KeyboardInterrupt:
                pass
            if next_command == SIG_STOP:
                break
            update, com, args = next_command
            if update:
                if args is not None:
                    db.execute(com, args)
                else:
                    db.execute(com)
                db.commit()
            else:
                if args is not None:
                    self.receive_data.put(db.execute(com, args).fetchall())
                else:
                    self.receive_data.put(db.execute(com).fetchall())
        db.commit()
        db.close()


    def _send_transaction_to_listener(self, trans_type, account, info):
        timestamp = datetime.now()
        self.exec_queue.put((
            True,
            "INSERT INTO TLog VALUES (?, ?, ?, ?)",
            (
                timestamp,
                trans_type,
                account,
                info
            )
        ))

    def log_account_created(self, ident, cash):
        trans_type = 'Create'
        info = f'Started with ${cash}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_deleted(self, ident):
        trans_type = 'Delete'
        self._send_transaction_to_listener(trans_type, ident, None)

    def log_account_deposit(self, ident, amount):
        trans_type = 'Deposit'
        info = f'${amount}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_withdraw(self, ident, amount):
        trans_type = 'Withdraw'
        info = f'${amount}'
        self._send_transaction_to_listener(trans_type, ident, info)

    def log_account_transfer(self, payer, payee, info):
        trans_type = 'Transfer'
        self._send_transaction_to_listener(trans_type, payer, info)
        self._send_transaction_to_listener(trans_type, payee, info)

    def log_server_started(self):
        trans_type = 'Server Start'
        id_num = None
        info = 'Server has started'
        self._send_transaction_to_listener(trans_type, id_num, info)

    def log_accounts_reloaded(self):
        trans_type = 'Reload'
        id_num = None
        info = 'Reloaded all accounts'
        self._send_transaction_to_listener(trans_type, id_num, info)

    def log_get_by_id(self, ident):
        self.exec_queue.put((
            False,
            "SELECT * FROM TLog WHERE account=? ORDER BY time",
            (ident,)
        ))
        return self.receive_data.get()

    def purge_logs(self):
        self.exec_queue.put((
            True,
            "DELETE FROM TLog",
            None
        ))

    def create_account(self, ident, name, pw_salt, pw_hash, cash, is_banker):
        self.exec_queue.put((
            True,
            "INSERT INTO Accounts VALUES (?, ?, ?, ?, ?, '{}', ?)",
            (ident, name, pw_salt, pw_hash, cash, is_banker)
        ))

    def update_account(self, ident, cash):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET cash=? WHERE id=?",
            (cash, ident)
        ))

    def update_properties(self, ident, properties):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET properties=? WHERE id=?",
            (properties, ident)
        ))

    def delete_account(self, ident):
        self.exec_queue.put((
            True,
            "DELETE FROM Accounts WHERE id=?",
            (ident,)
        ))

    def get_all_accounts(self):
        self.exec_queue.put((
            False,
            "SELECT * FROM Accounts",
            None
        ))
        return self.receive_data.get()

    def set_account_password(self, ident, salt, hashed_pass):
        self.exec_queue.put((
            True,
            "UPDATE Accounts SET salt=? password_hash=? WHERE id=?",
            (salt, hashed_pass, ident)
        ))

    def retrieve_hashed_password(self, ident):
        self.exec_queue.put((
            False,
            "SELECT salt, password_hash FROM Accounts WHERE id=?",
            (ident,)
        ))
        return self.receive_data.get()

    def nuke_tables(self):
        self.exec_queue.put((
            True,
            "DELETE FROM Accounts",
            None
        ))
        trans_type = 'Nuke Data'
        id_num = None
        info = 'Accounts and TLog were purged'
        self._send_transaction_to_listener(trans_type, id_num, info)
        self.purge_logs()

    def stop_db(self):
        trans_type = 'Server Stop'
        id_num = None
        info = 'Server has stopped'
        self._send_transaction_to_listener(trans_type, id_num, info)
        yield 'Logged server stop'
        self.exec_queue.put(SIG_STOP)
        yield 'Signaled db listener close'
        self.listener_thread.join()
        yield 'Stopped TLog'
