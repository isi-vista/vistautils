from typing import Optional

from flexnlp import EntityType
from flexnlp.utils.immutablecollections import ImmutableDict, ImmutableSet

VALID_ACE_TYPES = ImmutableSet.of({'PER', 'ORG', 'GPE', 'LOC', 'FAC', 'VEH', 'WEA'})
VALID_ACE_SUBTYPES = ImmutableDict.of(
    {"FAC": {"Airport", "Building-Grounds", "Path", "Plant", "Subarea-Facility"},
     "GPE": {"Continent", "County-or-District", "GPE-Cluster", "Nation",
             "Population-Center", "Special", "State-or-Province"},
     "LOC": {"Address", "Boundary", "Celestial", "Land-Region-Natural",
             "Region-General", "Region-International", "Water-Body"},
     "ORG": {"Commercial", "Educational", "Entertainment", "Government", "Media",
             "Medical-Science", "Non-Governmental", "Religious", "Sports"},
     "PER": {"Group", "Indeterminate", "Individual"},
     "VEH": {"Air", "Land", "Subarea-Vehicle", "Underspecified", "Water"},
     "WEA": {"Biological", "Blunt", "Chemical", "Exploding", "Nuclear",
             "Projectile", "Sharp", "Shooting", "Underspecified"}})
DEFAULT_ACE_SUBTYPES = ImmutableDict.of({'FAC': 'Building-Grounds',
                                         'GPE': 'Population-Center',
                                         'LOC': 'Region-General',
                                         'ORG': 'Commercial',
                                         'PER': 'Individual',
                                         'VEH': 'Land',
                                         'WEA': 'Shooting'})
ACE_ENTITY_TYPE_CONVERSIONS = ImmutableDict.of({'PERSON': 'PER',
                                                'NORP': 'GPE',  # imperfect
                                                'FACILITY': 'FAC'})


def get_ace_entity_type(entity_type: EntityType) -> Optional[EntityType]:

    if not entity_type:
        return None
    primary_type = entity_type.get_primary_type()

    # Entity type & subtype already valid
    if (primary_type in VALID_ACE_TYPES and
            entity_type.num_levels() > 1 and
            entity_type.get_secondary_type() in VALID_ACE_SUBTYPES[primary_type]):
        return entity_type

    # Convert primary type
    if primary_type in ACE_ENTITY_TYPE_CONVERSIONS:
        primary_type = ACE_ENTITY_TYPE_CONVERSIONS[primary_type]

    if primary_type not in VALID_ACE_TYPES:
        return None

    return EntityType((primary_type, DEFAULT_ACE_SUBTYPES[primary_type]))
