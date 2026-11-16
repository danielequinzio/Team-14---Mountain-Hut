FROM python:3.14-slim
LABEL authors="maaari"

WORKDIR /app

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# sqlite db lives in its own folder so docker compose can mount a volume on it
ENV DATABASE_URL=sqlite:////app/db_data/MountainHut.db
RUN mkdir -p /app/db_data
VOLUME /app/db_data

EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
