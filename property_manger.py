import json
from functools import cached_property

class Property:
    def __init__(self, name: str, color: str, rent_rates: list, costs: dict):
        # Base card properties
        self.name = name
        self.color = color
        self.rent_rates = rent_rates
        self.costs = costs
        # Current attributes in play
        self.owner = None
        self.rent_rate_index = 0
        self.mortgaged = False

    @cached_property
    def rent(self):
        return self.rent_rates[self.rent_rate_index]


class Railroad:
    def __init__(self, name: str, rent_rates: list, cost: int):
        # Base card properties
        self.name = name
        self.color = None
        self.rent_rates = rent_rates
        self.costs = {'property': cost}
        # Current attributes in play
        self.owner = None
        self.rent_rate_index = 0
        self.mortgaged = False

    @cached_property
    def rent(self):
        return self.rent_rates[self.rent_rate_index]


class Utility:
    def __init__(self, name: str, rent_rates: list, cost: int):
        # Base card properties
        self.name = name
        self.color = None
        self.rent_rates = rent_rates
        self.costs = {'property': cost}
        # Current attributes in play
        self.owner = None
        self.rent_rate_index = 0
        self.mortgaged = False

    @cached_property
    def rent(self):
        # Note this is a dice weighted rent
        return self.rent_rates[self.rent_rate_index]


class PropertyManager:
    def __init__(self, property_set):
        self.buildable = {}
        self.railroad = {}
        self.utility = {}

        with open(property_set, 'r') as prop_file:
            loaded_properties = json.load(prop_file)

        for name, attributes in loaded_properties.items():
            if attributes['type'] == 'buildable':
                self.buildable[name] = Property(name, attributes['color'], attributes['rent'], attributes['cost'])
            elif attributes['type'] == 'railroad':
                self.railroad[name] = Railroad(name, attributes['rent'], attributes['cost'])
            elif attributes['type'] == 'utility':
                self.utility[name] = Utility(name, attributes['rent'], attributes['cost'])
            else:
                raise ValueError('No type found for Monopoly Property type', attributes['type'])

    @cached_property
    def all_properties(self):
        return tuple(self.buildable.values()) + tuple(self.railroad.values()) + tuple(self.utility.values())

    @cached_property
    def unowned(self):
        return tuple(filter(lambda p: True if p.owner is None else False, self.all_properties))

    @cached_property
    def owned(self):
        return tuple(filter(lambda p: False if p.owner is None else True, self.all_properties))

