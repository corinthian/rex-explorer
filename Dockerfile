# python:3.11-slim
FROM python@sha256:8edbf9e42c7fb168b9c523718ed907117e6d2e60f5889c0c499bbda3a787da53

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY lastfm.py pathfind.py server.py ./
COPY static ./static

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8787

VOLUME ["/root/.cache/rex"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8787/', timeout=3)" || exit 1

CMD ["python", "server.py"]
