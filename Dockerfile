# Stage 1: build React bundle
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend serving compiled frontend
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Mount points — actual content comes from host volume mounts at runtime.
# /data  — SQLite persistence (read-write)
# /logs  — optional external log files (read-only)
# /claude — host ~/.claude directory (read-only)
# /codex  — host ~/.codex directory (read-only)
RUN mkdir -p /data /logs /claude /codex

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/usage.db \
    CLAUDE_CODE_DIR=/claude \
    CODEX_DIR=/codex \
    LOG_DIR=/logs

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
