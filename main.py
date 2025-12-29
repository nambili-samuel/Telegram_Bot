import os
import logging
import random
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from database import Database
from knowledge_base import KnowledgeBase

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURATION
# =========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ ERROR: TELEGRAM_BOT_TOKEN not set")
    exit(1)

# Admin configuration
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set(map(int, ADMIN_IDS_STR.split(','))) if ADMIN_IDS_STR else set()

GROUP_ID_STR = os.environ.get("GROUP_ID", "")
GROUP_ID = int(GROUP_ID_STR) if GROUP_ID_STR else None

# =========================================================
# INTELLIGENT BOT ENGINE
# =========================================================
class NamibiaBot:
    def __init__(self):
        self.db = Database()
        self.kb = KnowledgeBase()
        self.last_activity = {}
        self.welcomed_users = set()
        logger.info(f"🧠 Bot initialized with {len(self.kb.get_all_topics())} topics")
    
    def analyze_message(self, message, user_id, chat_id):
        """Analyze if bot should respond"""
        msg = message.lower().strip()
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Direct mentions - 100%
        if any(x in msg for x in ["@namibiabot", "namibia bot", "hey bot", "hello bot"]):
            return True, "direct_mention"
        
        # Questions - 80%
        question_words = ["what", "how", "where", "when", "why", "who", "which", "can you", "tell me"]
        if "?" in msg or any(msg.startswith(w) for w in question_words):
            return True, "question"
        
        # Greetings - 70%
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "moro"]
        if any(g in msg.split() for g in greetings):
            return random.random() < 0.7, "greeting"
        
        # Namibia mentions - 60%
        if "namibia" in msg or "namibian" in msg:
            return random.random() < 0.6, "namibia_mention"
        
        # Specific topics - 75%
        topics = ["python", "programming", "machine learning", "web development", "api", "database", 
                  "cloud", "git", "security", "mobile", "devops"]
        if any(t in msg for t in topics):
            return random.random() < 0.75, "specific_topic"
        
        # Travel/tech keywords - 50%
        keywords = ["learn", "code", "develop", "build", "create", "how to", "tutorial", "guide"]
        if any(k in msg for k in keywords):
            return random.random() < 0.5, "interest"
        
        return False, None
    
    def generate_response(self, message, response_type):
        """Generate intelligent response"""
        clean_msg = re.sub(r'@[^\s]*', '', message.lower()).strip()
        clean_msg = re.sub(r'(hey|hello)\s+(bot|namibia)', '', clean_msg).strip()
        
        # Search knowledge base
        if clean_msg and response_type in ["direct_mention", "question", "specific_topic", "namibia_mention", "interest"]:
            results = self.kb.search(clean_msg, limit=3)
            if results:
                best = results[0]
                
                response = f"🤔 *{best['topic']}*\n\n"
                response += f"{best['content']}\n\n"
                
                # Add related topics if available
                if len(results) > 1:
                    response += "📚 *Related topics:*\n"
                    for r in results[1:3]:
                        response += f"• {r['topic']}\n"
                    response += "\n"
                
                response += "💡 Use /topics to see all available topics or /menu for categories!"
                return response
        
        # Fallback responses by type
        responses = {
            "direct_mention": [
                "🇳🇦 Yes! What would you like to know?",
                "🦁 I'm here! How can I help you today?",
                "🏜️ At your service! Ask me anything!",
                "🇳🇦 Hello! Ready to help!"
            ],
            "greeting": [
                "👋 Hello! How can I assist you today?",
                "🇳🇦 Hi there! What would you like to know?",
                "👋 Hey! Ready to explore together?",
                "🌟 Greetings! Ask me anything!"
            ],
            "question": [
                "💡 That's interesting! Try asking more specifically or use /menu",
                "🤔 I might have info on that. Try /topics to browse available topics",
                "💭 Good question! Use /menu for organized information",
                "🎯 Try rephrasing or check /topics for what I know about"
            ],
            "namibia_mention": [
                "🌟 Great topic! What would you like to know?",
                "🦁 I have lots to share! Ask away!",
                "🏜️ Fascinating subject! How can I help?",
                "🇳🇦 That's what I'm here for! What interests you?"
            ],
            "specific_topic": [
                "🎯 That's a good topic! Try asking more specifically",
                "📚 I know about that! Use /menu for detailed info",
                "🔍 Interesting! Check /topics for related information",
                "💡 Good choice! Use /menu to explore more"
            ],
            "interest": [
                "🗺️ I can help with that! What specifically interests you?",
                "🎒 Sounds great! Use /menu for organized information",
                "🌅 I'd love to help! Check out /topics",
                "📖 Excellent! Use /menu to explore"
            ]
        }
        
        return random.choice(responses.get(response_type, ["Ask me anything!"]))
    
    def generate_welcome(self, name):
        """Welcome new members"""
        welcomes = [
            f"👋 Welcome {name}! I'm your AI assistant. Ask me anything! 🇳🇦",
            f"🌟 Hello {name}! Great to have you here! Feel free to ask questions! 🦁",
            f"🇳🇦 Welcome {name}! I'm here to help. Use /menu to get started! 🏜️",
            f"🦁 Greetings {name}! I'm your AI guide. Don't hesitate to ask! 🌅"
        ]
        return random.choice(welcomes)

