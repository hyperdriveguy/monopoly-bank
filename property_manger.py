import json
from functools import cached_property

class Buildable:
    def __init__(self, name: str, color: str, rent_rates: list, costs: dict):
        # Base card properties
        self.name = name
        self.color = color
        self.rent_rates = rent_rates
        self.costs = costs
        # Current attributes in play
        self.owner = None
        self.rent_rate_index = "Base"
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
        self.rent_rate_index = "Base"
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
        self.rent_rate_index = "Base"
        self.mortgaged = False

    @cached_property
    def rent(self):
        # Note this is a dice weighted rent
        return self.rent_rates[self.rent_rate_index]


class PropertyManager:
    def __init__(self, property_set):
        self.properties = {}

        with open(property_set, 'r') as prop_file:
            loaded_properties = json.load(prop_file)

        for name, attributes in loaded_properties.items():
            if attributes['type'] == 'buildable':
                self.properties[name] = Buildable(name, attributes['color'], attributes['rent'], attributes['cost'])
            elif attributes['type'] == 'railroad':
                self.properties[name] = Railroad(name, attributes['rent'], attributes['cost'])
            elif attributes['type'] == 'utility':
                self.properties[name] = Utility(name, attributes['rent'], attributes['cost'])
            else:
                raise ValueError('No type found for Monopoly Property type', attributes['type'])

    @cached_property
    def all_properties(self):
        return tuple(self.properties.values())

    @cached_property
    def unowned(self):
        return tuple(filter(lambda p: True if p.owner is None else False, self.all_properties))

    @cached_property
    def owned(self):
        return tuple(filter(lambda p: False if p.owner is None else True, self.all_properties))

