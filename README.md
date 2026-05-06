# ShieldComment

![Python](https://img.shields.io/badge/Python-3.9-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3-FF6600?style=flat-square&logo=rabbitmq&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-toxic--bert-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Academic%20Prototype-orange?style=flat-square)
![UPTC](https://img.shields.io/badge/UPTC-Ingeniería%20de%20Sistemas-003087?style=flat-square)

Intelligent comment moderation service with toxicity analysis and user reputation management, built on a distributed asynchronous architecture.

> Academic project developed for the Distributed Systems course at Universidad Pedagógica y Tecnológica de Colombia (UPTC).
> Authors: Oscar Ivan Rojas Cuesta, Julian Camilo Reyes Uribe.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Running the System](#running-the-system)
- [API Reference](#api-reference)
- [Toxicity Classification](#toxicity-classification)
- [Moderation Rules](#moderation-rules)
- [Scaling and Fault Tolerance](#scaling-and-fault-tolerance)
- [Known Limitations and Technical Debt](#known-limitations-and-technical-debt)
- [Database Access](#database-access)

---

## Overview

ShieldComment is a microservice designed to be integrated into any online platform that accepts user-generated comments. It decouples the reception of comments from their analysis using an asynchronous message queue, which keeps the API response time low regardless of how long the AI inference takes.

When a comment is submitted, the API enqueues it immediately and returns a response to the caller. A background worker then picks up the message, runs it through the `unitary/toxic-bert` transformer model, stores the result, and updates the user's offense record. A second worker handles temporary user blocks triggered by repeated violations.

**Core capabilities:**

- Per-comment toxicity scoring via a fine-tuned BERT model
- Three-tier classification: non-toxic, potentially-toxic, toxic
- Automatic temporary blocking with escalating durations
- Admin dashboard for reviewing flagged comments and user reputation
- Horizontally scalable workers and API instances behind a Traefik reverse proxy

---

## Architecture

```
                          +-----------------------+
  External Platform ------>      Traefik           |
                          |  (Reverse Proxy / LB)  |
                          +-----------+-----------+
                                      |
                          +-----------v-----------+
                          |     ShieldComment API  |
                          |     (FastAPI / Uvicorn)|
                          +-----------+-----------+
                                      |
                          +-----------v-----------+
                          |       RabbitMQ         |
                          |  comment_analysis_queue|
                          |  user_block_queue      |
                          +-----------+-----------+
                                      |
               +-----------------------+---------------------+
               |                                             |
   +-----------v-----------+               +----------------v-----------+
   |   Analysis Worker(s)  |               |    Block Worker(s)         |
   |  (toxic-bert inference)|               |  (user state update)      |
   +-----------+-----------+               +----------------+-----------+
               |                                             |
               +------------------+  +-----------------------+
                                  |  |
                          +-------v--v-------+
                          |    PostgreSQL     |
                          |   (shielddb)      |
                          +------------------+
```

**Data flow:**

1. A platform sends a POST request to `/api/v1/comments/` via Traefik.
2. The API saves the comment to the database and publishes a message to `comment_analysis_queue`.
3. An Analysis Worker consumes the message, runs inference with `unitary/toxic-bert`, stores the result, and updates the user's offense counter.
4. If the user's offense threshold is reached, the worker publishes a message to `user_block_queue`.
5. A Block Worker consumes that message and sets `is_blocked = true` and `blocked_until` on the user record.
6. Administrators can inspect flagged comments and user histories through the dashboard at `/`.

---

## Tech Stack

| Layer            | Technology                          |
|------------------|-------------------------------------|
| API Framework    | FastAPI 0.95 + Uvicorn              |
| ORM              | SQLAlchemy 2.0 (async)              |
| Database         | PostgreSQL 13                       |
| Message Broker   | RabbitMQ 3 (with management plugin) |
| AI Model         | HuggingFace Transformers — `unitary/toxic-bert` |
| Reverse Proxy    | Traefik (not configured in dev compose, see notes) |
| Containerization | Docker + Docker Compose             |
| Language         | Python 3.9                          |

---

## Project Structure

```
ShieldComment/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── comments.py      # Comment creation and retrieval endpoints
│   │           └── users.py         # User registration and status endpoints
│   ├── workers/
│   │   ├── analysis_worker.py       # Toxicity inference + offense tracking
│   │   └── block_worker.py          # User blocking state machine
│   ├── utils/
│   │   ├── config.py                # Pydantic settings loaded from .env
│   │   ├── queues.py                # Queue name constants
│   │   └── toxicity_analyzer.py     # Fallback keyword-based analyzer (dev only)
│   ├── templates/
│   │   └── index.html               # Admin dashboard (Jinja2)
│   ├── database.py                  # Async SQLAlchemy engine and session factory
│   ├── main.py                      # FastAPI app instantiation and startup
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── rabbitmq.py                  # Connection pool and publish helper
│   └── schemas.py                   # Pydantic request/response schemas
├── scripts/
│   └── init_db.py                   # Optional manual DB initialization script
├── frontend/                        # Placeholder for a separate frontend (unused)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.exapmple                    # Local environment variables (example)
```

---

## Getting Started

### Prerequisites

- Docker >= 20.10
- Docker Compose >= 2.0
- 4 GB of free RAM (the `unitary/toxic-bert` model requires approximately 1.5 GB on first load)
- An internet connection on first run so the model can be downloaded from HuggingFace Hub

### Environment Configuration

Copy the provided example and adjust values as needed:

```bash
cp .env.example .env
```

The `.env` file must define the following variables:

```env
# RabbitMQ
RABBITMQ_USER=shielduser
RABBITMQ_PASSWORD=shieldpass
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672

# PostgreSQL
POSTGRES_USER=shielduser
POSTGRES_PASSWORD=shieldpass
POSTGRES_DB=shielddb
POSTGRES_HOST=db
POSTGRES_PORT=5432

# API
API_HOST=0.0.0.0
API_PORT=8000
```

> **Security note:** The `.env` file is committed in this repository as a convenience for local development and academic evaluation. In any non-academic deployment, this file must be added to `.gitignore` and secrets must be managed through a vault or the deployment platform's secret injection mechanism. See [Known Limitations](#known-limitations-and-technical-debt) for a full discussion.

### Running the System

```bash
# Build images and start all services
docker compose up --build

# Or run in detached mode
docker compose up --build -d

# Follow logs for the analysis worker specifically
docker compose logs -f analysis_worker

# Scale analysis workers to 3 instances
docker compose up --scale analysis_worker=3
```

The first startup will take several minutes because Docker must pull the base images and the `unitary/toxic-bert` model weights (~440 MB) will be downloaded from HuggingFace Hub when the analysis worker initializes.

**Service endpoints after startup:**

| Service               | URL                          |
|-----------------------|------------------------------|
| REST API              | http://localhost:8000        |
| Swagger UI            | http://localhost:8000/api/docs |
| ReDoc                 | http://localhost:8000/api/redoc |
| Admin Dashboard       | http://localhost:8000/       |
| RabbitMQ Management   | http://localhost:15672       |

---

## API Reference

All endpoints are versioned under `/api/v1/`.

### Create a user

```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com"}' | jq
```

### Submit a comment

```bash
curl -X POST http://localhost:8000/api/v1/comments/ \
  -H "Content-Type: application/json" \
  -d '{"text": "Great article, thanks!", "user_id": 1}' | jq
```

### Retrieve a comment

```bash
curl http://localhost:8000/api/v1/comments/1 | jq
```

### Retrieve the toxicity analysis for a comment

Wait a few seconds after submission for the worker to process the message before calling this endpoint.

```bash
curl http://localhost:8000/api/v1/comments/1/analysis | jq
```

### Check a user's moderation status

```bash
curl http://localhost:8000/api/v1/comments/1/user-status | jq
```

### Submit a toxic comment (to observe automatic blocking)

```bash
curl -X POST http://localhost:8000/api/v1/comments/ \
  -H "Content-Type: application/json" \
  -d '{"text": "You are an idiot", "user_id": 1}' | jq
```

Submit two or more toxic comments in a short window to trigger the automatic block on user 1.

---

## Toxicity Classification

ShieldComment uses [`unitary/toxic-bert`](https://huggingface.co/unitary/toxic-bert), a BERT-based model fine-tuned on the Jigsaw Toxic Comment Classification dataset. The model outputs a probability score between 0 and 1 for several toxicity sub-categories (toxic, severe\_toxic, obscene, threat, insult, identity\_hate).

The Analysis Worker reads the `toxic` label score and maps it to three tiers:

| Score range | Classification      |
|-------------|---------------------|
| 0 – 30      | `non-toxic`         |
| 31 – 70     | `potentially-toxic` |
| 71 – 100    | `toxic`             |

The raw per-label scores are stored in the `analysis_result` JSONB column for full auditability.

> **Model limitation:** `unitary/toxic-bert` was trained predominantly on English text. Its performance on Spanish-language comments is degraded. This is a known trade-off accepted for this academic prototype; a production deployment targeting Spanish content should evaluate alternatives such as `pysentimiento/robertuito-offensive-language` or a multilingual checkpoint.

---

## Moderation Rules

The system applies two independent blocking strategies:

**1. Recent offense window (short-term):**
If a user submits 2 or more toxic or potentially-toxic comments within a 5-minute window, they are blocked for 1 hour immediately. This catches burst harassment.

**2. Cumulative offense escalation (long-term):**
Each toxic or potentially-toxic comment increments the user's `offense_count`. If the count reaches 3 or more and the user is not already blocked, a block is applied with a duration of `(offense_count - 1)` hours. The offense counter resets to 0 if more than 1 hour has passed since the last offense.

Both strategies share the same block mechanism: the Analysis Worker sets `is_blocked = true` and `blocked_until` directly on the User record and publishes a message to `user_block_queue`. The Block Worker then independently confirms and re-applies the block, which provides a degree of redundancy.

---

## Scaling and Fault Tolerance

**Horizontal scaling of workers:**

Because each worker is a stateless consumer reading from a durable RabbitMQ queue, you can run multiple instances in parallel without coordination:

```bash
docker compose up --scale analysis_worker=4 --scale block_worker=2
```

RabbitMQ distributes messages across available consumers using round-robin. The `prefetch_count` is set to 2 per analysis worker channel, meaning each worker holds at most 2 unacknowledged messages at a time, which prevents a single slow worker from starving the queue.

**Message durability:**

- Queues are declared as `durable=True`, so they survive a RabbitMQ restart.
- Messages are published with `DeliveryMode.PERSISTENT`, so they are written to disk before the broker acknowledges publication.
- A dead-letter exchange (`dlx`) is configured on both queues. Messages that exceed the TTL (24 hours) or the queue length limit (10,000) are routed there rather than silently dropped.

**Worker reconnection:**

The Analysis Worker runs inside a `while True` loop with a 10-second sleep on connection failure. If RabbitMQ is temporarily unavailable, the worker will keep retrying indefinitely without crashing the container.

**API scaling:**

Multiple API instances can run behind Traefik, which is included in the architecture but not fully configured in the development `docker-compose.yml`. See [Known Limitations](#known-limitations-and-technical-debt).

---

## Known Limitations and Technical Debt

This section documents intentional shortcuts taken in this academic prototype and explains the rationale. None of these represent gaps in understanding; they are explicit trade-offs made to deliver a working system within the project timeline.

---

### 1. `.env` file is committed to the repository

**What it is:** The `.env` file containing database credentials and RabbitMQ credentials is tracked in Git and therefore visible in the repository.

**Why it exists here:** Academic projects are evaluated by instructors who need to clone and run the system immediately. Requiring them to configure secrets manually would introduce unnecessary friction. The credentials used (`shieldpass`, `shielduser`) are development-only values with no connection to any real infrastructure.

**What the correct approach is:** In a real project, `.env` must be listed in `.gitignore`. Secrets must be injected at deployment time through environment variables provided by the CI/CD platform (GitHub Actions secrets, Railway variables, Render environment config, etc.) or a secrets manager such as HashiCorp Vault or AWS Secrets Manager. A `.env.example` file with placeholder values should be committed instead, serving as documentation of required variables without exposing actual secrets.

---

### 2. CORS is configured with `allow_origins=["*"]`

**What it is:** The FastAPI app accepts cross-origin requests from any domain.

**Why it exists here:** The admin dashboard is served from the same origin as the API, so CORS is not actually exercised in the current setup. The wildcard was added to avoid any browser-side issues during development without spending time on proper origin configuration.

**What the correct approach is:** In production, `allow_origins` must be set to the explicit list of domains that are allowed to call the API. Using `["*"]` with `allow_credentials=True` is also rejected by browsers per the CORS specification, which means this configuration would break any authenticated cross-origin request.

---

### 3. Database tables are created via `Base.metadata.create_all` on startup

**What it is:** The FastAPI `startup` event handler calls `create_all`, which generates the schema from ORM models if the tables do not exist.

**Why it exists here:** It removes the need to run a separate migration step before the first startup, which simplifies the development workflow.

**What the correct approach is:** Schema management in a production application must go through a migration tool such as Alembic (which is already listed in `requirements.txt` but not wired up). `create_all` does not handle schema evolution: if a column is added to a model, it will not be added to an existing table, leading to silent runtime errors. Alembic generates versioned migration scripts that can be applied, rolled back, and committed to version control alongside the code.

---

### 4. Traefik is defined in the architecture but not fully configured in `docker-compose.yml`

**What it is:** The project proposal describes Traefik as the reverse proxy and load balancer, but the compose file exposes the API directly on port 8000 without routing traffic through Traefik.

**Why it exists here:** Traefik configuration (labels, entrypoints, routers, TLS) adds meaningful complexity that was deferred to keep the compose file focused on demonstrating the core distributed components.

**What the correct approach is:** A full Traefik setup would define a `traefik` service using the official image, expose ports 80 and 443, and add Docker provider labels to each service that should be routed. The API container would not expose port 8000 directly; all external traffic would enter through Traefik. This is the configuration required for horizontal scaling to function properly.

---

### 5. The `block_worker` uses `print` instead of structured logging

**What it is:** The Block Worker uses `print()` for output while the Analysis Worker uses the `logging` module.

**Why it exists here:** The Block Worker was implemented later in the development cycle and was not refactored to match the logging standard established in the Analysis Worker.

**What the correct approach is:** All application output should go through the `logging` module configured at the application root. This allows log level control, structured output (JSON logs for log aggregation platforms), and consistent formatting across all components.

---

### 6. The `toxicity_analyzer.py` utility is a keyword-matching stub

**What it is:** `app/utils/toxicity_analyzer.py` contains a hardcoded list of Spanish swear words and a simple counter. It is not used by the production Analysis Worker, which instead loads `unitary/toxic-bert` directly.

**Why it exists here:** It served as a development scaffold to allow endpoint testing before the model integration was complete.

**What the correct approach is:** This file should either be deleted or clearly marked as a testing utility. Having dead code in the repository creates confusion about which path is actually executed.

---

### 7. The `analysis_worker.py` applies the block directly before publishing to `user_block_queue`

**What it is:** When the Analysis Worker determines that a user should be blocked, it writes `is_blocked = true` to the database itself and then publishes a message to `user_block_queue`. The Block Worker then also writes the same block state when it processes that message.

**Why it exists here:** The block was initially written directly by the Analysis Worker for speed. The queue publication was added afterward to demonstrate the second queue, resulting in redundant writes.

**What the correct approach is:** The two operations should be separated cleanly: the Analysis Worker publishes to `user_block_queue` and does not touch the block state directly. The Block Worker is the single owner of that state transition. This enforces clear responsibility boundaries between services.

---

## Database Access

To inspect stored data during development:

```bash
# Open a psql session inside the database container
docker compose exec db psql -U shielduser -d shielddb

# View the most recent comment analyses
SELECT c.id, c.text, ca.classification, ca.toxicity_score, ca.analyzed_at
FROM comments c
JOIN comment_analysis ca ON c.id = ca.comment_id
ORDER BY ca.analyzed_at DESC
LIMIT 10;

# View user block status
SELECT id, username, offense_count, is_blocked, blocked_until
FROM users
ORDER BY offense_count DESC;
```

RabbitMQ Management UI is available at http://localhost:15672 using the credentials defined in `.env` (`shielduser` / `shieldpass` by default).

---

## Licencia

Este proyecto se distribuye bajo la **Licencia MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
