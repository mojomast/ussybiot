# Next Steps / Handoff

## Purpose
This document tracks the latest development session, including new project management features, GitHub integration, task assignment, and notes functionality.

---

## Summary of Latest Changes (December 3, 2025 - Session 4)

### Dynamic LLM Model Selection Command (`/model`)

**Feature Added:** Password-protected `/model` command to switch between AI models without restarting the bot.

**Implementation Details:**
- New `PasswordModal` class for password input (password: "platypus")
- New `ModelSelectView` class with interactive buttons for model selection
- Models fetched dynamically from Requesty API
- Current model highlighted with success button style
- Supports switching between OpenAI models (GPT-5-nano, GPT-4o, GPT-4o-mini) and other providers

**Key Architecture Decisions:**
- Password-based access (not admin ID) allows any user to try
- Password prompt on initial command AND when clicking model buttons (security)
- `send_modal()` used for initial response, `followup.send()` for subsequent messages
- Model persists in memory (`bot.llm.model`), reverts to default on restart (from `.env` `LLM_MODEL`)

**Files Modified:**
- `src/bot.py`: Added PasswordModal, ModelSelectView classes, model_command function

**Documentation Updated:**
- `README.md`: Added to "New Features" section
- `USAGE_GUIDE.md`: New section explaining how to switch models
- `QUICK_REFERENCE.md`: Added `/model` command reference
- `TECHNICAL_DOCUMENTATION.md`: Added implementation details section

**Bug Fixes in This Session:**
- Fixed `AttributeError: 'InteractionResponse' object has no attribute 'show_modal'` → Changed to `send_modal()`
- Fixed `InteractionResponded` error → Removed `defer()` call after modal (already responded to interaction)

**Available Models:**
- `openai/gpt-5-nano` - Fast, efficient (default)
- `openai/gpt-4o` - Most capable
- `openai/gpt-4o-mini` - Balanced
- Others available via Requesty API

---

## Summary of Latest Changes (December 3, 2025 - Session 3)

### Multi-Round Tool Call Memory Fix (CRITICAL)

**Problem Identified:** When users requested complex multi-step operations (e.g., "create a project with 5 tasks, assign them, and add notes"), the bot would go into an infinite loop, creating multiple projects instead of just one. It was creating 7+ projects for a single request!

**Root Cause:** The `chat_with_tool_results()` function was only passing the CURRENT round's tool calls and results to the LLM. The model had no memory of previous rounds, so it kept "forgetting" that it had already created a project.

**Solution Implemented:**

#### Full Tool History Tracking
- `src/llm.py` - Modified `chat_with_tool_results()` to accept `all_tool_history` parameter containing complete history of all tool rounds
- `src/cogs/chat.py` - Now accumulates all tool calls and results into `tool_history` list and passes it to LLM each round
- The LLM now sees the FULL conversation: Round 1 (create project) → Round 2 (create tasks) → Round 3 (assign) → etc.

#### Tool Result Message Improvements
- `create_project` now returns "SUCCESS: Project created with ID X. DO NOT create another project."
- `create_task` returns "SUCCESS: Task created with ID X in project Y."
- `assign_task` returns "SUCCESS: Task X assigned to user."
- `add_task_note` returns "SUCCESS: Note added to task X."

#### Enhanced Prompt Efficiency Rules
Added critical efficiency rules to the system prompt:
1. NEVER create the same thing twice
2. Track IDs from tool results
3. Call tools in parallel when possible
4. When you see "SUCCESS", that action is DONE
5. After ALL actions complete, STOP and give a summary
6. Includes a concrete workflow example

#### Other Fixes
- Fixed Discord modal placeholder too long error (persona set command)
- Fixed mention stripping to only remove BOT's mention, preserving user mentions
- `assign_task` and `get_user_tasks` now auto-extract numeric IDs from `<@USER_ID>` format
- Database migration added for `assigned_to` column on existing databases
- Max tool rounds set to 20 (sufficient with full history)

---

## Summary of Latest Changes (December 3, 2025 - Session 2)

### Discord Mention Handling & User ID Resolution

**Problem Identified:** When users mentioned others with `@username` (e.g., "assign task to @Mirrowel"), the bot wasn't automatically extracting user IDs from Discord mentions. Users had to manually provide numeric IDs, which was confusing.

**Solution Implemented:**

#### Enhanced Prompt Instructions
- **Discord mention format documentation**: Bot now understands that `<@USER_ID>` format contains the actual numeric user ID
- **Extraction instructions**: Clear guidance on parsing `<@123456789>` patterns to extract user IDs
- **Full tool documentation**: All available tools are now listed in the system prompt with their parameters

