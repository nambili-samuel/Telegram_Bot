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
    logger.error("❌ TELEGRAM_BOT_TOKEN not set")
    exit(1)

ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set(map(int, ADMIN_IDS_STR.split(','))) if ADMIN_IDS_STR else set()

# =========================================================
# EVA GEISES - NAMIBIA BOT ENGINE
# =========================================================
class EvaGeisesBot:
    def __init__(self):
        self.db = Database()
        self.kb = KnowledgeBase()
        self.last_activity = {}
        self.welcomed_users = set()
        logger.info(f"🇳🇦 Eva Geises initialized with {len(self.kb.get_all_topics())} Namibia topics")
    
    def get_greeting(self):
        """Get time-appropriate greeting"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        elif 17 <= hour < 21:
            return "Good evening"
        else:
            return "Hello"
    
    def analyze_message(self, message, user_id, chat_id):
        """Analyze if Eva should respond"""
        msg = message.lower().strip()
        self.last_activity[str(chat_id)] = datetime.now()
        
        # 1. Direct mentions - 100%
        mentions = ["@eva", "eva", "hey eva", "hello eva", "hi eva", "bot"]
        if any(mention in msg for mention in mentions):
            return True, "search"
        
        # 2. Questions - 100% (ALWAYS search for questions)
        question_words = ["what", "how", "where", "when", "why", "who", "which", 
                         "can you", "tell me", "explain", "show me", "is", "are", "do", "does"]
        if "?" in msg or any(msg.startswith(w) for w in question_words):
            return True, "search"
        
        # 3. Greetings - 80%
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", 
                    "moro", "greetings", "hallo", "howzit"]
        if any(g in msg.split() for g in greetings):
            return random.random() < 0.8, "greeting"
        
        # 4. Namibia mentions - 85% (search for info)
        if "namibia" in msg or "namibian" in msg:
            return random.random() < 0.85, "search"
        
        # 5. Specific Namibia topics - 90% (ALWAYS search)
        topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", 
                 "desert", "dunes", "fish river", "cheetah", "elephant", "lion", "wildlife",
                 "safari", "namib", "kalahari", "capital", "visa", "currency", "weather"]
        if any(t in msg for t in topics):
            return True, "search"
        
        # 6. Travel keywords - 80%
        travel = ["travel", "tour", "visit", "trip", "vacation", "holiday", "safari", 
                 "destination", "tourist", "booking", "accommodation"]
        if any(w in msg for w in travel):
            return random.random() < 0.8, "search"
        
        # 7. Quiet chat engagement - 30%
        if self.is_chat_quiet(chat_id, minutes=15):
            return random.random() < 0.3, "conversation_starter"
        
        return False, None
    
    def is_chat_quiet(self, chat_id, minutes=15):
        """Check if chat has been quiet"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_activity:
            return True
        
        last_active = self.last_activity[chat_id_str]
        quiet_time = datetime.now() - last_active
        return quiet_time > timedelta(minutes=minutes)
    
    def generate_response(self, message, response_type):
        """Generate Eva's intelligent response"""
        clean_msg = re.sub(r'@[^\s]*', '', message.lower()).strip()
        clean_msg = re.sub(r'(hey|hello|hi)\s+(eva|bot)', '', clean_msg).strip()
        
        # ALWAYS search knowledge base for "search" type responses
        if response_type == "search" and clean_msg:
            results = self.kb.search(clean_msg, limit=3)
            
            if results:
                best = results[0]
                
                response = f"🇳🇦 *{best['topic']}*\n\n"
                response += f"{best['content']}\n\n"
                
                # Add related topics if available
                if len(results) > 1:
                    response += "📚 *Related:*\n"
                    for r in results[1:]:
                        response += f"• {r['topic']}\n"
                    response += "\n"
                
                response += f"💡 *Category: {best['category']}*"
                
                # Add helpful tip
                if random.random() < 0.4:
                    tips = [
                        "\n\n🔍 Ask me anything else about Namibia!",
                        "\n\n📖 Use /menu for more topics!",
                        "\n\n🌟 Want to know more? Just ask!",
                        "\n\n💬 I'm here to help with all Namibia questions!"
                    ]
                    response += random.choice(tips)
                
                return response
            else:
                # No results found - be helpful
                return (
                    "🤔 I searched but couldn't find specific information about that.\n\n"
                    "Try asking about:\n"
                    "• Etosha National Park\n"
                    "• Sossusvlei dunes\n"
                    "• Himba or Herero people\n"
                    "• Windhoek\n"
                    "• Wildlife and safaris\n\n"
                    "Or use /menu to browse all topics! 📚"
                )
        
        # Greeting responses
        greeting = self.get_greeting()
        
        if response_type == "greeting":
            greetings = [
                f"👋 {greeting}! How can I help you explore Namibia today?",
                f"🇳🇦 {greeting}! What would you like to know about Namibia?",
                f"🦁 {greeting}! I'm Eva, your Namibia guide. Ask away!",
                f"🏜️ {greeting}! Ready to discover Namibia?"
            ]
            return random.choice(greetings)
        
        # Conversation starter
        if response_type == "conversation_starter":
            return self.get_conversation_starter()
        
        # Default fallback (should rarely happen)
        return "🇳🇦 Ask me anything about Namibia! Try: \"Where is Namibia?\" or \"Tell me about Etosha\""
    
    def get_conversation_starter(self):
        """Generate conversation starter"""
        starters = [
            "💭 *Question for everyone:* What's your dream Namibia destination?",
            "🦁 *Wildlife talk:* Who has been on a Namibian safari?",
            "🏜️ *Desert discussion:* The Namib Desert is 55-80 million years old! Amazing, right?",
            "👥 *Cultural question:* What do you find most interesting about Namibia's people?",
            "🗺️ *Travel curiosity:* What surprises you most about Namibia?",
            "🌅 *Scenic moment:* Has anyone seen sunrise at Sossusvlei? Breathtaking!",
            "🦓 *Fun fact:* Namibia has the world's largest cheetah population! 🐆",
            "🇳🇦 *Did you know?* Namibia has one of the lowest population densities in the world!"
        ]
        return random.choice(starters)
    
    def generate_welcome(self, name):
        """Welcome new members"""
        greeting = self.get_greeting()
        welcomes = [
            f"👋 {greeting} {name}! I'm Eva Geises, your AI Namibia expert. Feel free to ask me anything! 🇳🇦",
            f"🌟 Welcome {name}! I'm Eva, here to help with all things Namibia! 🦁",
            f"🇳🇦 {greeting} {name}! Ready to explore Namibia together? Ask me anything! 🏜️",
            f"🦓 {greeting} {name}! I'm Eva, your Namibia guide. Don't hesitate to ask questions! 🌅"
        ]
        return random.choice(welcomes)

