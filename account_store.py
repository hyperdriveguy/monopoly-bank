#!/usr/bin/env python
from threading import Event

class Account:

    def __init__(self, id, name, starting_cash:int=0, update_event=Event()):
        self.id = id
        self.name = name.capitalize()
        self.cash = starting_cash
        self.properties = []
        self.account_sync = update_event
    
    def __str__(self):
        return f'{self.name}:\n\tID: {self.id}\n\tBalance: ${self.cash}'

    def withdraw(self, amount):
        if amount > self.cash:
            amount = self.cash
            self.cash = 0
        else:
            self.cash -= amount
        self.account_sync.set()
        return amount

    def deposit(self, amount):
        print('deposit', amount)
        if amount > 0:
            self.cash += amount
        else:
            amount = 0
        self.account_sync.set()
        return amount


class AccountManager:

    def __init__(self):
        self.card_numbers = dict()
        self.sync_event = Event()

    def new(self, id_num, card_holder, starting_amount:int=0):
        """
        Create a new account
        """
        if self.exists(id_num):
            return f'ID "{id_num}" already associated with an account!'
        self.card_numbers[id_num] = Account(id_num, card_holder, starting_amount, self.sync_event)
        self.sync_event.set()
        return f'Created new account for {card_holder}.'

    def delete(self, id_num):
        self.card_numbers.pop(id_num)
        self.sync_event.set()
    
    def exists(self, id_num):
        return id_num in self.card_numbers
    
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
            # return sorted(self.card_numbers.values(), key=lambda x: x.name)
            return self.card_numbers
        return { u:a for u, a in self.card_numbers.items() if match_in_query(a)}
        # return sorted(tuple(filter(match_in_query, self.card_numbers.values())), key=lambda x: x.name)
    
    def transfer(self, payer, payee, amount: int):
        paying_account = self.card_numbers[payer]
        if paying_account.cash < amount:
            return f'{paying_account.name} does not have enough funds to complete the transaction.'
        paying_account.withdraw(amount)
        payee_account = self.card_numbers[payee]
        payee_account.deposit(amount)
        self.sync_event.set()
        return f'{self.card_numbers[payer].name} paid {self.card_numbers[payee].name} ${amount}.'
    
    def sync(self):
        print('Event sync set:', self.sync_event.is_set())
        self.sync_event.clear()
