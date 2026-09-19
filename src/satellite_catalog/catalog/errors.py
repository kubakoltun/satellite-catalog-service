class CatalogError(Exception):
    """Base exception for errors at the storage-search layer"""


class ItemPersistenceError(CatalogError):
    """Saving an Item to the catalog did not succeede (data basse error)."""


class CollectionPersistenceError(CatalogError):
    """Saving/registering Collection in the catalog did not succeede."""


class SearchError(CatalogError):
    """Searchin the catalog did not succeede (data basse error)."""
