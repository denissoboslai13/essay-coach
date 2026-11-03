# One image with everything: the built frontend is served by the backend (app/site.py).

# 1) Build the frontend
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Backend + built frontend
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend \
    DATABASE_URL=sqlite:////data/essay_coach.db \
    COOKIE_SECURE=true
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./frontend

# Run as an unprivileged user; the database lives in the /data volume
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser
EXPOSE 8000
# --proxy-headers: behind the Cloudflare tunnel, read the real scheme and client IP from its headers
CMD ["uvicorn", "app.site:site", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
