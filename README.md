# satellite-catalog-service

> Postgres+pgSTAC + pusta aplikacja
> FastAPI z endpointem `/health`, który realnie odpytuje bazę. Logika
> ingestion/catalog w kolejnych krokach.

## Uruchomienie

```bash
docker compose up --build
```

Compose podnosi trzy serwisy w kolejności zależności:

1. `postgres` - obraz `ghcr.io/stac-utils/pgstac` (PostGIS + rozszerzenia wymagane przez pgSTAC).
2. `pgstac-migrate` - jednorazowo ładuje schemat pgSTAC (`pypgstac migrate`), kończy się i wychodzi.
3. `app` - startuje dopiero, gdy `postgres` jest zdrowy, a migracja zakończyła się sukcesem.

## Weryfikacja

```bash
curl -i http://localhost:8000/health
```

Oczekiwana odpowiedź:

```json
{"status": "ok", "database": "reachable"}
```

Jeśli baza jest nieosiągalna, endpoint zwróci `503` z opisem błędu -
to celowe: `/health` ma sprawdzać całą rurę (aplikacja <-> Postgres),
nie tylko to, że proces Pythona żyje.

## Struktura (na razie)

```
src/satellite_catalog/
├── main.py           # FastAPI app + /health
├── settings.py        # konfiguracja z env (DATABASE_URL)
└── db/
    └── session.py      # pula połączeń asyncpg
```
