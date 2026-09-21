class CatalogError(Exception):
    """Base exception for errors at the storage-search layer"""


class ItemPersistenceError(CatalogError):
    """Saving an Item to the catalog did not succeed (database error)."""


class CollectionPersistenceError(CatalogError):
    """Saving/registering a Collection in the catalog did not succeed."""


class SearchError(CatalogError):
    """Searching the catalog did not succeed (database error)."""
