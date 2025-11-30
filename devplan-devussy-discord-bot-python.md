# Devussy Discord Bot — Python Devplan (Interview → Handoff)

## 0. Meta

- **Project name:** devussy-discord-bot
- **Language / stack:** **Python-first**
- **Primary libs:**
  - Discord bot: `discord.py` (or `nextcord` as a drop-in if you prefer)
  - HTTP runner service: `FastAPI` (+ `uvicorn` for serving)
  - Tasks / background work (optional, later): `celery` or simple internal job queue
- **Related repos:**
  - `mojomast/devussy` (core pipeline + web UI)
  - New repo: `mojomast/devussy-discord-bot` (this project)

**Goal:**  
Run the full Devussy 7-stage pipeline (interview → devplan → handoff) from inside Discord, using **only Python** on both sides:

- Python Discord bot
- Python Devussy runner service
- Python glue code to invoke Devussy APIs/CLI and patch artifacts.

---

## 1. High-Level Design

### 1.1 Components (Python Only)

1. **Discord Bot (Python)**
   - Based on `discord.py`.
   - Handles:
     - Slash commands (`/devussy new`, `/devussy run`, `/devussy handoff-next`, etc.).
     - Threads / channels for each project.
     - Dialog-like interview (“interview pipeline” replicated in Discord).

2. **Devussy Runner (Python + FastAPI)**

   Minimal FastAPI service that wraps Devussy:

   - `POST /runs`  
     - Body: interview payload + project config.
     - Behaviour: Build `interview.json`, call Devussy pipeline, return `run_id`.

   - `GET /runs/{run_id}`  
     - Status + stage info.

   - `GET /runs/{run_id}/artifacts`  
     - Returns file list and paths/URLs for `devplan.md`, `phase*.md`, `handoff.md`, etc.

3. **Artifact Storage (Filesystem, Python I/O)**

   - Simple initial layout:

     ```text
     runs/
       <project_id>/
         devplan.md
         handoff.md
         phase1.md
         phase2.md
         ...
         logs/
           pipeline.log
     ```

   - Accessed by both:
     - Devussy Runner (writes)
     - Discord bot (reads/modifies via Python filesystem APIs).

4. **LLM Adapter (Python)**

   - Python module that abstracts over:
     - Requesty / z.ai / other OpenAI-compatible endpoints.
   - Exposes functions like:

     ```python
     async def run_handoff_task(
         project_id: str,
         handoff_text: str,
         devplan_chunk: str,
         phase_chunk: str,
         provider: str,
         model: str
     ) -> str:
         ...
     ```

5. **Persistence / Config**

   - Start with:
     - `sqlite3` via `SQLAlchemy` or `databases` library.
   - Tables (or equivalent dataclasses + simple ORM):
     - `projects`
     - `runs`
     - `interview_sessions`
     - `guild_config`
     - `llm_profiles`

---

## 2. Directory Layout

Recommended repo layout for a **Python-only** solution:

```text
devussy-discord-bot/
  README.md
  pyproject.toml         # or setup.cfg + setup.py / requirements.txt
  .env.example
  src/
    bot/
      __init__.py
      main.py            # discord bot entrypoint
      commands/
        devussy.py       # slash commands + interview flows
      models.py          # pydantic/dataclasses for project/run/session
      storage.py         # wrapper around DB + filesystem
      llm_adapter.py     # Requesty/z.ai integration
      handoff_agent.py   # logic to read/write devplan/phase/handoff
    runner/
      __init__.py
      main.py            # FastAPI app (uvicorn entrypoint)
      devussy_adapter.py # calls into devussy repo
      models.py          # pydantic models for HTTP API
  runs/                  # default output (gitignored)
  tests/
    test_interview.py
    test_runner_api.py
    test_handoff_agent.py
```

---

## 3. Dependencies & Environment

### 3.1 Python Versions & Tools

- **Python:** 3.11+ recommended.
- **Core dependencies:**

  ```toml
  # pyproject.toml (example)
  [project]
  name = "devussy-discord-bot"
  requires-python = ">=3.11"

  [project.dependencies]
  discord.py = "^2.4.0"
  fastapi = "^0.115.0"
  uvicorn = "^0.30.0"
  httpx = "^0.27.0"
  pydantic = "^2.8.0"
  python-dotenv = "^1.0.1"
  sqlalchemy = "^2.0.0"
  aiosqlite = "^0.20.0"
  # plus whatever Devussy requires
  ```

- Devussy itself:
  - Local dev:

    ```bash
    # from devussy-discord-bot/
    pip install -e ../devussy
    ```

  - Or via PyPI if/when published.

### 3.2 .env Configuration

Example `.env`:

```env
DISCORD_TOKEN=your_discord_bot_token_here
DEVUSSY_RUNNER_URL=http://localhost:8000
DEVUSSY_RUNS_ROOT=./runs

LLM_DEFAULT_PROVIDER=requesty
LLM_DEFAULT_MODEL=claude-3.5-sonnet
LLM_REQUESTY_API_KEY=sk-...
LLM_ZAI_API_KEY=sk-...

DATABASE_URL=sqlite+aiosqlite:///./devussy_bot.db
```