# =========================================================
# INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    def __init__(self, kb):
        self.kb = kb
    
    def main_menu(self):
        """Create main menu with categories"""
        keyboard = [
            [InlineKeyboardButton("💻 Programming", callback_data="cat_programming"),
             InlineKeyboardButton("🤖 AI & ML", callback_data="cat_ai")],
            [InlineKeyboardButton("🌐 Web Dev", callback_data="cat_web"),
             InlineKeyboardButton("💾 Databases", callback_data="cat_database")],
            [InlineKeyboardButton("☁️ Cloud", callback_data="cat_cloud"),
             InlineKeyboardButton("🔐 Security", callback_data="cat_security")],
            [InlineKeyboardButton("📱 Mobile", callback_data="cat_mobile"),
             InlineKeyboardButton("🚀 DevOps", callback_data="cat_devops")],
            [InlineKeyboardButton("📋 All Topics", callback_data="show_all_topics")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def back_button(self):
        """Back to main menu button"""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")
        ]])
    
    def get_category_topics(self, category):
        """Get topics by category with smart matching"""
        category_keywords = {
            "programming": ["python", "code", "programming", "syntax"],
            "ai": ["machine learning", "ai", "artificial intelligence", "algorithms"],
            "web": ["web", "html", "css", "javascript", "frontend", "backend"],
            "database": ["database", "sql", "data", "queries"],
            "cloud": ["cloud", "aws", "azure", "gcp", "infrastructure"],
            "security": ["security", "cybersecurity", "encryption", "authentication"],
            "mobile": ["mobile", "ios", "android", "app"],
            "devops": ["devops", "ci/cd", "automation", "docker", "kubernetes"]
        }
        
        keywords = category_keywords.get(category, [])
        all_topics = self.kb.get_all_topics()
        
        # Find topics matching keywords
        matched = []
        for topic in all_topics:
            topic_lower = topic.lower()
            if any(kw in topic_lower for kw in keywords):
                matched.append(topic)
        
        return matched if matched else all_topics[:5]
    
    def format_category_content(self, category, topics):
        """Format category content"""
        emoji_map = {
            "programming": "💻",
            "ai": "🤖",
            "web": "🌐",
            "database": "💾",
            "cloud": "☁️",
            "security": "🔐",
            "mobile": "📱",
            "devops": "🚀"
        }
        
        emoji = emoji_map.get(category, "📚")
        title = category.replace("_", " ").title()
        
        content = f"{emoji} *{title}*\n\n"
        content += "*Available Topics:*\n\n"
        
        for i, topic in enumerate(topics[:8], 1):
            content += f"{i}. {topic}\n"
        
        if len(topics) > 8:
            content += f"\n_...and {len(topics) - 8} more topics_\n"
        
        content += "\n💡 *Ask me:* Type your question about any topic!"
        content += "\n📖 *Example:* \"Tell me about " + (topics[0] if topics else "Python") + "\""
        
        return content

