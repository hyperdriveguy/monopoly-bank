import json
from functools import cached_property

class Property:
    def __init__(self, name: str, rent_rates: list, costs: dict, prop_type: str, color: str=None,):
        # Base card properties
        self.name = name
        self.color = color
        self.prop_type = prop_type
        self.rent_rates = rent_rates
        self.costs = costs
        # Current attributes in play
        self.owner = None
        self.rent_rate_index = "Base"
        self.mortgaged = False

    @cached_property
    def rent(self):
        return self.rent_rates[self.rent_rate_index]

    @cached_property
    def json(self):
        return {
            self.name: {
                'type': self.prop_type,
                'color': self.color,
                'rent': self.rent_rates,
                'cost': self.costs,
                'owner': self.owner,
                'rent index': self.rent_rate_index,
                'mortgaged': self.mortgaged
            }
        }


class PropertyManager:
    def __init__(self, property_set):
        self.properties = {}
        self.complete_sets = {}

        with open(property_set, 'r') as prop_file:
            loaded_properties = json.load(prop_file)

        for name, attributes in loaded_properties.items():
            if attributes['type'] == 'buildable':
                new_prop = Property(name, attributes['rent'], attributes['cost'], attributes['type'], attributes['color'])
                self.properties[name] = new_prop
                if attributes['color'] in self.complete_sets:
                    self.complete_sets[attributes['color']].add(new_prop)
                else:
                    self.complete_sets[attributes['color']] = {new_prop, }
            else:
                new_prop = Property(name, attributes['rent'], attributes['cost'], attributes['type'])
                self.properties[name] = new_prop
                if attributes['type'] in self.complete_sets:
                    self.complete_sets[attributes['type']].add(new_prop)
                else:
                    self.complete_sets[attributes['type']] = {new_prop, }

    def check_full_set(self, color):
        last_owner = None
        for prop in self.complete_sets[color]:
            if prop.owner is None:
                return False
            if prop.owner == last_owner or last_owner is None:
                prop.owner = last_owner
        return True

    @cached_property
    def all_properties(self):
        return tuple(self.properties.values())

    @cached_property
    def unowned(self):
        return tuple(filter(lambda p: True if p.owner is None else False, self.all_properties))

    @cached_property
    def owned(self):
        return tuple(filter(lambda p: False if p.owner is None else True, self.all_properties))