---

## 4. Detailed Phases (Python Implementation Roadmap)

### Phase 1 — Python Project Bootstrap

**Goal:** Python repo with a minimal Discord bot and basic config.

Tasks:

- [ ] Initialize `pyproject.toml` and `src/` layout.
- [ ] Add `discord.py` bot entrypoint at `src/bot/main.py`:
  - Register `/ping` and `/devussy version` commands.
- [ ] Load `.env` with `python-dotenv`.
- [ ] Add minimal logging setup.
- [ ] Confirm bot can run locally and respond in a sandbox channel.

Example `src/bot/main.py` (sketch):

```python
import os
import logging
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@tree.command(name="ping", description="Check if the bot is alive.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong from devussy-bot (python)!")

@client.event
async def on_ready():
    logging.info(f"Logged in as {client.user} (id={client.user.id})")
    await tree.sync()
    logging.info("Commands synced.")

if __name__ == "__main__":
    token = os.environ["DISCORD_TOKEN"]
    client.run(token)
```

---

### Phase 2 — Devussy Runner Service (FastAPI, Python)

**Goal:** HTTP wrapper around Devussy pipeline, written in Python.

Tasks:

- [ ] Create `src/runner/main.py` with FastAPI app:

  ```python
  from fastapi import FastAPI, HTTPException
  from .models import RunRequest, RunStatus, ArtifactList
  from .devussy_adapter import start_run, get_run_status, get_artifacts

  app = FastAPI()

  @app.post("/runs", response_model=RunStatus)
  async def create_run(req: RunRequest):
      return await start_run(req)

  @app.get("/runs/{run_id}", response_model=RunStatus)
  async def read_run(run_id: str):
      status = await get_run_status(run_id)
      if status is None:
          raise HTTPException(status_code=404, detail="Run not found")
      return status

  @app.get("/runs/{run_id}/artifacts", response_model=ArtifactList)
  async def read_artifacts(run_id: str):
      artifacts = await get_artifacts(run_id)
      if artifacts is None:
          raise HTTPException(status_code=404, detail="Run not found")
      return artifacts
  ```

- [ ] Implement `devussy_adapter.py` to:
  - Build `interview.json` under `runs/<project_id>/`.
  - Call Devussy pipeline via:
    - Either a Python API if exposed by the repo, or
    - `subprocess.run(["python", "-m", "src.cli", ...])` with appropriate args.
  - Track `run_id` and stage-by-stage status in a small sqlite DB or JSON file.

- [ ] Add CLI to start the runner:

  ```bash
  uvicorn src.runner.main:app --reload --host 0.0.0.0 --port 8000
  ```

---

### Phase 3 — Discord Interview Orchestration (Python)

**Goal:** Mirror Devussy interview questions via Discord.

Tasks:

- [ ] Define an **InterviewSession** model (pydantic/dataclass) with at least:

  ```python
  class InterviewSession(BaseModel):
      id: str
      project_id: str
      guild_id: int
      channel_id: int
      user_id: int
      state: Literal["pending", "collecting", "ready", "cancelled"]
      answers: dict[str, str]
  ```

- [ ] Implement storage helpers in `src/bot/storage.py`:
  - `create_interview_session(...)`
  - `update_answer(session_id, field, value)`
  - `mark_ready(session_id)`
  - `get_active_session_for_user(...)`

- [ ] Implement `/devussy new` command:

  - Creates:
    - A new `project_id`.
    - A new thread channel (`discord.TextChannel.create_thread`).
    - A new `InterviewSession` in DB.
  - Sends the **first interview question** in the thread.

- [ ] Implement a simple Q&A loop:

  - Each answer message is captured by an event handler in that thread.
  - The handler:
    - Maps the answer to a field (e.g., `goal`, `users`, `stack`, `constraints`).
    - Saves it, then sends the next question.
  - When all required fields are answered:
    - Mark `state = "ready"`.
    - Present a summary of answers.
    - Offer a button or `/devussy run` to launch the pipeline.

---

### Phase 4 — Connect Interview → Devussy Runner (Python)

**Goal:** Trigger Devussy and surface results.

Tasks:

- [ ] Implement `src/bot/runner_client.py` (using `httpx`):

  ```python
  import httpx
  from .models import RunRequest, RunStatus, ArtifactList

  async def create_run(base_url: str, req: RunRequest) -> RunStatus:
      async with httpx.AsyncClient() as client:
          resp = await client.post(f"{base_url}/runs", json=req.model_dump())
          resp.raise_for_status()
          return RunStatus(**resp.json())
  ```

- [ ] On `/devussy run`:
  - Fetch the interview session.
  - Validate required fields are present.
  - Build a `RunRequest` pydantic model containing interview data and `project_id`.
  - Call Devussy Runner `POST /runs`.
  - Store `run_id` in `projects` table.

