# Telegram AI Bot

AI-powered Telegram bot with admin panel, memory system, and OpenAI-compatible API support.

## Features

- 🤖 AI-powered responses via OpenAI-compatible API
- 💬 Telegram Business chat support
- 🧠 Persistent memory that learns about users
- ⚙️ Admin panel for bot configuration
- 🔄 Typing indicators while generating responses
- ⏸️ Pause/resume bot functionality

## Setup

1. Clone the repository:
```bash
git clone https://github.com/Harshit-shrivastav/Chat-Automation-Bot.git
cd Chat-Automation-Bot
```

2. Install dependencies:
```bash
pip install -e .
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Run the bot:
```bash
python -m bot
# or
telegram-bot
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | Required |
| `API_KEY` | Your AI API key | Required |
| `BASE_URL` | OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `MODEL` | Model to use | `gpt-4o-mini` |
| `DATABASE_URL` | SQLAlchemy database URL | SQLite (local) |

## Project Structure

```
src/bot/
├── __init__.py          # Package init
├── __main__.py          # Entry point
├── admin.py             # Admin panel handlers
├── bot.py               # Main bot handlers
├── config.py            # Configuration
├── database.py          # Database models
├── memory.py            # Memory management
├── openai_service.py    # AI API integration
└── main.py              # Application entry
```

## Admin Commands

- `/admin` - Open admin panel
- `*` (trigger) - Toggle chat on/off

## License

MIT