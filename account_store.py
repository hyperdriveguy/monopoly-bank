#!/usr/bin/env python

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
            return self.card_numbers.values()
        return tuple(filter(match_in_query, self.card_numbers.values()))
    
    def transfer(self, payer, payee, amount: int):
        paying_account = self.card_numbers[payer]
        if paying_account.cash < amount:
            return f'{paying_account.name} does not have enough funds to complete the transaction.'
        paying_account.withdraw(amount)
        payee_account = self.card_numbers[payee]
        payee_account.deposit(amount)
        return f'{self.card_numbers[payer].name} paid {self.card_numbers[payee].name} ${amount}.'
