# satellite-catalog-service

Mikroserwis STAC dla katalogu SKY_SHIELD (SkyIsNoLimit, JSON) i SPACE_EYE
(SpaceIsNoLimit, XML): przyjmuje surowe metadane, mapuje je na STAC Item, 
zapisuje w Postgres+pgSTAC i udostępnia przez 
`GET /search` z filtrowaniem po bbox/datetime/cloud_cover/processing:level.

> Interaktywna dokumentacja API (Swagger UI): http://localhost:8000/docs

## Szybki start

Uruchom poniższe polecenia z katalogu głównego repozytorium.

### 1. Przygotuj konfigurację

Projekt korzysta ze zmiennych środowiskowych zapisanych w pliku .env.
W repozytorium znajduje się gotowa konfiguracja przykładowa w pliku .env.example. Aby ją skopiować, uruchom:
```bash
./bin/copy_env.sh
```
Domyślne wartości z .env.example wystarczają do lokalnego uruchomienia aplikacji.

### 2. Uruchom aplikację
Aby uruchomić:
```bash
# skrypt wykonuje: docker compose up --build
./bin/start.sh
```

Compose podnosi trzy serwisy w kolejności zależności:

- `postgres` - obraz `ghcr.io/stac-utils/pgstac` (PostGIS + rozszerzenia dla pgSTAC).
- `pgstac-migrate` - jednorazowo ładuje schemat pgSTAC (`pypgstac migrate`), kończy się i wychodzi.
- `rabbitmq` - broker wiadomości. Przechowuje surowe payloady wysłane na `/ingest/{mission}` w trwałej kolejce (`ingestion.raw.q`) do czasu przetworzenia przez `worker`
- `worker` - osobny proces konsumujący `ingestion.raw.q`: parsuje surowe metadane do STAC Item i zapisuje w pgSTAC. Potwierdza wiadomość (`ack`) dopiero po udanym zapisie; błędne dane trafiają do DLQ
- `app` - startuje dopiero, gdy `postgres` jest zdrowy, a migracja zakończyła się sukcesem. Przy starcie rejestruje kolekcje `SKY_SHIELD`/`SPACE_EYE` w pgSTAC.

### 3. Sprawdź, czy aplikacja działa

```bash
curl -i http://localhost:8000/health
# {"status": "ok", "database": "reachable"}
```

## Przykładowe zapytania curl

### 1. Wysłanie metadanych SKY_SHIELD (JSON)

```bash
curl -i -X POST http://localhost:8000/ingest/SKY_SHIELD \
  -H "Content-Type: application/json" \
  --data-binary @tests/fixtures/sky_shield_sample.json
```

### 2. Wysłanie metadanych SPACE_EYE (XML)

```bash
curl -i -X POST http://localhost:8000/ingest/SPACE_EYE \
  -H "Content-Type: application/xml" \
  --data-binary @tests/fixtures/space_eye_sample.xml
```

### 3. Przeszukanie katalogu

```bash
# Wszystko, domyślny limit
curl -s http://localhost:8000/search | jq

# Filtr po bbox (obejmuje scenę SKY_SHIELD z próbki)
curl -s "http://localhost:8000/search?bbox=20.0,51.0,22.0,53.0" | jq

# Filtr po dacie (interwał) + kolekcji
curl -s "http://localhost:8000/search?datetime=2026-08-01T00:00:00Z/2026-09-01T00:00:00Z&collections=SKY_SHIELD" | jq

# Max zachmurzenie + poziom przetworzenia
curl -s "http://localhost:8000/search?max_cloud_cover=20&processing_level=L1C" | jq
```

Odpowiedź to natywny wynik `pgstac.search()` - dict w kształcie STAC API
ItemCollection (`type: FeatureCollection`, `features: [...STAC Item]`, `links`).

## Testy

### Mock "satelita"

Serwis `mock-satellite` symuluje nadawanie danych: w losowych odstępach
(5-30s) wysyła próbkę SKY_SHIELD lub SPACE_EYE na `POST /ingest/{mission}`.
Jest opcjonalny (profil `mock`):

```bash
# skrypt wykonuje: docker compose --profile mock up --build
./bin/mock_profile.sh
```

>Podgląd kolejek/DLQ: http://localhost:15672 (guest/guest).

### Testy jednostkowe, bez Dockera

```bash
pip install -e ".[dev]"
pytest -v                          
```

### Testy na realnym Postgres+pgSTAC (testcontainers, wymaga Docker)

```bash
pip install -e ".[dev,integration]"
pytest -v -m integration
```

## Struktura

```
src/satellite_catalog/
├── main.py                     # FastAPI app: /health, wiring routerów, repozytorium i kolejki
├── settings.py                 # konfiguracja z env (DATABASE_URL)
├── deps.py                     # Depends(get_repository) - DI dla routerów
├── db/
│   └── session.py                # pula połączeń asyncpg
├── core/                        # wspólny rdzeń domenowy STAC
│   ├── mission.py                 # enum Mission
│   ├── geometry.py                # reprojekcja CRS, bbox
│   ├── extensions.py              # eo / processing / view / sat
│   └── stac_models.py             # budowa + walidacja STAC Item (stac-pydantic)
├── ingestion/                   # przyjęcie i parsowanie
│   ├── errors.py
│   ├── service.py                 # IngestionService: parse -> save
│   ├── api.py                     # POST /ingest/{mission} - publikuje do kolejki, zwraca 202
│   ├── queue_port.py              # QueuePort (Protocol)
│   ├── rabbitmq_queue.py          # implementacja QueuePort (aio-pika, topologia exchange/queue/DLQ)
│   ├── worker.py                  # osobny proces: konsumuje kolejkę, wywołuje 
│   └── parsers/
│       ├── base.py                 # ParserPort (Strategy)
│       ├── sky_is_no_limit.py
│       ├── space_is_no_limit.py
│       └── registry.py             # Mission -> parser (Factory/OCP)
└── catalog/                     # przechowywanie i wyszukiwanie
    ├── errors.py
    ├── collections.py             # STAC Collection dla obu misji
    ├── repository.py              # CatalogRepositoryPort (Protocol)
    ├── pgstac_repository.py       # implementacja (funkcje SQL pgSTAC)
    ├── search.py                  # budowa/walidacja query -> search body pgSTAC
    └── api.py                     # GET /search

docker/
├── app.Dockerfile
├── worker.Dockerfile
└── mock-satellite.Dockerfile

bin/
├── copy_env.sh
├── mock_profile.sh
├── start.sh
└── stop.sh

mock_satellite/
└── sender.py                    # mock "satelity": losowo POST-uje próbki na /ingest/{mission}

tests/
├── fixtures/                    # dostarczone próbki JSON/XML
├── unit/                        # testy, bez Dockera
│   ├── ingestion/                 # parsery + IngestionService
│   ├── catalog/                   # collections, search, repository (fake DB)
│   └── api/                       # endpointy na fake repozytorium (FastAPI TestClient)
└── integration/                 # testy na realnym Postgres+pgSTAC (testcontainers)
    └── test_pgstac_repository_integration.py   # wymaga Docker - pytest -m integration
```
