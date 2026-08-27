FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY scholarnexus ./scholarnexus
COPY data/fixture ./data/fixture
RUN pip install --no-cache-dir .

ENV SN_PROFILE=offline SN_CORPUS=/app/data/fixture/corpus.jsonl
EXPOSE 8080
CMD ["python", "-m", "scholarnexus.server", "--profile", "offline", "--port", "8080"]
