FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY plexa_server ./plexa_server

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
  && python -m pip install --no-cache-dir --no-deps --no-build-isolation .

RUN useradd --create-home --uid 10001 plexa
USER plexa

EXPOSE 8000

CMD ["uvicorn", "plexa_server.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "none"]
