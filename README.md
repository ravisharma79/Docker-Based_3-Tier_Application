# 🐳 Docker-Based 3-Tier Application
**FiftyFive Technologies — DevOps Intern Assessment**

---

## 1. Setup Instructions

### Prerequisites
- Docker Engine 24+
- Docker Compose plugin (`sudo apt-get install -y docker-compose-plugin`)

### Single command to run everything

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-folder>

# Create your .env file from the example
cp .env.example .env

# Build and start all services
docker compose up --build
```

> ⚠️ Do NOT use `docker compose up --build` if port 80 is already in use on your machine.
> In that case, set `FRONTEND_PORT=8080` in your `.env` file before running.

---

## 2. Architecture Diagram

```
                        ┌─────────────────────────────────────────────────────┐
                        │           Docker Network: threetier_network          │
                        │                                                      │
  Browser               │  ┌──────────────────┐              ┌─────────────┐  │
  http://localhost:80 ──┼─▶│  Frontend (Nginx) │──/api/*────▶│   Backend   │  │
                        │  │  nginx:alpine     │  proxy_pass │ python:3.12 │  │
                        │  │  Port: 80         │             │ Port: 5000  │  │
                        │  └──────────────────┘             └──────┬──────┘  │
                        │                                           │ MySQL   │
                        │                                    ┌──────▼──────┐  │
                        │                                    │  Database   │  │
                        │                                    │  mysql:8.0  │  │
                        │                                    │  Port: 3306 │  │
                        │                                    └──────┬──────┘  │
                        └───────────────────────────────────────────┼─────────┘
                                                                     │
                                                          Named Volume: db_data
                                                          (mysql_persistent_data)
```

**Request Flow:**
```
Browser → Nginx :80 → (proxy /api/*) → Flask :5000 → MySQL :3306
```

---

## 3. Explanation

### How the backend waits for MySQL

A **two-layer** approach ensures the backend never crashes permanently if MySQL isn't ready:

**Layer 1 — Compose `depends_on` with healthcheck condition:**
```yaml
depends_on:
  db:
    condition: service_healthy
```
Docker Compose will not start the backend container until MySQL passes its `mysqladmin ping` healthcheck. This prevents premature startup.

**Layer 2 — In-app retry loop (`wait_for_db` in `app.py`):**
```python
def wait_for_db(retries=30, delay=2):
    for attempt in range(retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            conn.close()
            return  # success — proceed to start Flask
        except MySQLError:
            time.sleep(2)  # wait and retry
    raise SystemExit(1)
```
Even if MySQL becomes temporarily unavailable after startup (e.g. a restart), the `/health` endpoint gracefully reports the failure without crashing the backend process.

### How Nginx gets the backend URL dynamically

The backend URL is **never hardcoded** in `nginx.conf`. Instead:

1. `nginx.conf.template` contains `${BACKEND_URL}` as a placeholder
2. At container startup, `envsubst` substitutes the environment variable:
```sh
envsubst '$BACKEND_URL' < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
```
3. In `docker-compose.yml` the value is injected as:
```yaml
environment:
  BACKEND_URL: http://backend:5000
```
Docker's internal DNS resolves `backend` to the backend container automatically — no IP addresses needed.

### How services communicate

All three containers share the custom bridge network `threetier_network`. Services communicate using their **service names** as DNS hostnames:

| From      | To       | Address              |
|-----------|----------|----------------------|
| Browser   | Nginx    | `http://localhost:80`|
| Nginx     | Backend  | `http://backend:5000`|
| Backend   | MySQL    | `db:3306`            |

No container IP addresses are hardcoded anywhere.

---

## 4. Testing Steps

### Access the frontend
Open your browser at: **http://localhost:80**

The page shows a live health dashboard for all three tiers.

### Hit the API via Nginx proxy

```bash
# Backend root endpoint
curl http://localhost/api/

# Expected response:
# {"message": "Backend is running", "status": "ok"}
```

```bash
# Health endpoint — shows DB connection status
curl http://localhost/api/health

# Expected response:
# {"database": "ok", "db_info": "Connected", "status": "ok"}
```

### Check all container statuses
```bash
docker compose ps
```

All three containers should show `healthy`:
```
mysql_db         Up (healthy)
python_backend   Up (healthy)
nginx_frontend   Up (healthy)
```

### View live logs
```bash
docker compose logs -f               # all services
docker compose logs -f backend       # backend only
docker compose logs -f db            # MySQL only
docker compose logs -f frontend      # Nginx only
```

---

## 5. Failure Scenario — MySQL Restart

### How to reproduce
```bash
docker restart mysql_db
```

### What happens and how it recovers

From actual observed logs during testing:

```
10:48:55  GET /health → DB health check FAILED
          "Can't connect to MySQL server on 'db:3306' (111 Connection refused)"

10:49:11  GET /health → DB health check OK
          Automatically reconnected — no manual intervention needed
```

| Time   | Event |
|--------|-------|
| T+0s   | MySQL container stops. All DB connections drop immediately. |
| T+0–16s| `GET /api/health` returns `{"database": "error"}` — backend stays alive, does NOT crash |
| T+~16s | MySQL finishes restarting and accepts connections again |
| T+~16s | Next `/health` call succeeds — `{"database": "ok"}` — fully recovered |

**Recovery time: ~16 seconds** (observed from logs above)

### How it was handled

The backend uses `mysql-connector-python` which opens a **fresh connection per request**. This means:
- No connection pool to drain or reset
- No backend restart needed
- The very next request after MySQL is back automatically succeeds

The `/health` endpoint is designed to **never return 5xx** — even when the DB is down it returns HTTP 200 with `{"database": "error"}`. This prevents the Compose healthcheck from killing the backend container during a DB outage.

### Verify recovery yourself
```bash
# Terminal 1 — watch health in real time
watch -n 2 "curl -s http://localhost/api/health"

# Terminal 2 — restart MySQL
docker restart mysql_db

# Terminal 3 — watch backend logs
docker compose logs -f backend
```

---

## Bonus Features

| Feature | Implementation |
|---------|---------------|
| ⭐ Multi-stage builds | Backend Dockerfile uses a `builder` stage to install dependencies, then copies only the installed packages into a lean `runtime` stage — keeping the final image small |
| ⭐ Non-root USER | Backend runs as `appuser` (non-root). Created via `adduser -S appuser` in the Dockerfile |

---

## Repository Structure

```
.
├── frontend/
│   ├── Dockerfile              # Nginx + envsubst for dynamic BACKEND_URL
│   ├── .dockerignore
│   ├── nginx.conf.template     # Dynamic backend URL via ${BACKEND_URL}
│   └── index.html              # Static frontend with live health dashboard
├── backend/
│   ├── Dockerfile              # Multi-stage build + non-root user
│   ├── .dockerignore
│   ├── app.py                  # Flask API: GET /, GET /health, wait_for_db()
│   └── requirements.txt        # flask, mysql-connector-python
├── docker-compose.yml          # All services, healthchecks, network, volumes
├── .env.example                # Placeholder values — commit this
└── README.md
```

> ⚠️ Never commit `.env` — only `.env.example` is committed to the repository.