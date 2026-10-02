# Build from the REPO ROOT so this Dockerfile can also copy ../data:
#   docker build -f backend/Dockerfile -t clinops-backend .
# (docker-compose.yml at the repo root is already configured this way.)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV DATABASE_URL=sqlite:////app/clinops_ai.db

COPY backend/requirements.txt ./
RUN pip install --upgrade pip "setuptools<81" wheel && \
    pip install --no-cache-dir --no-build-isolation -r requirements.txt

COPY backend/app ./app
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
