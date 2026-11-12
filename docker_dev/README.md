# Docker (dev)

Runs the whole app with Docker Compose. There are three containers:

| Service    | What it is                     | URL                        |
|------------|--------------------------------|----------------------------|
| `frontend` | React app (Vite dev server)    | http://localhost:5173      |
| `backend`  | FastAPI API                    | http://localhost:8000      |
| `mailpit`  | Test mail server and web inbox | http://localhost:8025      |

API docs (Swagger): http://localhost:8000/docs

## First setup

1. Install Docker Desktop and keep it running.
2. Get the `secrets.txt` file from a teammate and copy it into this folder, as
   `docker_dev/secrets.txt`:

   ```bash
   cp /path/to/secrets.txt docker_dev/secrets.txt
   ```

   It holds the SMTP password. Don't type the password yourself: always use the shared file.
   `secrets.txt` is gitignored, so **never commit it** and never paste the password into
   `docker-compose.yml`. Compose won't start without this file.

## Usage

Run all commands from the `docker_dev/` folder.

```bash
docker compose up --build      # build and start everything (Ctrl+C to stop)
docker compose up -d --build   # same, in the background
docker compose logs -f backend # follow the logs of one service
docker compose down            # stop and remove the containers (data is kept)
```

Rebuild (`--build`) after changing code or dependencies: the source is copied into the images,
so changes on your machine aren't picked up live.

## Login credentials

With `SEED_DATA: "true"` (the default in the compose file), the backend fills an **empty** database
with sample data on first start. You log in with the **email** and password:

| Role     | Email                          | Password   |
|----------|--------------------------------|------------|
| Warden   | luca.bonetti@rifugio.example   | `warden`   |
| Employee | giulia.ferrero@rifugio.example | `employee` |
| Hiker    | anna.rossi@mail.example        | `hiker`    |
| Hiker    | paolo.bianchi@mail.example     | `hiker`    |

The sample data is only added when the database has no users. To get it back, reset the
database (see below).

## Data

Data is saved in folders on your machine, so it survives restarts and rebuilds:

| Folder           | Content                                    |
|------------------|--------------------------------------------|
| `data/db/`       | SQLite database (`MountainHut.db`)         |
| `data/mailpit/`  | Emails received by Mailpit                 |

To start from a clean database: `docker compose down`, delete `data/db/`, then `docker compose up`.

## Emails

The backend sends **real emails** through Gmail (`mountainhut14@gmail.com`). It reads the
password from `secrets.txt` when it starts. If that file is missing or wrong, no email is sent.

## Configuration

The backend settings are environment variables in `docker-compose.yml`, the same ones as
`backend/.env.example`. The only secret, `SMTP_PASSWORD`, is kept in `secrets.txt`. Compose
mounts that file into the container as `/run/secrets/smtp_password`, and the backend's start
command exports it as `SMTP_PASSWORD`.

The frontend gets `VITE_API_BASE_URL=http://localhost:8000`. The browser makes these calls, so
the URL points to the backend's port on your machine, not to the container name.