- [ ] Implement a background task (within bot process) for polling:
  - Periodically check `GET /runs/{run_id}`.
  - When status moves to `completed`:
    - Call `/runs/{run_id}/artifacts`.
    - Use Python file I/O to read `devplan.md`, `handoff.md`, `phase*.md`.
    - Upload `devplan.md` and `handoff.md` as attachments in the project thread.
    - Post a summary: complexity, phases, etc.

---

### Phase 5 — Handoff Agent (Circular Development) in Python

**Goal:** Have a Python module that reads `handoff.md`, runs an LLM, and patches files.

Tasks:

- [ ] Implement `src/bot/handoff_agent.py`:

  - Functions:

    ```python
    async def load_handoff(project_id: str) -> str: ...
    async def select_target_section(handoff_text: str) -> HandoffTask: ...
    async def load_context_for_task(task: HandoffTask) -> tuple[str, str]: ...
    async def apply_llm_update(
        project_id: str,
        task: HandoffTask,
        llm_output: str
    ) -> None: ...
    ```

- [ ] Implement `src/bot/llm_adapter.py`:

  - Use `httpx` to call Requesty / z.ai with an OpenAI-style payload.
  - Environment-driven configuration for:
    - Provider
    - Base URL
    - Model
    - API key(s).

- [ ] `/devussy handoff-next` command:

  1. Locate project and verify artifacts exist in `runs/<project_id>/`.
  2. Read `handoff.md` and parse the current instruction.
  3. Load relevant `devplan.md` and `phaseN.md` slices.
  4. Construct a prompt:

     """python
     system_prompt = "You are a Devussy Circular Development agent..."
     user_prompt = f"""
     Current task from handoff.md:
     {{task_text}}

     Relevant part of devplan.md:
     {{devplan_chunk}}

     Relevant part of phase file:
     {{phase_chunk}}

     Please update ONLY the specified sections, following Devussy's rules...
     """
     """

  5. Call `llm_adapter.run_handoff_task(...)`.
  6. Apply changes:
     - Carefully patch the specific section(s) using Python string ops or a small markdown AST helper.
  7. Update `handoff.md` for the next task.
  8. Post a summary message in the thread with a brief diff.

---

### Phase 6 — Persistence, Multi-Guild Support & Admin Commands (Python)

**Goal:** Use the same Python DB layer to support multiple guilds/projects.

Tasks:

- [ ] Define SQLAlchemy models:

  - `GuildConfig`
  - `Project`
  - `Run`
  - `InterviewSession`
  - `LLMProfile`

- [ ] Add admin-only commands:

  - `/devussy admin set-provider`
  - `/devussy admin set-model`
  - `/devussy admin set-max-runs`
  - Permissions:
    - Restrict to users with `manage_guild` or a configured role.

- [ ] Per-guild defaults resolved by Python helper:

  ```python
  async def get_guild_llm_profile(guild_id: int) -> LLMProfile:
      # fall back to global defaults if none configured
  ```

- [ ] Add cleanup scripts:
  - Python job to clean `runs/` directories older than N days.
  - DB row pruning for finished runs if desired.

---

### Phase 7 — Testing, Observability, Polish (Python)

**Goal:** Python tests and logging so you trust the thing.

Tasks:

- [ ] Unit tests (pytest):

  - `test_interview_flow.py`
  - `test_runner_client.py`
  - `test_handoff_agent.py`
  - `test_llm_adapter.py` (using mocked HTTP endpoints).

- [ ] Integration tests:

  - Spin up FastAPI test client in-process.
  - Simulate a full run from `RunRequest` → generated artifacts fixture.
  - Simulate a `handoff-next` call with a fake LLM response.

- [ ] Logging & metrics:

  - Use Python `logging` to log per-project and per-run IDs.
  - Include stage transitions (“Stage 3 → Stage 4”, etc.).
  - Optionally add Prometheus-style metrics via FastAPI middlewares.

- [ ] UX polish (still all Python-driven):

  - Discord embeds for summaries.
  - Nice status messages (complexity, phases, risks).
  - Short “HUD” snippet pinned to thread topic.

---

## 5. Step-by-Step “First Working Slice” (Python Only)

1. **Get the Discord bot running** (`/ping`).
2. **Bring up the FastAPI Devussy runner** and hard-code a simple fake run that just writes dummy `devplan.md` + `handoff.md`.
3. Wire `/devussy run` → `POST /runs` → `GET /runs/{id}` → upload dummy artifacts.
4. Replace dummy run with real Devussy call via `devussy_adapter.py`.
5. Implement minimal `/devussy new` + interview flow that feeds into `/devussy run`.
6. Implement a barebones `/devussy handoff-next` that:
   - Reads `handoff.md`,
   - Calls a fake LLM,
   - Writes a trivial change to a phase file,
   - Posts a summary to Discord.
7. Swap fake LLM with real provider via `llm_adapter.py`.

Once that works, you’ll have **end-to-end Devussy → Discord** in pure Python, and you can iterate on prompts + UX from there.
