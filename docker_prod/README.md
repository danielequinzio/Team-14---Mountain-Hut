# Docker (prod)

Runs the app from the **published images on Docker Hub**. Nothing is built here: Compose
downloads the images and starts them. The images are multi-arch (amd64 + arm64), so Docker picks
the right one for your machine. To build and publish the images, see [BUILD.md](BUILD.md).

| Service    | Image                                 | URL                   |
|------------|---------------------------------------|-----------------------|
| `frontend` | `maaari401/mountain-hut-14:frontend`  | http://localhost:5173 |
| `backend`  | `maaari401/mountain-hut-14:backend`   | http://localhost:8000 |

API docs (Swagger): http://localhost:8000/docs

## First setup

1. Install Docker Desktop and keep it running.
2. Get the `secrets.txt` file from a teammate and copy it into this folder, as
   `docker_prod/secrets.txt`:

   ```bash
   cp /path/to/secrets.txt docker_prod/secrets.txt
   ```

   It holds the SMTP (Gmail) password, on a single line. `secrets.txt` is gitignored, so
   **never commit it** and never paste the password into `docker-compose.yml`.
   Compose won't start without this file.

## Run

Run all commands from the `docker_prod/` folder.

```bash
docker compose up -d           # download the images (if needed) and start in the background
docker compose ps              # check that both containers are running
docker compose logs -f backend # follow the logs of one service
docker compose down            # stop and remove the containers (data is kept)
```

Then open http://localhost:5173.

`pull_policy: always` is set on both services, so every `docker compose up` checks Docker Hub and
downloads a newer image if one was published. To only update the images without starting them:
`docker compose pull`.

## Login credentials

With `SEED_DATA: "true"` (the default in the compose file), the backend fills an **empty**
database with sample data on first start. Log in with the **email** and password:

| Role     | Email                          | Password   |
|----------|--------------------------------|------------|
| Warden   | luca.bonetti@rifugio.example   | `warden`   |
| Employee | giulia.ferrero@rifugio.example | `employee` |
| Hiker    | anna.rossi@mail.example        | `hiker`    |
| Hiker    | paolo.bianchi@mail.example     | `hiker`    |

The sample data is only added when the database has no users. To get it back, reset the
database (see below).

## Data

The SQLite database is saved on your machine in `data/db/MountainHut.db`, so it survives
restarts and image updates. The folder is gitignored.

To start from a clean database:

```bash
docker compose down
rm -rf data/db
docker compose up -d
```

## Emails

The backend sends **real emails** through Gmail (`mountainhut14@gmail.com`). There is no Mailpit
in this setup. The password is read from `secrets.txt` when the backend starts: if the file is
wrong, emails fail to send.

## Configuration

The backend settings are environment variables in `docker-compose.yml`. Change them there and run
`docker compose up -d` again to apply them. The only secret, `SMTP_PASSWORD`, is kept in
`secrets.txt`: Compose mounts it as `/run/secrets/smtp_password` and the backend's start command
exports it as `SMTP_PASSWORD`.

The frontend calls the API at `http://localhost:8000`. That URL is baked into the frontend image
when it is built, so it **can't** be changed from this compose file: keep the backend on port 8000.
