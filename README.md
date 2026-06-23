# Petopia Chat Service

A real-time chat microservice for the Petopia pet adoption platform, built with **Python FastAPI**, **MongoDB**, and **Redis**.

It runs independently from the main ASP.NET Core backend and reuses the same JWT access tokens for authentication — no separate login flow needed.

## Features

- 1-on-1 and group conversations
- Real-time delivery via WebSocket + Redis Pub/Sub
- Message reactions, replies, forwarding, and soft-delete
- Cursor-based pagination for conversations and message history
- Read receipts

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.9+) |
| Real-time | WebSocket + Redis Pub/Sub |
| Database | MongoDB 7 (Motor async driver) |
| Auth | JWT HS256 — shared secret with Petopia.Backend |

---

## Prerequisites

- Python 3.9+
- Docker (for MongoDB)
- Access to the existing **Petopia.Backend Redis** instance (reused for Pub/Sub)

---

## Setup

### 1. Clone and enter the directory

```bash
cd Petopia-Chat
```

### 2. Create a virtual environment and install dependencies

```bash
make install
# or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Must match `Token:AccessTokenKey` in `Petopia.Backend/appsettings.json` |
| `MONGODB_URL` | MongoDB connection URL with credentials |
| `REDIS_URL` | URL of the existing Petopia Redis instance |

### 4. Start MongoDB

```bash
make docker-up
```

This starts a local MongoDB container with the credentials from your `.env` file.

### 5. Run the service

```bash
# Development (auto-reload on file changes)
make dev

# Production
make run
```

The service starts on `http://localhost:8000`.

---

## API Docs

Swagger UI is available at `http://localhost:8000/docs` when the service is running.

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/conversations` | List your conversations (paginated) |
| `POST` | `/conversations` | Create a direct or group conversation |
| `GET` | `/conversations/{id}` | Get conversation details |
| `GET` | `/conversations/{id}/messages` | Get message history (paginated) |
| `POST` | `/conversations/{id}/messages` | Send a message |
| `POST` | `/conversations/{id}/read` | Mark all messages as read |
| `DELETE` | `/messages/{id}` | Soft-delete a message |
| `POST` | `/messages/{id}/reactions` | Add or remove a reaction |
| `POST` | `/messages/{id}/forward` | Forward a message to another conversation |
| `GET` | `/health` | Health check |

### WebSocket

Connect to `/ws?token=<access_token>`.

**Client → Server frames:**

```json
{ "type": "user_typing",   "payload": { "conversation_id": "<id>" } }
{ "type": "messages_read", "payload": { "conversation_id": "<id>" } }
```

**Server → Client events:**

| Event type | Trigger |
|-----------|---------|
| `new_message` | A message was sent in a conversation you participate in |
| `message_deleted` | A message was soft-deleted |
| `reaction_updated` | A reaction was added or removed |
| `user_typing` | Another participant is typing |
| `messages_read` | A participant read your messages |

---

## Make Targets

| Target | Description |
|--------|-------------|
| `make install` | Create `.venv` and install dependencies |
| `make dev` | Run with auto-reload (development) |
| `make run` | Run for production |
| `make docker-up` | Start MongoDB container in background |
| `make docker-down` | Stop and remove MongoDB container |
