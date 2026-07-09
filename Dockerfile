FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

CMD ["sh", "-c", "python -m uvicorn finbot.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]

