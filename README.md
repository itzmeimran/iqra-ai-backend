# GenAI Chat Backend

FastAPI + LangGraph backend for a scalable, local-LLM-first chat app.

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI + Uvicorn |
| Workflow | LangGraph |
| Observability | LangSmith |
| Database | MongoDB (Motor async) |
| Auth | JWT (access + refresh) + Google SSO |
| LLM Runtime | Ollama / LM Studio / vLLM (OpenAI-compat) |
| Password Hashing | bcrypt via passlib |
| Token Counting | tiktoken (cl100k_base) |

---

## Quick Start

### 1. Clone and install
```bash
git clone <repo>
cd genai-backend
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — set MONGODB_URI, JWT secrets, LLM_PROVIDER, etc.
```

### 3. Start a local LLM (choose one)

**Ollama** (recommended):
```bash
ollama serve
ollama pull llama3
```

**LM Studio**: Start server on port 1234, set `LLM_BASE_URL=http://localhost:1234`

**vLLM**:
```bash
python -m vllm.entrypoints.openai.api_server --model mistralai/Mistral-7B-v0.1
```

### 4. Run the backend
```bash
make dev
# or: uvicorn main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register with email + password |
| POST | `/api/auth/login` | Login, receive JWT tokens |
| POST | `/api/auth/google` | Google SSO (pass idToken) |
| POST | `/api/auth/refresh-token` | Refresh access token |
| POST | `/api/auth/logout` | Invalidate refresh token |
| GET | `/api/auth/me` | Get current user profile |

### Chat Sessions
| Method | Path | Description |
|---|---|---|
| POST | `/api/chats` | Create new chat session |
| GET | `/api/chats` | List all sessions |
| GET | `/api/chats/{id}` | Get session + messages |
| PATCH | `/api/chats/{id}` | Rename / change model |
| DELETE | `/api/chats/{id}` | Delete session + messages |

### Messages
| Method | Path | Description |
|---|---|---|
| POST | `/api/chats/{id}/messages` | Send message (blocking) |
| POST | `/api/chats/{id}/messages/stream` | Send message (SSE stream) |
| POST | `/api/chats/{id}/regenerate` | Regenerate last response |

### Usage & Limits
| Method | Path | Description |
|---|---|---|
| GET | `/api/usage` | Today's + monthly usage |
| GET | `/api/usage/limits` | Plan limits + remaining quota |

### Models
| Method | Path | Description |
|---|---|---|
| GET | `/api/models` | List available models |
| POST | `/api/models/select` | Set preferred model |

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Backend health |
| GET | `/api/llm/health` | LLM runtime availability |

---

## LangGraph Workflow

```
validate_token_limit
    ↓ (limit ok)
load_chat_history
    ↓
save_user_message
    ↓
call_llm
    ↓
save_assistant_message
    ↓
update_usage
    ↓
END
```

Limit exceeded → short-circuits to END with 429 error.

---

## Streaming (SSE)

```js
const es = new EventSource('/api/chats/{id}/messages/stream', { ... });
es.onmessage = ({ data }) => {
  const event = JSON.parse(data);
  if (event.type === 'chunk')  appendToUI(event.content);
  if (event.type === 'done')   finalize(event);
  if (event.type === 'error')  handleError(event);
};
```

---

## Plan Limits (defaults)

| Plan | Daily tokens | Monthly tokens | Max chats |
|---|---|---|---|
| free | 10,000 | 100,000 | 20 |
| pro | 100,000 | 2,000,000 | 500 |
| enterprise | 1,000,000 | 50,000,000 | unlimited |

---

## Project Structure

```
app/
  api/          # FastAPI routers (auth, chat, usage, models)
  core/         # config, security, jwt
  db/           # MongoDB Motor client + index setup
  graph/        # LangGraph state, nodes, compiled graph
  middlewares/  # JWT auth dependency
  models/       # Pydantic document models
  schemas/      # Request/response schemas
  services/     # auth, chat, llm, usage services
  utils/        # token_counter, response helpers
  main.py       # FastAPI app + lifespan
main.py         # Uvicorn entry point
```
