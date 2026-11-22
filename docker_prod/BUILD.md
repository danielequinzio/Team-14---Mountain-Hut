# Building and publishing the images

How to build the two images used by `docker_prod/docker-compose.yml` and push them to Docker Hub.
To just **run** the app, see [README.md](README.md): you don't need any of this.

| Image                                | Dockerfile                       | Build context |
|--------------------------------------|----------------------------------|---------------|
| `maaari401/mountain-hut-14:backend`  | `docker_dev/backend.Dockerfile`  | `backend/`    |
| `maaari401/mountain-hut-14:frontend` | `docker_dev/frontend.Dockerfile` | `frontend/`   |

The Dockerfiles live in `docker_dev/` and are shared by the dev and prod setups.

## Before you start

1. Docker Desktop running.
2. Log in to Docker Hub with an account that can push to `maaari401/mountain-hut-14`:

   ```bash
   docker login
   ```

3. Multi-arch builds (amd64 + arm64) need a `buildx` builder with the `docker-container` driver.
   Create it once:

   ```bash
   docker buildx create --name multiarch --driver docker-container --use
   docker buildx inspect --bootstrap
   ```

   Later on, select it again with `docker buildx use multiarch`.

## Build and push

Run these from the **repository root**. `--push` sends the image straight to Docker Hub: a
multi-arch image can't be loaded into your local Docker, so it isn't kept on your machine.

```bash
# backend
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f docker_dev/backend.Dockerfile \
  -t maaari401/mountain-hut-14:backend \
  --push \
  backend

# frontend
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f docker_dev/frontend.Dockerfile \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  -t maaari401/mountain-hut-14:frontend \
  --push \
  frontend
```

`VITE_API_BASE_URL` is written into the frontend's JS at build time. It's the URL the **browser**
uses to reach the API, so it must match where the backend is published (port 8000 in
`docker_prod/docker-compose.yml`). If you change it, you have to rebuild and push the frontend.

Check that both architectures were pushed:

```bash
docker buildx imagetools inspect maaari401/mountain-hut-14:backend
docker buildx imagetools inspect maaari401/mountain-hut-14:frontend
```

## Local test build (no push)

To try an image on your machine without publishing it, build only for your own architecture and
load it into local Docker with `--load`:

```bash
docker buildx build -f docker_dev/backend.Dockerfile  -t maaari401/mountain-hut-14:backend  --load backend
docker buildx build -f docker_dev/frontend.Dockerfile -t maaari401/mountain-hut-14:frontend --load frontend
```

Note: `docker_prod/docker-compose.yml` uses `pull_policy: always`, so `docker compose up` there
would replace these local images with the ones on Docker Hub. To test local builds, use
`docker_dev/` (`docker compose up --build`) instead.

## After publishing

On any machine running the prod setup, from `docker_prod/`:

```bash
docker compose up -d   # pulls the new images and recreates the containers
```
see more on how to run it in [README.md](README.md)

## Notes

- The backend installs `backend/requirements-prod.txt`, not `requirements.txt`. Add new
  runtime dependencies there too.
- What's left out of each image is set in `backend/.dockerignore` and `frontend/.dockerignore`
  (`.env` files, local databases, `node_modules`, `dist`, ...). No secret is baked into the images:
  the SMTP password is passed at runtime from `secrets.txt`.