# =========================================================
# INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    def __init__(self, kb):
        self.kb = kb
    
    def main_menu(self):
        """Create main menu"""
        keyboard = [
            [InlineKeyboardButton("🏞️ Tourism & Travel", callback_data="cat_Tourism"),
             InlineKeyboardButton("📜 History", callback_data="cat_History")],
            [InlineKeyboardButton("👥 Culture & People", callback_data="cat_Culture"),
             InlineKeyboardButton("ℹ️ Practical Info", callback_data="cat_Practical")],
            [InlineKeyboardButton("🦁 Wildlife & Nature", callback_data="cat_Wildlife"),
             InlineKeyboardButton("🚀 Quick Facts", callback_data="cat_Facts")],
            [InlineKeyboardButton("🗺️ Geography", callback_data="cat_Geography"),
             InlineKeyboardButton("📋 All Topics", callback_data="show_all")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def back_button(self):
        """Back button"""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")
        ]])
    
    def format_category(self, category):
        """Format category content"""
        topics = self.kb.get_by_category(category)
        
        emoji_map = {
            "Tourism": "🏞️", "History": "📜", "Culture": "👥",
            "Practical": "ℹ️", "Wildlife": "🦁", "Facts": "🚀",
            "Geography": "🗺️"
        }
        
        emoji = emoji_map.get(category, "📚")
        
        content = f"{emoji} *{category}*\n\n"
        
        if topics:
            content += "*Available Topics:*\n\n"
            for i, topic in enumerate(topics, 1):
                content += f"{i}. {topic['topic']}\n"
            
            content += f"\n💡 *Ask me:* \"Tell me about {topics[0]['topic']}\""
            content += "\n📖 Or select a specific topic from the list!"
        else:
            content += "No topics available in this category yet."
        
        return content

