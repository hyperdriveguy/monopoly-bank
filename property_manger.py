import json
from functools import cached_property

class Property:
    """
    Contains data and methods for all types of Monopoly properties.
    """
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

    @property
    def rent(self):
        return self.rent_rates[self.rent_rate_index]

    @property
    def json(self):
        """
        JSONified version of the property object.
        This is not what is written to the DB.
        """
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

    def load_attributes(self, saved):
        """
        Load state from saved JSON
        """
        self.owner = saved['owner']
        self.rent_rate_index = saved['rent_rate']
        self.mortgaged = saved['mortgaged']

    def save_attributes(self):
        """
        Save the property identifier and non-permanent state
        """
        return {
            'name': self.name,
            'owner': self.owner,
            'rent_rate': self.rent_rate_index,
            'mortgaged': self.mortgaged
        }


class PropertyManager:
    """
    Load properties from a given JSON file.
    Operations for rent updates and checking color sets are provided.
    """
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

    def check_full_set(self, color):
        last_owner = None
        for prop in self.complete_sets[color]:
            if prop.owner is None:
                return False
            if prop.owner == last_owner or last_owner is None:
                last_owner = prop.owner
        return True

    def update_color_set_rent(self, color):
        """
        Updates rent index if a color set is completed or broken.
        If a color set is broken, the rent rate will be reset back to base rent.
        """
        is_full_set = self.check_full_set(color)
        print('Color set is complete!') if is_full_set else print('Color set seperated.')
        for prop in self.complete_sets[color]:
            print(prop.name)
            if is_full_set:
                prop.rent_rate_index = 'Color set'
            else:
                prop.rent_rate_index = 'Base'

    @cached_property
    def all_properties(self):
        return tuple(self.properties.values())

    @property
    def unowned(self):
        return tuple(filter(lambda p: True if p.owner is None else False, self.all_properties))

    @property
    def owned(self):
        return tuple(filter(lambda p: False if p.owner is None else True, self.all_properties))

