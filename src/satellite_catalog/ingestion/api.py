"""Endpoint `POST /ingest/{mission}` - warstwa przyjęcia danych.

Decyzja architektoniczna (świadomie, zgodnie z wcześniejszym planem):
**sync accept + BackgroundTasks**, bez zewnętrznego brokera.

- Endpoint tylko czyta surowe body (JSON albo XML - zależnie od misji),
  planuje przetwarzanie w tle i **natychmiast** zwraca `202 Accepted`.
  Realne parsowanie + zapis do bazy dzieje się już poza cyklem
  request/response - to jest odpowiedź na wymaganie "dane przychodzą
  burstami": klient (segment naziemny) nie czeka na zapis do bazy,
  żeby dostać potwierdzenie przyjęcia.
- Błędy parsowania/walidacji/zapisu są łapane i logowane w tle - endpoint
  ich nie zwraca synchronicznie. To jest świadomy kompromis: prostszy
  i wystarczający do tego zadania, kosztem natychmiastowego feedbacku
  o błędzie dla klienta. W realnym systemie produkcyjnym to miejsce,
  w którym dokłada się broker (RabbitMQ/Kafka) + dead-letter queue +
  endpoint statusu ingestion (`GET /ingest/{id}`), żeby błąd dało się
  zaobserwować bez grzebania w logach - celowo pominięte w tym MVP,
  żeby nie budować infrastruktury, zanim jest ku temu jasna potrzeba.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError

from satellite_catalog.catalog.errors import CatalogError
from satellite_catalog.catalog.repository import CatalogRepositoryPort
from satellite_catalog.core.mission import Mission
from satellite_catalog.deps import get_repository
from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/{mission}", status_code=202)
async def ingest(
    mission: Mission,
    request: Request,
    background_tasks: BackgroundTasks,
    repository: CatalogRepositoryPort = Depends(get_repository),
) -> dict:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Puste body żądania")

    service = IngestionService(repository)
    background_tasks.add_task(_process_in_background, service, mission, raw)

    return {"status": "accepted", "mission": mission.value}


async def _process_in_background(
    service: IngestionService, mission: Mission, raw: bytes
) -> None:
    try:
        item = await service.ingest(mission, raw)
    except ParsingError as exc:
        logger.error("Błąd parsowania metadanych (misja=%s): %s", mission.value, exc)
    except ValidationError as exc:
        logger.error(
            "Wynikowy STAC Item niezgodny ze specyfikacją (misja=%s): %s", mission.value, exc
        )
    except CatalogError as exc:
        logger.error("Błąd zapisu do katalogu (misja=%s): %s", mission.value, exc)
    except Exception:  # noqa: BLE001 - ostatnia linia obrony w tle, ma trafić do logów, nie ubić workera
        logger.exception("Nieoczekiwany błąd podczas ingestion (misja=%s)", mission.value)
    else:
        logger.info("Zaingestowano item '%s' (misja=%s)", item["id"], mission.value)