# =========================================================
# INITIALIZE
# =========================================================
eva = EvaGeisesBot()
menu = InteractiveMenu(eva.kb)

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    eva.db.add_user(user.id, user.username or "Unknown")
    
    greeting = eva.get_greeting()
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = f"""🇳🇦 *Eva Geises - Namibia Expert Activated!*

{greeting} everyone! I'm Eva Geises, your AI-powered Namibia assistant! 🦁

*I can help with:*
• Tourism & Travel Planning
• Wildlife & Safari Information
• Cultural Insights & History
• Practical Travel Advice
• Geography & Quick Facts
• And much more about Namibia!

*How to interact with me:*
• Ask questions naturally - I understand context!
• Mention Namibia - I'll join the conversation!
• Use /menu for organized categories
• Use /topics to see all I know
• I respond to greetings and questions!

*Try asking:*
• "What's the best time to visit Namibia?"
• "Tell me about Etosha National Park"
• "What's special about Himba culture?"
• "Where is Sossusvlei?"

*Commands:*
/menu - Browse by category
/topics - List all topics
/stats - Your statistics
/help - Help information

🇳🇦 Let's explore Namibia together! 🏜️"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"👋 {greeting} {user.first_name}!\n\n"
            f"I'm Eva Geises, your Namibia expert! 🇳🇦\n\n"
            f"Add me to a group or ask me anything about Namibia!\n\n"
            f"Use /menu to explore topics! 🦁",
            parse_mode="Markdown"
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu"""
    await update.message.reply_text(
        "🇳🇦 *Namibia Knowledge Categories*\n\nWhat would you like to explore?",
        parse_mode="Markdown",
        reply_markup=menu.main_menu()
    )

async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /topics"""
    topics = eva.kb.get_all_topics()
    
    if topics:
        response = "📚 *All Namibia Topics:*\n\n"
        for i, topic in enumerate(topics, 1):
            response += f"{i}. {topic}\n"
        
        response += f"\n*Total: {len(topics)} topics*\n\n"
        response += "💡 Ask me about any topic!\n"
        response += "📖 Example: \"Tell me about Etosha National Park\""
    else:
        response = "No topics available yet."
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        all_users = eva.db.get_all_users()
        popular = eva.db.get_popular_queries(5)
        
        stats = f"""📊 *Eva Geises Statistics (Admin)*

*System Status:*
• Total users: {len(all_users)}
• Namibia topics: {len(eva.kb.get_all_topics())}
• Categories: {len(eva.kb.get_categories())}
• Status: ✅ Active

*Popular Questions:*
"""
        for i, q in enumerate(popular, 1):
            stats += f"{i}. \"{q['query']}\" ({q['count']}x)\n"
        
        await update.message.reply_text(stats, parse_mode="Markdown")
    else:
        user_stats = eva.db.get_user_stats(user_id)
        
        stats = f"""📊 *Your Statistics*

*Your Activity:*
• Questions asked: {user_stats['query_count']}
• Member since: {user_stats['joined_date'][:10] if user_stats['joined_date'] else 'Unknown'}
• Last query: {user_stats['last_query'][:10] if user_stats['last_query'] else 'Never'}

*Eva's Knowledge:*
• Namibia topics: {len(eva.kb.get_all_topics())}
• Categories: {len(eva.kb.get_categories())}

🇳🇦 Use /menu to explore Namibia! 🦁"""
        
        await update.message.reply_text(stats, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    greeting = eva.get_greeting()
    
    help_text = f"""🆘 *Eva Geises - Help & Information*

{greeting}! I'm Eva, your AI Namibia expert! 🇳🇦

*What I can help with:*
• Tourism destinations & planning
• Wildlife safaris & nature
• Cultural insights & traditions
• Practical travel information
• Historical facts
• Geography & quick facts

*How to talk to me:*
• Ask natural questions - I understand!
• Mention Namibia - I'll join in!
• Greet me - I respond warmly!
• Use /menu for organized topics
• Browse /topics for everything I know

*Example questions:*
• "Good morning! What's Etosha like?"
• "Tell me about Himba people"
• "Best time to visit Namibia?"
• "Where is Sossusvlei?"
• "What currency does Namibia use?"

