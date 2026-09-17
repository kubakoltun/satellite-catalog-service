class CatalogError(Exception):
    """Bazowy wyjątek dla błędów warstwy przechowywania/wyszukiwania."""


class ItemPersistenceError(CatalogError):
    """Zapis Itemu do katalogu się nie powiódł (błąd bazy danych)."""


class CollectionPersistenceError(CatalogError):
    """Zapis/rejestracja Collection w katalogu się nie powiodła."""


class SearchError(CatalogError):
    """Wyszukiwanie w katalogu się nie powiodło (błąd bazy danych)."""
