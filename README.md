# 🚀 BRRR Bot

A Discord bot that makes weekly coding projects go **BRRRRRRRR**!

## Features

- **📋 Project Management** - Create, track, and archive projects with checklists
- **💡 Idea Pool** - Capture ideas and turn them into projects
- **📅 Weekly Rhythm** - Start weeks, run retros, track progress
- **🧠 Memory System** - The bot remembers things about each user
- **🤖 AI Chat** - Conversational AI powered by Requesty.ai
- **🔄 Bot-to-Bot** - Responds to other bots too!

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your tokens:

```bash
cp .env.example .env
```

Required:
- `DISCORD_TOKEN` - Your Discord bot token
- `REQUESTY_API_KEY` - Your Requesty.ai API key (for LLM features)

Optional:
- `LLM_MODEL` - Model to use (default: `openai/gpt-4o-mini`)
- `DATABASE_PATH` - SQLite database path (default: `data/brrr.db`)

### 3. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to Bot settings:
   - Enable "Message Content Intent"
   - Enable "Server Members Intent"
4. Copy the bot token to your `.env`
5. Go to OAuth2 > URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`, `Create Public Threads`, `Send Messages in Threads`
6. Use the generated URL to invite the bot to your server

### 4. Run the Bot

```bash
python -m src.bot
```

Or on Windows:
```powershell
python -m src.bot
```

## Commands

### Project Commands
| Command | Description |
|---------|-------------|
| `/project start` | Start a new project (opens modal) |
| `/project status` | List all projects |
| `/project info <id>` | View project details |
| `/project archive <id>` | Archive a project |
| `/project checklist add <id> <task>` | Add a task |
| `/project checklist list <id>` | View/toggle tasks |

### Weekly Commands
| Command | Description |
|---------|-------------|
| `/week start` | Post weekly overview |
| `/week retro` | Run retrospective for all projects |
| `/week summary` | Quick progress summary |

### Idea Commands
| Command | Description |
|---------|-------------|
| `/idea add` | Add an idea (opens modal) |
| `/idea quick <title>` | Quick add idea |
| `/idea list` | Browse all ideas |
| `/idea pick` | Turn an idea into a project |
| `/idea random` | Get a random idea |

### Memory Commands
| Command | Description |
|---------|-------------|
| `/memory show` | See what the bot remembers about you |
| `/memory add <key> <value>` | Manually add a memory |
| `/memory forget <key>` | Remove a specific memory |
| `/memory clear` | Clear all your memories |

### Other
| Command | Description |
|---------|-------------|
| `/ping` | Check if bot is alive |
| `/brrr` | Bot status |
| `/help` | Show all commands |
| `/chat <message>` | Direct chat with the bot |

## Chatting with the Bot

You can chat with the bot by:
1. **@mentioning** it in any channel
2. **Replying** to one of its messages
3. Using the `/chat` command

The bot will remember things you tell it (preferences, skills, projects, etc.) and use that context in future conversations.

### Memory System

The bot automatically extracts and saves relevant information about users during conversations:
- Current projects you're working on
- Programming languages you know
- Your interests and preferences
- Timezone and availability
- And more!

You can view and manage these memories with `/memory show`, `/memory forget`, etc.

## Architecture

```
src/
├── bot.py          # Main bot file, event handlers
├── database.py     # SQLite database with aiosqlite
├── llm.py          # Requesty.ai LLM client
└── cogs/
    ├── projects.py # /project commands
    ├── weekly.py   # /week commands
    ├── ideas.py    # /idea commands
    └── chat.py     # Chat + memory commands
```

## Bot-to-Bot Communication

This bot is designed to respond to other bots! Unlike typical Discord bots that ignore bot messages, BRRR Bot will:
- Respond when mentioned by other bots
- Maintain separate memory for each bot it interacts with
- Add context that the message came from a bot

This enables fun multi-bot interactions in your server.

## Development

### Running in Development

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Unix)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m src.bot
```

### Database

The bot uses SQLite for persistence. The database is automatically created on first run. Tables:

- `projects` - Project tracking
- `tasks` - Project checklists
- `ideas` - Idea pool
- `guild_config` - Per-server settings
- `user_memories` - What the bot remembers about users
- `conversation_history` - Recent chat history for context

## License

MIT - Go make it brrrrr! 🏎️
