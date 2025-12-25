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
        # Mortgaged properties collect no rent
        if self.mortgaged:
            return 0
        return self.rent_rates[self.rent_rate_index]

    @property
    def mortgage_value(self):
        """Calculate mortgage value (half of property cost)."""
        return self.costs['property'] // 2

    def mortgage(self):
        """Mortgage the property. Returns the mortgage value."""
        if not self.mortgaged and self.owner:
            self.mortgaged = True
            return self.mortgage_value
        return 0

    def unmortgage(self, interest_rate=0.10):
        """Unmortgage the property. Returns the cost to unmortgage (mortgage + interest)."""
        if self.mortgaged and self.owner:
            unmortgage_cost = int(self.mortgage_value * (1 + interest_rate))
            self.mortgaged = False
            return unmortgage_cost
        return 0

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

    def upgrade(self):
        """
        Upgrade property to next building level (add house or hotel).
        Returns True if successful, False otherwise.
        """
        if self.prop_type != 'buildable' or not self.owner:
            return False
        
        upgrade_sequence = ['Base', 'Color set', '1 House', '2 Houses', '3 Houses', '4 Houses', 'Hotel']
        
        if self.rent_rate_index not in upgrade_sequence:
            return False
        
        current_index = upgrade_sequence.index(self.rent_rate_index)
        if current_index < len(upgrade_sequence) - 1:
            self.rent_rate_index = upgrade_sequence[current_index + 1]
            return True
        return False

    def downgrade(self, property_manager=None):
        """
        Downgrade property to previous building level (remove house or hotel).
        Returns True if successful, False otherwise.
        If owner doesn't have full color set, skip 'Color set' tier and go to 'Base'.
        """
        if self.prop_type != 'buildable' or not self.owner:
            return False
        
        downgrade_sequence = ['Hotel', '4 Houses', '3 Houses', '2 Houses', '1 House', 'Color set']
        
        if self.rent_rate_index not in downgrade_sequence:
            return False
        
        current_index = downgrade_sequence.index(self.rent_rate_index)
        if current_index < len(downgrade_sequence) - 1:
            next_level = downgrade_sequence[current_index + 1]
            # If next level would be 'Color set' but owner doesn't have full set, go to 'Base'
            if next_level == 'Color set' and property_manager:
                if not self.owner_has_full_set(property_manager):
                    next_level = 'Base'
            self.rent_rate_index = next_level
            return True
        return False

    @property
    def can_build(self):
        """Check if property can have buildings added."""
        return self.prop_type == 'buildable' and self.owner is not None and not self.mortgaged

    @property
    def building_level(self):
        """Get the current building level as a readable string."""
        if self.rent_rate_index in ['Base', 'Color set']:
            return 'No buildings'
        return self.rent_rate_index

    def owner_has_full_set(self, property_manager):
        """Check if the owner has the full color set for this property."""
        if not self.color or not self.owner:
            return False
        return property_manager.check_full_set(self.color)


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
        If a color set is broken, properties with buildings keep their buildings.
        Only properties without buildings (Base or Color set) are updated.
        """
        is_full_set = self.check_full_set(color)
        print('Color set is complete!') if is_full_set else print('Color set seperated.')
        for prop in self.complete_sets[color]:
            print(prop.name)
            # Only update properties without buildings
            if prop.rent_rate_index in ['Base', 'Color set']:
                if is_full_set:
                    prop.rent_rate_index = 'Color set'
                else:
                    prop.rent_rate_index = 'Base'
            # Properties with buildings keep their buildings even if set is broken

    @cached_property
    def all_properties(self):
        return tuple(self.properties.values())

    @property
    def unowned(self):
        return tuple(filter(lambda p: True if p.owner is None else False, self.all_properties))

    @property
    def owned(self):
        return tuple(filter(lambda p: False if p.owner is None else True, self.all_properties))

