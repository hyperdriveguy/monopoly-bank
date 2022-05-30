#!/usr/bin/env python
MAX_SWIPE_TRIES = 3

def clear(prompt=False):
    if prompt == True:
        input('Press Enter to continue...')
    print('\033c')


class Account:

    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.cash = 0
        self.properties = []
    
    def __str__(self):
        return f'{self.name}:\n\tID: {self.id}\n\tBalance: ${self.cash}'

    def withdraw(self, amount):
        if amount > self.cash:
            amount = self.cash
            self.cash = 0
        else:
            self.cash -= amount
        return amount

    def deposit(self, amount):
        self.cash += amount
        return amount


class AccountManager:

    def __init__(self):
        self.card_numbers = dict()

    def new(self, id_num, card_holder):
        """
        Create a new account
        """
        if self.exists(id_num):
            return 'Card already associated with an account!'
        self.card_numbers[id_num] = Account(id_num, card_holder)
        return f'Created new account for {card_holder}.'

    def delete(self, id_num):
        self.card_numbers.pop(id_num)
    
    def exists(self, id_num):
        return id_num in self.card_numbers
    
    def query(self, id_num):
        return self.card_numbers[id_num]
    
    def transfer(self, payer, payee, amount: int):
        paying_account = self.card_numbers[payer]
        if paying_account.cash < amount:
            return f'{paying_account.name} does not have enough funds to complete the transaction.'
        paying_account.withdraw(amount)
        payee_account = self.card_numbers[payee]
        payee_account.deposit(amount)
        return f'{self.card_numbers[payer].name} paid {self.card_numbers[payee].name} ${amount}.'


def term_swipe_card(accounts, verify=True):
    card_num = input('Swipe card... ')
    if verify:
        tried = 1
        while not accounts.exists(card_num) and tried < MAX_SWIPE_TRIES:
            card_num = input('Account not found, reswipe card... ')
            tried += 1
        if not accounts.exists(card_num):
            card_num = ''
    clear()
    return card_num


def term_new_account(accounts):
    clear()
    card_num = term_swipe_card(accounts, verify=False)
    card_holder = input('Card holder\'s name: ')
    print(accounts.new(card_num, card_holder))
    clear(True)


def term_del_account(accounts):
    clear()
    card_num = term_swipe_card(accounts)
    if card_num == '':
        return
    confirm = input(f'{accounts.query(card_num)}\nAre you sure you want to delete this account? (y/N) ')
    if len(confirm) == 0:
        print('Account was not deleted')
        clear(True)
        return
    confirm = confirm[0].lower()
    if confirm == 'y':
        accounts.delete(card_num)
        print('Account deleted.')
    else:
        print('Account was not deleted')
    clear(True)


def term_query_account(accounts):
    clear()
    card_num = term_swipe_card(accounts)
    if card_num == '':
        return
    print(accounts.query(card_num))
    clear(True)


def term_deposit(accounts):
    clear()
    card_num = term_swipe_card(accounts)
    if card_num == '':
        return
    target_account = accounts.query(card_num)
    amount = input('Enter amount for deposit: ')
    try:
        amount = int(amount)
    except ValueError:
        return
    target_account.deposit(amount)
    print(f'Deposited ${amount}.')
    clear(True)


def term_withdraw(accounts):
    clear()
    card_num = term_swipe_card(accounts)
    if card_num == '':
        return
    target_account = accounts.query(card_num)
    amount = input('Enter amount for withdrawl: ')
    try:
        amount = int(amount)
    except ValueError:
        return
    withdrawn = target_account.withdraw(amount)
    print(f'Withdrew ${withdrawn}.')
    clear(True)


def term_transfer(accounts):
    clear()
    print('Have payer swipe card.')
    payer = term_swipe_card(accounts)
    if payer == '':
        return
    print('Have payee swipe card.')
    payee = term_swipe_card(accounts)
    if payee == '':
        return
    amount = input('Enter amount for payment: ')
    try:
        amount = int(amount)
    except ValueError:
        return
    print(accounts.transfer(payer, payee, amount))
    clear(True)
    

def terminal_mode():
    accounts = AccountManager()
    all_commands = {'n': term_new_account, 'e': term_del_account, 'q': term_query_account, 'd': term_deposit, 'w': term_withdraw, 't': term_transfer}
    while True:
        clear()
        print('(N)ew Account | d(E)lete Account | (Q)uery | (D)eposit | (W)ithdraw | (T)ransfer | qu(I)t')
        command = input('>>> ')
        if len(command) == 0:
            continue
        command = command[0].lower()
        if command == 'i':
            break
        if command not in all_commands:
            continue
        all_commands[command](accounts)

    

if __name__ == '__main__':
    terminal_mode()
