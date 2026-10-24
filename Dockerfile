FROM python:3.15.1-alpine3.24@sha256:54448f67d7c31c39e5cdd3ea2d6382395ce142806c284425f8e897d78a0465b3 AS sqlite-builder
WORKDIR /app
RUN apk upgrade --no-cache && apk add --no-cache build-base ca-certificates openssl
COPY sqlite-runtime.json ./
COPY scripts/setup_sqlite_runtime.py scripts/build_sqlite_apk.py ./scripts/
COPY app/__init__.py app/sqlite_runtime.py ./app/
RUN python -I scripts/setup_sqlite_runtime.py
RUN python -I scripts/build_sqlite_apk.py

FROM python:3.15.1-alpine3.24@sha256:54448f67d7c31c39e5cdd3ea2d6382395ce142806c284425f8e897d78a0465b3
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/runtime_bootstrap:/app
WORKDIR /app
RUN apk upgrade --no-cache \
    && addgroup -S -g 10001 autoposter && adduser -S -u 10001 -G autoposter autoposter \
    && mkdir -p /app/data/uploads /app/scripts \
    && chown -R autoposter:autoposter /app/data
COPY requirements.lock.txt sqlite-runtime.json ./
COPY --from=sqlite-builder /app/.autoposter-runtime ./.autoposter-runtime
COPY --from=sqlite-builder /tmp/autoposter-sqlite.apk /tmp/autoposter-sqlite.apk
COPY --from=sqlite-builder /tmp/autoposter-package-keys /tmp/autoposter-package-keys
COPY runtime_bootstrap ./runtime_bootstrap
COPY --chown=autoposter:autoposter alembic.ini .
COPY --chown=autoposter:autoposter migrations ./migrations
COPY --chown=autoposter:autoposter app ./app
COPY --chown=autoposter:autoposter public ./public
RUN python -I -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock.txt \
    && python -I -m pip uninstall -y pip \
    && apk --keys-dir /tmp/autoposter-package-keys --no-network add /tmp/autoposter-sqlite.apk \
    && rm -f /tmp/autoposter-sqlite.apk \
    && rm -rf /tmp/autoposter-package-keys /root/.cache/pip
USER autoposter
RUN --mount=type=bind,source=scripts/probe_native_runtime.py,target=/app/scripts/probe_native_runtime.py,readonly \
    python /app/scripts/probe_native_runtime.py --image
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:8000/api/health', timeout=3); assert response.status == 200"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