# =========================================================
# INITIALIZE GLOBAL INSTANCES
# =========================================================
bot = NamibiaBot()
menu = InteractiveMenu(bot.kb)

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    bot.db.add_user(user.id, user.username or "Unknown")
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = """🇳🇦 *Intelligent Knowledge Bot Activated!*

I'm your AI-powered assistant with a comprehensive knowledge base! 🧠

*I can help with:*
• Programming & Development
• AI & Machine Learning
• Web Development
• Cloud Computing
• Cybersecurity
• Mobile Development
• DevOps & More!

*How to use:*
• Ask questions naturally
• Use /menu for organized topics
• Use /topics to see all available topics
• Tag me (@bot) for specific answers
• I'll join conversations naturally!

*Try asking:*
• "What is Python?"
• "Tell me about machine learning"
• "How does cloud computing work?"
• "What is API development?"

*Commands:*
/menu - Interactive categories
/topics - List all topics
/stats - Your statistics
/help - Help information

Let's explore knowledge together! 🚀"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"👋 Hi {user.first_name}!\n\n"
            f"Add me to a group to get started, or ask me questions here!\n\n"
            f"Use /menu to explore topics or just ask me anything! 🚀",
            parse_mode="Markdown"
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu"""
    await update.message.reply_text(
        "🧠 *Knowledge Base Categories*\n\nSelect a category to explore:",
        parse_mode="Markdown",
        reply_markup=menu.main_menu()
    )

async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /topics - list all topics"""
    topics = bot.kb.get_all_topics()
    
    if topics:
        # Group topics in a nice format
        response = "📚 *Available Topics:*\n\n"
        for i, topic in enumerate(topics, 1):
            response += f"{i}. {topic}\n"
            if i % 15 == 0 and i < len(topics):
                response += "\n"
        
        response += f"\n*Total: {len(topics)} topics*\n\n"
        response += "💡 Ask me about any topic!\n"
        response += "📖 Use /menu for organized categories"
    else:
        response = "No topics available. Use /menu to explore!"
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        # Admin stats
        all_users = bot.db.get_all_users()
        total_queries = sum(1 for _ in bot.db.get_popular_queries(1000))
        
        stats = f"""📊 *Bot Statistics (Admin)*

*System:*
• Total users: {len(all_users)}
• Knowledge topics: {len(bot.kb.get_all_topics())}
• Categories: {len(bot.kb.categories) if hasattr(bot.kb, 'categories') else 'N/A'}
• Total queries: {total_queries}

*Status:* ✅ Active and running

*Popular Queries:*
"""
        popular = bot.db.get_popular_queries(5)
        for i, query in enumerate(popular, 1):
            stats += f"{i}. \"{query['query']}\" ({query['count']}x)\n"
        
        await update.message.reply_text(stats, parse_mode="Markdown")
    else:
        # User stats
        user_stats = bot.db.get_user_stats(user_id)
        
        stats = f"""📊 *Your Statistics*

*Activity:*
• Total queries: {user_stats['query_count']}
• Member since: {user_stats['joined_date'][:10] if user_stats['joined_date'] else 'Unknown'}
• Last query: {user_stats['last_query'][:10] if user_stats['last_query'] else 'No queries yet'}

*Available:*
• Knowledge topics: {len(bot.kb.get_all_topics())}

Use /menu to explore topics! 🚀"""
        
        await update.message.reply_text(stats, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    help_text = """🆘 *Help & Information*

*I'm an AI-powered knowledge assistant!*

*I can help with:*
• Programming languages
• Web development
• AI & Machine Learning
• Cloud computing
• Cybersecurity
• Mobile development
• DevOps practices
• And much more!

*How to interact:*
• Ask natural questions
• Use /menu for categories
• Use /topics to browse all topics
• Tag me in groups for specific help

*Example questions:*
• "What is Python programming?"
• "Explain machine learning"
• "How does API development work?"
• "Tell me about cloud computing"

*Commands:*
/menu - Browse by category
/topics - See all topics
/stats - Your statistics
/help - This message
/start - Restart bot