*Commands:*
/menu - Browse categories
/topics - All topics
/stats - Your statistics
/help - This message
/start - Restart

*My personality:*
I'm friendly, engaging, and love Namibia! I'll:
• Greet you warmly
• Welcome new members
• Join conversations naturally
• Share fascinating facts
• Help plan your journey

🇳🇦 Ask me anything about Namibia! 🦁"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin command only.")
        return
    
    if not context.args or '|' not in ' '.join(context.args):
        await update.message.reply_text(
            "*Usage:* /add <topic> | <content> | <category> | <keywords>\n\n"
            "*Example:*\n"
            "`/add Skeleton Coast | The Skeleton Coast is a haunting stretch of Namibia's coastline | Tourism | coast, skeleton, beach`",
            parse_mode="Markdown"
        )
        return
    
    try:
        parts = ' '.join(context.args).split('|')
        topic = parts[0].strip()
        content = parts[1].strip()
        category = parts[2].strip() if len(parts) > 2 else 'General'
        keywords = parts[3].strip() if len(parts) > 3 else ''
        
        eva.kb.add_knowledge(topic, content, category, keywords)
        await update.message.reply_text(f"✅ Added: *{topic}* to category {category}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages"""
    if update.message.from_user.id == context.bot.id:
        return
    
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    
    eva.db.add_user(user_id, update.effective_user.username or "Unknown")
    
    should_respond, response_type = eva.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        logger.info(f"Eva responding to: {message[:50]}... (type: {response_type})")
        response = eva.generate_response(message, response_type)
        
        if response:
            await asyncio.sleep(random.uniform(0.8, 2.0))
            
            try:
                eva.db.log_query(user_id, message)
                
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                logger.info("✅ Eva responded")
            except Exception as e:
                logger.error(f"Error: {e}")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages"""
    if update.message.text.startswith('/'):
        return
    
    user_id = update.effective_user.id
    message = update.message.text
    
    results = eva.kb.search(message, limit=3)
    
    if results:
        response = "🔍 *Here's what I found:*\n\n"
        for i, r in enumerate(results, 1):
            response += f"*{i}. {r['topic']}*\n{r['content']}\n\n"
        response += "💡 Use /menu for more organized browsing!"
    else:
        response = (
            "🤔 I couldn't find specific information about that.\n\n"
            "Try:\n"
            "• Using /menu to browse categories\n"
            "• Asking about Etosha, Sossusvlei, or Himba people\n"
            "• Rephrasing your question\n\n"
            "🇳🇦 I know about Namibia's tourism, wildlife, culture, and more!"
        )
    
    eva.db.log_query(user_id, message)
    await update.message.reply_text(response, parse_mode="Markdown")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                continue
            
            if member.id not in eva.welcomed_users:
                welcome = eva.generate_welcome(member.first_name)
                eva.db.add_user(member.id, member.username or "Unknown")
                eva.welcomed_users.add(member.id)
                
                await asyncio.sleep(1.5)
                await update.message.reply_text(welcome, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_back":
        await query.edit_message_text(
            "🇳🇦 *Namibia Knowledge Categories*\n\nWhat would you like to explore?",
            parse_mode="Markdown",
            reply_markup=menu.main_menu()
        )
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        content = menu.format_category(category)
        
        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )
    elif data == "show_all":
        topics = eva.kb.get_all_topics()
        
        response = "📚 *All Namibia Topics:*\n\n"
        for i, topic in enumerate(topics, 1):
            response += f"{i}. {topic}\n"
        
        response += f"\n*Total: {len(topics)} topics*"
        response += "\n\n💡 Ask me about any topic!"
        
        await query.edit_message_text(
            response,
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )

# =========================================================
# MAIN
# =========================================================
def main():
    """Run Eva Geises"""
    logger.info("=" * 60)
    logger.info("🇳🇦 EVA GEISES - NAMIBIA EXPERT BOT")
    logger.info("=" * 60)
    logger.info(f"✅ Namibia topics: {len(eva.kb.get_all_topics())}")
    logger.info(f"✅ Categories: {len(eva.kb.get_categories())}")
    logger.info(f"✅ Admins: {len(ADMIN_IDS)}")
    logger.info("=" * 60)
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
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
    
    logger.info("🚀 Eva Geises is now running...")
    
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("🛑 Eva stopped")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
