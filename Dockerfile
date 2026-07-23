# python:3.11-slim
FROM python@sha256:5f1cdbcab9a50594a79502dd73e885456d2a2fc31f1a1fa18484815b37ee9152

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
