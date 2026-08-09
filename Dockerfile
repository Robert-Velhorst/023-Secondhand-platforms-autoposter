FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --system autoposter \
    && useradd --system --gid autoposter --home-dir /app autoposter \
    && mkdir -p /app/data/uploads \
    && chown -R autoposter:autoposter /app

COPY --chown=autoposter:autoposter alembic.ini .
COPY --chown=autoposter:autoposter migrations ./migrations
COPY --chown=autoposter:autoposter app ./app
COPY --chown=autoposter:autoposter public ./public

USER autoposter

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:8000/api/health', timeout=3); assert response.status == 200"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
