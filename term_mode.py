#!/usr/bin/env python

from account_store import AccountManager

MAX_SWIPE_TRIES = 3

def clear(prompt=False):
    if prompt == True:
        input('Press Enter to continue...')
    print('\033c')


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
