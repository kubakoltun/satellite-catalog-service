FROM python:3.12-slim

WORKDIR /app

# Zależności instalowana przed skopiowaniem kodu źródłowego, żeby Docker 
# mógł cacheować  tę warstwę między buildami dopóki pyproject.toml bez zmian
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "satellite_catalog.main:app", "--host", "0.0.0.0", "--port", "8000"]