#### New Member Lookup Tools
When users reference someone by name without an @mention, the bot can now look them up:
- `lookup_guild_member` - Search for a user by username/display name, returns their ID
- `get_guild_members` - List guild members (useful for random selection when requested)

#### Updated Tool Schemas
- `assign_task` - Enhanced description explaining mention format and user_id extraction
- `get_user_tasks` - Enhanced description with user_id format examples

#### Code Changes
- `src/prompts.py` - Added comprehensive Discord mention handling instructions and full tool documentation to CHAT_CAPABILITIES
- `src/tool_schemas.py` - Added LOOKUP_GUILD_MEMBER_SCHEMA and GET_GUILD_MEMBERS_SCHEMA, updated assign_task and get_user_tasks descriptions
- `src/tools.py` - Added `_lookup_guild_member()` and `_get_guild_members()` implementations
- `src/cogs/chat.py` - Now passes `guild` object in tool context for member lookup

---

## Summary of Latest Changes (December 3, 2025 - Session 1)

### New Project Management Features

#### Task Assignment
- **Task attribution**: Tasks can now be assigned to specific users
- **Database schema**: Added `assigned_to` field to tasks table
- **New tools**: 
  - `assign_task` - Assign a task to a user
  - `unassign_task` - Remove task assignment
  - `get_user_tasks` - Get all tasks assigned to a specific user
- **Methods added**: `assign_task()`, `unassign_task()`, `get_user_tasks()` in database.py

#### Notes System
- **Project notes**: Add notes to projects for tracking decisions, updates, and general information
- **Task notes**: Add notes to tasks for tracking progress, blockers, or additional context
- **Database tables**: 
  - `project_notes` table (id, project_id, author_id, content, created_at)
  - `task_notes` table (id, task_id, author_id, content, created_at)
- **New tools**:
  - `add_project_note` - Add a note to a project
  - `get_project_notes` - Get all notes for a project
  - `add_task_note` - Add a note to a task
  - `get_task_notes` - Get all notes for a task
- **Methods added**: `add_project_note()`, `get_project_notes()`, `add_task_note()`, `get_task_notes()` in database.py

#### GitHub Integration
- **Full GitHub API integration**: Bot can now interact with GitHub repositories
- **New tools**:
  - `github_list_files` - List files in a repository at a specific path
  - `github_read_file` - Read the contents of a file from a repository
  - `github_create_pr` - Create a pull request
  - `github_list_branches` - List all branches in a repository
  - `github_update_file` - Update/create a file in a repository (creates a commit)
  - `github_list_prs` - List pull requests (open, closed, or all)
- **Requirements**: PyGithub library added to requirements.txt
- **Authentication**: Uses GITHUB_TOKEN environment variable

### Previous Features (from earlier session)

#### Concurrency & Race Condition Fixes
- **Per-channel message locking** (`src/bot.py`): Added `_channel_locks` dictionary with `asyncio.Lock` per channel to prevent concurrent message processing in the same channel.
- **Global API lock** (`src/llm.py`): Added `_api_lock` to serialize all LLM API calls, ensuring only one request is in-flight at a time.
- **Startup timestamp filtering** (`src/bot.py`): Bot now tracks `_started_at` timestamp (set in `on_ready`) and ignores any messages created before the bot was fully connected. This prevents processing old cached Discord messages on reconnect.

#### Model Configuration
#### Model Configuration
- **Default model**: `openai/gpt-5-nano` (configurable via `LLM_MODEL` env var)
- **Increased max_tokens**: Changed from 1000 to 2000 to accommodate gpt-5-nano's reasoning tokens
- **Fallback model**: `openai/gpt-4o-mini` used when primary model returns empty content with `finish_reason=length`

---

## Files Modified
- `src/llm.py` — Added `all_tool_history` parameter to `chat_with_tool_results()` for full context preservation across tool rounds
- `src/cogs/chat.py` — Accumulates tool history and passes to LLM; fixed mention stripping to preserve user mentions; fixed modal placeholder length
- `src/prompts.py` — Enhanced CHAT_CAPABILITIES with efficiency rules, workflow examples, and Discord mention handling
- `src/tools.py` — Improved tool result messages with SUCCESS prefix; auto-extract user IDs from mention format
- `src/tool_schemas.py` — Added member lookup schemas, improved tool descriptions
- `src/database.py` — Added migration for `assigned_to` column, project_notes and task_notes tables

---

