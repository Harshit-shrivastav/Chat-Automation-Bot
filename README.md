# Telegram AI Chat Automation Bot

A Telegram bot that provides AI-powered responses using OpenAI-compatible APIs. Supports both direct messages and Telegram Business integration.

## Features

- AI-powered responses using OpenAI-compatible APIs
- Telegram Business chat automation (reply on behalf of user)
- Persistent memory and user info storage (SQLite/PostgreSQL)
- Admin panel with inline keyboard controls
- Automatic memory extraction from conversations
- Message deduplication
- Configurable via environment variables

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py`

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| BOT_TOKEN | Telegram bot token from @BotFather | - |
| API_KEY | Your AI API key | - |
| BASE_URL | API base URL | https://api.openai.com/v1 |
| MODEL | Model to use | gpt-4o-mini |
| DATABASE_URL | PostgreSQL URL (optional) | SQLite default |

## Admin Commands

- `/admin` or `/settings` - Open admin panel
- `*` (trigger) - Toggle bot response for current chat

## License

MIT
