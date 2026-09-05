# Containerization

## Default environment

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The default Compose graph is:

```text
db (healthy) -> backend migrations/API (healthy) -> frontend
ollama (healthy) -> ollama-init model pull -> backend
```

PostgreSQL data is stored in `postgres_data`. Ollama models are stored in `ollama_data`. The backend health check requires the database, pgvector HNSW index, and Ollama API to be ready. The Ollama init service pulls `OLLAMA_MODEL` before the backend starts.

The default model is `llama3.2`. The first startup downloads the model and can require several minutes and substantial disk/RAM. The embedding model is downloaded lazily when the application first performs embedding work.

Services expose:

- Frontend: `http://localhost:${FRONTEND_PORT:-3000}`
- Backend: `http://localhost:${BACKEND_PORT:-8000}`
- Ollama: `http://localhost:${OLLAMA_PORT:-11434}`

## Host Ollama alternative

Running Ollama in Docker is reproducible, but can be impractical on Windows machines with limited Docker Desktop memory, slow container storage, or GPU passthrough requirements. In that case, run Ollama on the host:

```powershell
ollama serve
ollama pull llama3.2
```

Set this in `.env`:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

For this alternative, remove the `ollama` and `ollama-init` services from the active Compose file and remove the `ollama-init` dependency under `backend`. Keep the backend health check: it will verify the host Ollama API through `host.docker.internal`.

This alternative is justified only for local development. Production deployments should use a managed inference service or a separately operated Ollama host with explicit capacity, access control, and model lifecycle management.

## Verification

The expected verification commands are:

```powershell
docker compose config
docker compose up --build
docker compose ps
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
```

Startup is considered verified only when `db`, `ollama`, `backend`, and `frontend` report healthy and the backend health response reports `status: ok`. No successful startup result is recorded in this repository until those commands complete in the target environment.




docker compose logs -f backend
How can a product team improve activation?
docker cp "C:\path\to\transcript.md" lennygrowthassistan-backend-1:/tmp/transcript.md
docker compose exec backend python scripts/ingest.py /tmp/transcript.md