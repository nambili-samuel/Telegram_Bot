# Telegram Knowledge Bot

A full-featured Telegram bot with an integrated knowledge database, ready to deploy on Railway.

## Features

- 🔍 **Smart Search**: Full-text search capabilities using SQLite FTS5
- 📚 **Knowledge Base**: Pre-seeded with tech topics (easily expandable)
- 👥 **User Management**: Track users and their activity
- 📊 **Statistics**: User stats and query analytics
- 🎯 **Interactive UI**: Inline keyboards for easy navigation
- 🔐 **Admin Commands**: Add/manage knowledge entries
- 💾 **SQLite Database**: Lightweight, serverless database

## Quick Start

### 1. Create Your Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the instructions
3. Save your bot token

### 2. Deploy on Railway

#### Option A: Deploy with Railway Button (Easiest)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

1. Click the button above
2. Connect your GitHub account
3. Set environment variables (see below)
4. Deploy!

#### Option B: Manual Deployment

1. Create a new project on [Railway](https://railway.app)
2. Connect your GitHub repository
3. Set environment variables
4. Deploy

### 3. Set Environment Variables in Railway

Go to your Railway project → Variables → Add these:

```
TELEGRAM_BOT_TOKEN=your_token_from_botfather
ADMIN_IDS=your_telegram_user_id
DATABASE_PATH=bot_data.db
```

**How to get your Telegram User ID:**
- Send a message to `@userinfobot` on Telegram
- Or use `@raw_data_bot`

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see main menu |
| `/help` | Show help message with all commands |
| `/search <query>` | Search the knowledge base |
| `/topics` | List all available topics |
| `/stats` | Show your usage statistics |
| `/add <topic> \| <content>` | Add knowledge (admin only) |

## Usage Examples

**Simple search:**
```
User: What is Python?
Bot: [Returns relevant information about Python]
```

**Command search:**
```
/search machine learning
```

**Add new knowledge (admin):**
```
/add Docker | Docker is a platform for containerizing applications...
```

## File Structure

```
telegram-bot/
├── main.py              # Main bot logic
├── database.py          # Database operations
├── knowledge_base.py    # Knowledge base management
├── requirements.txt     # Python dependencies
├── railway.json         # Railway configuration
├── Procfile            # Process configuration
├── .env.example        # Environment variables template
└── README.md           # This file
```

## Database Schema

### Users Table
- `user_id` (PRIMARY KEY)
- `username`
- `first_seen`
- `last_active`

### Knowledge Table
- `id` (PRIMARY KEY)
- `topic`
- `content`
- `keywords`
- `created_at`
- `updated_at`

### Query Logs
- `id` (PRIMARY KEY)
- `user_id` (FOREIGN KEY)
- `query`
- `timestamp`

## Customization

### Adding Initial Knowledge

Edit `knowledge_base.py` → `seed_initial_data()` method:

```python
initial_data = [
    ('Your Topic', 
     'Your content here',
     'keywords, tags, search terms'),
    # Add more entries...
]
```

### Modify Bot Behavior

Edit `main.py` to customize:
- Welcome messages
- Response formats
- Button layouts
- Command handlers

## Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` file from `.env.example`
4. Run the bot:
   ```bash
   python main.py
   ```

## Environment Variables Explained

- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather (required)
- `DATABASE_PATH`: SQLite database file location (optional, defaults to `bot_data.db`)
- `ADMIN_IDS`: Comma-separated Telegram user IDs who can use admin commands

## Troubleshooting

### Bot not responding
- Check if `TELEGRAM_BOT_TOKEN` is set correctly
- Verify the bot is running in Railway logs
- Make sure you've started the bot with `/start`

### Database errors
- Railway provides persistent storage by default
- Database is created automatically on first run
- Check Railway logs for specific error messages

### Admin commands not working
- Verify your user ID is in `ADMIN_IDS`
- User IDs must be integers, comma-separated
- Get your ID from `@userinfobot` on Telegram

## Railway Deployment Tips

1. **Persistent Storage**: Railway provides persistent volumes for SQLite databases
2. **Logs**: Check Railway logs for debugging
3. **Environment Variables**: Always set them in Railway dashboard, not in code
4. **Restarts**: Bot automatically restarts on failure (configured in `railway.json`)

## Extending the Bot

### Add New Commands

```python
async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello!")

# In run() method:
app.add_handler(CommandHandler("mycommand", self.my_command))
```

### Add New Knowledge Categories

Modify the `seed_initial_data()` function in `knowledge_base.py`

### Integrate External APIs

Add API calls in `main.py` or create a new module

## Support

For issues or questions:
1. Check Railway logs first
2. Verify environment variables
3. Test commands in Telegram
4. Review error messages

## License

MIT License - feel free to modify and use for your projects!

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- SQLite with FTS5
- Railway for deployment