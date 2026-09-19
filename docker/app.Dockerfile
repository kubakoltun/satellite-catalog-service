FROM python:3.12-slim

WORKDIR /app

# dependencies are installed before coping source code, so that docker may cache betweend builds
# until pyproject.toml stays the same
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "satellite_catalog.main:app", "--host", "0.0.0.0", "--port", "8000"]