*Tips:*
• Be specific in your questions
• Explore /menu for organized topics
• I respond naturally in conversations
• I can search my knowledge base instantly

Ask me anything! 🚀"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add - admin only"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is admin-only.")
        return
    
    if not context.args or '|' not in ' '.join(context.args):
        await update.message.reply_text(
            "*Usage:* /add <topic> | <content>\n\n"
            "*Example:*\n"
            "`/add Rust Programming | Rust is a systems programming language focused on safety and performance.`",
            parse_mode="Markdown"
        )
        return
    
    text = ' '.join(context.args)
    try:
        topic, content = text.split('|', 1)
        topic = topic.strip()
        content = content.strip()
        
        if topic and content:
            bot.kb.add_knowledge(topic, content)
            await update.message.reply_text(f"✅ Added topic: *{topic}*", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Topic and content cannot be empty.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages intelligently"""
    if update.message.from_user.id == context.bot.id:
        return
    
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    
    # Track message
    bot.db.add_user(user_id, update.effective_user.username or "Unknown")
    
    # Analyze and respond
    should_respond, response_type = bot.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        logger.info(f"Responding to: {message[:50]}... (type: {response_type})")
        response = bot.generate_response(message, response_type)
        
        if response:
            # Natural delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            try:
                # Log the query
                bot.db.log_query(user_id, message)
                
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                logger.info(f"✅ Response sent")
            except Exception as e:
                logger.error(f"Error sending response: {e}")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages"""
    if update.message.text.startswith('/'):
        return
    
    user_id = update.effective_user.id
    message = update.message.text
    
    # Search knowledge base
    results = bot.kb.search(message, limit=3)
    
    if results:
        response = "🔍 *Search Results:*\n\n"
        for i, result in enumerate(results, 1):
            response += f"*{i}. {result['topic']}*\n{result['content']}\n\n"
        response += "💡 Use /menu for more organized browsing!"
    else:
        response = (
            "🤔 I couldn't find specific information about that.\n\n"
            "Try:\n"
            "• Using /menu to browse categories\n"
            "• Using /topics to see all available topics\n"
            "• Rephrasing your question\n\n"
            "I have information on programming, web development, AI, cloud computing, and more!"
        )
    
    bot.db.log_query(user_id, message)
    await update.message.reply_text(response, parse_mode="Markdown")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                continue
            
            if member.id not in bot.welcomed_users:
                welcome = bot.generate_welcome(member.first_name)
                bot.db.add_user(member.id, member.username or "Unknown")
                bot.welcomed_users.add(member.id)
                
                await asyncio.sleep(1)
                await update.message.reply_text(welcome, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_back":
        await query.edit_message_text(
            "🧠 *Knowledge Base Categories*\n\nSelect a category to explore:",
            parse_mode="Markdown",
            reply_markup=menu.main_menu()
        )
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        topics = menu.get_category_topics(category)
        content = menu.format_category_content(category, topics)
        
        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )
    elif data == "show_all_topics":
        topics = bot.kb.get_all_topics()
        
        response = "📚 *All Available Topics:*\n\n"
        for i, topic in enumerate(topics[:20], 1):
            response += f"{i}. {topic}\n"
        
        if len(topics) > 20:
            response += f"\n_...and {len(topics) - 20} more topics_"
        
        response += f"\n\n*Total: {len(topics)} topics*"
        response += "\n\n💡 Ask me about any topic!"
        
        await query.edit_message_text(
            response,
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )

# =========================================================
# MAIN APPLICATION
# =========================================================
def main():
    """Run the bot"""
    logger.info("=" * 60)
    logger.info("🧠 INTELLIGENT KNOWLEDGE BOT")
    logger.info("=" * 60)
    logger.info(f"✅ Knowledge topics: {len(bot.kb.get_all_topics())}")
    logger.info(f"✅ Admins configured: {len(ADMIN_IDS)}")
    logger.info(f"✅ Database initialized")
    logger.info("=" * 60)
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers (order matters!)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('topics', topics_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('add', add_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message))
    
    logger.info("🚀 Bot running... Press Ctrl+C to stop")
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