## Environment Variables
- `DISCORD_TOKEN` — required for Discord connection
- `REQUESTY_API_KEY` — required for LLM calls
- `DATABASE_PATH` — optional, defaults to `data/brrr.db`
- `LLM_MODEL` — optional, defaults to `openai/gpt-5-nano`
- `GITHUB_TOKEN` — **NEW**, optional, required for GitHub integration features (get from https://github.com/settings/tokens)

Example `.env`:
```
DISCORD_TOKEN=your_token_here
REQUESTY_API_KEY=sk-xxxxx
DATABASE_PATH=data/brrr.db
LLM_MODEL=openai/gpt-5-nano
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx
```

---

## How to Run

### Discord Bot
```powershell
python run.py
```

### Local Test Harness (without Discord)
```powershell
python tests/test_local.py
```

### Unit Tests
```powershell
python -m pytest tests/test_llm.py tests/test_tools.py tests/test_chat.py -v
```

### Install New Dependencies
```powershell
pip install -r requirements.txt
```

---

## New Tool Usage Examples

### Task Assignment
```
User: "@brrr assign task 5 to @alice"
Bot: [calls assign_task with task_id=5, user_id=alice's Discord ID]

User: "@brrr show me all tasks assigned to me"
Bot: [calls get_user_tasks with the user's Discord ID]

User: "@brrr unassign task 5"
Bot: [calls unassign_task with task_id=5]
```

### Notes
```
User: "@brrr add a note to project 3: We decided to use React instead of Vue"
Bot: [calls add_project_note with project_id=3, content="We decided to use React instead of Vue"]

User: "@brrr show me notes for task 7"
Bot: [calls get_task_notes with task_id=7]

User: "@brrr add a note to task 12: Blocked by API rate limit, waiting for approval"
Bot: [calls add_task_note with task_id=12, content="..."]
```

### GitHub Integration
```
User: "@brrr list files in owner/repo at docs/"
Bot: [calls github_list_files with repo="owner/repo", path="docs/"]

User: "@brrr read README.md from owner/repo"
Bot: [calls github_read_file with repo="owner/repo", path="README.md"]

User: "@brrr create a PR in owner/repo from feature-branch to main titled 'Add new feature'"
Bot: [calls github_create_pr]

User: "@brrr update the docs in owner/repo, change docs/api.md to include the new endpoint"
Bot: [calls github_update_file with appropriate parameters]

User: "@brrr show me open PRs in owner/repo"
Bot: [calls github_list_prs with repo="owner/repo", state="open"]
```

---

## Architecture Notes

### Database Schema Updates
The database now supports:
1. **Task assignments** via `assigned_to` field (user_id)
2. **Project notes** via dedicated `project_notes` table
3. **Task notes** via dedicated `task_notes` table

### Tool System
- All tool schemas centralized in `src/tool_schemas.py`
- Tool execution logic in `src/tools.py`
- GitHub tools use PyGithub library for API interaction
- All tools include proper error handling and user-friendly responses

### Message Processing Flow
1. `on_message` receives Discord message
2. Check: Is message from self? → skip
3. Check: Is message before `_started_at`? → skip (prevents old message processing)
4. Check: Is bot mentioned, replied to, or "brrr" in content? → proceed
5. Acquire per-channel lock (`_channel_locks[channel_id]`)
6. Call `chat_cog.handle_mention(message)`
7. LLM call (with global `_api_lock` to serialize API requests)
8. If tool_calls returned → execute tools → second LLM call with results
9. Release locks, send response

---

## Known Issues / Caveats
- **GitHub token security**: Make sure GITHUB_TOKEN is kept secure and not committed to version control
- **GitHub API rate limits**: Be aware of GitHub API rate limits (typically 5,000 requests/hour for authenticated requests)
- **File size limits**: GitHub file reading is truncated at 4000 characters to prevent context overflow
- **gpt-5-nano reasoning tokens**: This model uses "reasoning tokens" internally which consume token budget. The 2000 max_tokens setting accommodates this, but very complex requests may still hit limits.

---

## Recommended Next Steps

### Immediate
1. ✅ ~~Add task assignment features~~ (complete)
2. ✅ ~~Add notes system~~ (complete)
3. ✅ ~~Add GitHub integration~~ (complete)
4. Test new features with real Discord interactions
5. Update unit tests to cover new functionality

### Short-term
6. Add GitHub webhook integration for automatic updates
7. Add project templates with pre-defined task structures
8. Implement task dependencies (task X blocks task Y)
9. Add task deadlines and reminders
10. Create slash commands for common operations (e.g., `/task assign`)

### Medium-term
11. Add visualization for project progress (charts, graphs)
12. Implement sprint planning features
13. Add time tracking for tasks
14. Create project analytics and reports
15. Add integration with other services (Jira, Trello, etc.)

---

## Quick Commit Suggestion
```powershell
git add -A
git commit -m "Add task assignment, notes system, and GitHub integration

- Add assigned_to field to tasks table for user attribution
- Add project_notes and task_notes tables with full CRUD operations
- Add 6 new GitHub integration tools (list files, read file, create PR, etc.)
- Add PyGithub dependency for GitHub API access
- Update tool schemas and execution logic for all new features"
```
