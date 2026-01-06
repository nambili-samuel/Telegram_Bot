import os
import logging
import random
import re
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, NetworkError
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
# EVA GEISES - NAMIBIA BOT ENGINE WITH REAL ESTATE
# =========================================================
class EvaGeisesBot:
    def __init__(self):
        self.db = Database()
        self.kb = KnowledgeBase()
        self.last_activity = {}
        self.welcomed_users = set()
        self.last_greeting = {}
        self.last_property_post = {}
        logger.info(f"🇳🇦 Eva Geises initialized with {len(self.kb.get_all_topics())} topics")
    
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
        
        response_types = []
        
        # 1. Direct mentions - 100%
        bot_mentions = ["@eva", "eva", "@namibiabot", "namibia bot", "hey bot", "hello bot", "hey eva"]
        if any(mention in msg for mention in bot_mentions):
            response_types.append(("search", 100))
        
        # 2. Questions - 90%
        question_words = ["what", "how", "where", "when", "why", "who", "which", 
                         "can you", "tell me", "explain", "show me", "is", "are", "do", "does"]
        if "?" in msg or any(msg.startswith(w) for w in question_words):
            response_types.append(("search", 90))
        
        # 3. Greetings - 80%
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", 
                    "moro", "greetings", "hallo", "howzit"]
        if any(g in msg.split() for g in greetings):
            response_types.append(("greeting", 80))
        
        # 4. Namibia mentions - 85%
        if "namibia" in msg or "namibian" in msg:
            response_types.append(("search", 85))
        
        # 5. Real estate keywords - 95%
        real_estate_keywords = ["house", "property", "land", "plot", "sale", "buy", 
                               "real estate", "windhoek west", "omuthiya", "okahandja",
                               "bedroom", "bedroomed", "rent", "invest"]
        if any(keyword in msg for keyword in real_estate_keywords):
            response_types.append(("search", 95))
        
        # 6. Specific topics - 90%
        topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", 
                 "desert", "dunes", "fish river", "cheetah", "elephant", "lion", "wildlife",
                 "safari", "namib", "capital", "visa", "currency", "weather"]
        if any(t in msg for t in topics):
            response_types.append(("search", 90))
        
        # 7. Travel keywords - 80%
        travel = ["travel", "tour", "visit", "trip", "vacation", "holiday", 
                 "destination", "tourist", "booking"]
        if any(w in msg for w in travel):
            response_types.append(("search", 80))
        
        # 8. Quiet chat - 30%
        if self.is_chat_quiet(chat_id, minutes=20):
            response_types.append(("conversation_starter", 30))
        
        if response_types:
            response_types.sort(key=lambda x: x[1], reverse=True)
            top = response_types[0]
            if random.random() < (top[1] / 100):
                return True, top[0]
        
        return False, None
    
    def is_chat_quiet(self, chat_id, minutes=20):
        """Check if chat quiet"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_activity:
            return True
        return datetime.now() - self.last_activity[chat_id_str] > timedelta(minutes=minutes)
    
    def should_send_greeting(self, chat_id):
        """Check if should send periodic greeting (every 2 hours)"""
        chat_id_str = str(chat_id)
        now = datetime.now()
        
        if chat_id_str not in self.last_greeting:
            self.last_greeting[chat_id_str] = now
            return True
        
        if now - self.last_greeting[chat_id_str] > timedelta(hours=2):
            self.last_greeting[chat_id_str] = now
            return True
        
        return False
    
    def get_periodic_greeting(self):
        """Get varied time-based greetings"""
        hour = datetime.now().hour
        
        if 5 <= hour < 8:
            greetings = [
                "🌅 *Rise and shine, Namibia lovers!*\n\nWhat's everyone up to today?\n\n📱 Check /menu for Namibia info!",
                "☀️ *Early morning vibes!*\n\nAnyone planning a Namibia adventure?\n\n💡 Use /menu to explore!",
                "🌄 *Good morning, everyone!*\n\nWhat aspect of Namibia interests you most?\n\n📚 Try /menu!"
            ]
        elif 8 <= hour < 12:
            greetings = [
                "☕ *Good morning, Namibia enthusiasts!*\n\nWhat brings you here today?\n\n📱 Use /menu to discover!",
                "🌞 *Morning everyone!*\n\nReady to learn something amazing about Namibia?\n\n💡 Check /menu!",
                "👋 *Good morning!*\n\nAsk me anything about Namibia or use /menu! 🇳🇦"
            ]
        elif 12 <= hour < 17:
            greetings = [
                "🌤️ *Good afternoon, everyone!*\n\nWhat Namibia topic shall we explore?\n\n📱 Use /menu!",
                "☀️ *Afternoon vibes!*\n\nAnyone curious about Namibia wildlife?\n\n🦁 Try /menu → Wildlife!",
                "👋 *Good afternoon!*\n\nI'm here to answer Namibia questions! 🇳🇦\n\n💡 /menu for topics!"
            ]
        elif 17 <= hour < 21:
            greetings = [
                "🌆 *Good evening, Namibia fans!*\n\nHow's everyone doing?\n\n📱 Use /menu to explore!",
                "🌅 *Evening everyone!*\n\nPerfect time to learn about Namibia!\n\n💡 Check /menu!",
                "👋 *Good evening!*\n\nReady for some Namibia facts? 🇳🇦\n\n📚 Try /menu!"
            ]
        else:
            greetings = [
                "🌙 *Good evening, night owls!*\n\nWhat Namibia topic interests you?\n\n📱 Use /menu!",
                "✨ *Hello everyone!*\n\nI'm here if you need Namibia info! 🇳🇦\n\n💡 Try /menu!",
                "🌟 *Evening, travelers!*\n\nAsk me about Namibia anytime!\n\n📚 Use /menu!"
            ]
        
        return random.choice(greetings)
    
    def generate_response(self, message, response_type):
        """Generate Eva's response"""
        clean_msg = re.sub(r'@[^\s]*', '', message.lower()).strip()
        clean_msg = re.sub(r'(hey|hello|hi)\s+(eva|bot|namibia)', '', clean_msg).strip()
        
        # Search knowledge base
        if response_type == "search" and clean_msg:
            results = self.kb.search(clean_msg, limit=3)
            
            if results:
                best = results[0]
                
                response = f"🤔 *Based on your question:*\n\n"
                response += f"**{best['topic']}**\n"
                response += f"{best['content']}\n\n"
                
                # Add related topics
                if len(results) > 1:
                    response += "💡 *Related information:*\n"
                    for r in results[1:]:
                        response += f"• {r['topic']}\n"
                    response += "\n"
                
                response += f"📱 *Use /menu for more topics or ask another question!*"
                return response
            else:
                return (
                    "🤔 I searched but couldn't find specific information about that.\n\n"
                    "Try asking about:\n"
                    "• Etosha National Park\n"
                    "• Sossusvlei dunes\n"
                    "• Himba or Herero people\n"
                    "• Windhoek capital\n"
                    "• Wildlife and safaris\n"
                    "• Real Estate properties\n\n"
                    "📱 Or use /menu to browse all topics!"
                )
        
        # Greeting responses
        greeting = self.get_greeting()
        
        if response_type == "greeting":
            greetings = [
                f"👋 {greeting}! How can I help you explore Namibia today?\n\n📱 Use /menu to browse topics!",
                f"🇳🇦 {greeting}! What would you like to know about Namibia?\n\n💡 Try /menu for categories!",
                f"🦁 {greeting}! I'm Eva, your Namibia guide. Ask away!\n\n📚 Check /menu for all topics!",
                f"🏜️ {greeting}! Ready to discover Namibia?\n\n✨ Use /menu to explore!"
            ]
            return random.choice(greetings)
        
        # Conversation starter
        if response_type == "conversation_starter":
            return self.get_conversation_starter()
        
        return "🇳🇦 Ask me anything about Namibia!\n\n💡 Try: \"Where is Namibia?\" or use /menu"
    
    def get_conversation_starter(self):
        """Generate conversation starter"""
        starters = [
            "💭 *Question for everyone:* What's your dream Namibia destination?\n\n📱 Use /menu to explore destinations!",
            "🦁 *Wildlife talk:* Who has been on safari in Namibia?\n\n🦓 Check /menu → Wildlife for more!",
            "🏜️ *Fun fact:* The Namib Desert is 55-80 million years old!\n\n📚 Use /menu for more Namibia facts!",
            "👥 *Cultural question:* What interests you about Namibia's people?\n\n💡 Try /menu → Culture!",
            "🗺️ *Travel tip:* Best time to visit is May-October!\n\n✈️ Use /menu → Tourism for planning!",
            "🌅 *Amazing:* Sossusvlei has the world's highest dunes!\n\n📖 Discover more with /menu!"
        ]
        return random.choice(starters)
    
    def generate_welcome(self, name):
        """Welcome new members"""
        greeting = self.get_greeting()
        welcomes = [
            f"👋 {greeting} {name}! I'm Eva Geises, your AI Namibia expert.\n\n💡 Ask me anything or use /menu to explore! 🇳🇦",
            f"🌟 Welcome {name}! I'm Eva, here to help with all things Namibia!\n\n📱 Try /menu or ask me questions! 🦁",
            f"🇳🇦 {greeting} {name}! Ready to explore Namibia together?\n\n✨ Use /menu to get started! 🏜️",
            f"🦓 {greeting} {name}! I'm Eva, your Namibia guide!\n\n📚 Check out /menu or ask away! 🌅"
        ]
        return random.choice(welcomes)

# =========================================================
# INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    def __init__(self, kb):
        self.kb = kb
        self.categories = kb.get_categories()
    
    def main_menu(self):
        """Create main menu"""
        keyboard = [
            [InlineKeyboardButton("🏠 Real Estate", callback_data="cat_Real Estate")],
            [InlineKeyboardButton("🏞️ Tourism", callback_data="cat_Tourism")],
            [InlineKeyboardButton("📜 History", callback_data="cat_History")],
            [InlineKeyboardButton("👥 People", callback_data="cat_Culture")],
            [InlineKeyboardButton("ℹ️ Info", callback_data="cat_Practical")],
            [InlineKeyboardButton("🦁 Wildlife", callback_data="cat_Wildlife")],
            [InlineKeyboardButton("🔍 Quick Facts", callback_data="cat_Facts")],
            [InlineKeyboardButton("🗺️ Geography", callback_data="cat_Geography")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_submenu(self, category):
        """Create submenu with individual topic buttons"""
        topics = self.kb.get_by_category(category)
        keyboard = []
        
        if topics:
            # Add each topic as a clickable button
            for i, topic in enumerate(topics):
                topic_name = topic['topic']
                # Truncate long names but keep them readable
                if len(topic_name) > 35:
                    topic_name = topic_name[:32] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📌 {topic_name}", 
                        callback_data=f"topic_{category}_{i}"
                    )
                ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_back")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def back_button(self, category=None):
        """Create back button(s)"""
        if category:
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Category", callback_data=f"cat_{category}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_back")]
            ]
        else:
            keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")]]
        
        return InlineKeyboardMarkup(keyboard)
    
    def format_category(self, category):
        """Format category overview"""
        topics = self.kb.get_by_category(category)
        
        emoji_map = {
            "Real Estate": "🏠",
            "Tourism": "🏞️", "History": "📜", "Culture": "👥",
            "Practical": "ℹ️", "Wildlife": "🦁", "Facts": "🔍",
            "Geography": "🗺️"
        }
        
        emoji = emoji_map.get(category, "📚")
        content = f"{emoji} *{category}*\n\n"
        
        if topics:
            content += f"*{len(topics)} topics available*\n\n"
            content += "*Quick Preview:*\n"
            
            # Show first 3 topics as preview
            for i, topic in enumerate(topics[:3], 1):
                content += f"{i}. {topic['topic']}\n"
            
            if len(topics) > 3:
                content += f"\n_...and {len(topics) - 3} more topics_\n"
            
            content += "\n💡 *Select a topic below to learn more!*"
        else:
            content += "No topics available in this category yet."
        
        return content

# =========================================================
# INITIALIZE
# =========================================================
eva = EvaGeisesBot()
menu = InteractiveMenu(eva.kb)

# =========================================================
# PROPERTY POSTING SCHEDULER
# =========================================================
async def post_daily_property(context: ContextTypes.DEFAULT_TYPE):
    """Post one property per day to registered chats"""
    try:
        properties = eva.kb.get_by_category("Real Estate")
        
        if not properties:
            return
        
        # Get all group chats where bot is active
        chats = eva.db.get_active_chats()
        
        for chat in chats:
            chat_id = chat['chat_id']
            chat_key = str(chat_id)
            
            # Get last posted property index
            last_index = eva.last_property_post.get(chat_key, -1)
            
            # Get next property (cycle through properties)
            next_index = (last_index + 1) % len(properties)
            property_data = properties[next_index]
            
            # Format property message
            message = f"🏠 *Featured Property of the Day*\n\n"
            message += f"**{property_data['topic']}**\n\n"
            message += f"{property_data['content']}\n\n"
            message += f"📱 Use /menu → Real Estate for all properties!"
            
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )
                
                # Update last posted index
                eva.last_property_post[chat_key] = next_index
                
                logger.info(f"Posted property to chat {chat_id}")
                
                # Wait between posts to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error posting to chat {chat_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in property posting: {e}")

# =========================================================
# GREETING SCHEDULER
# =========================================================
async def send_periodic_greetings(context: ContextTypes.DEFAULT_TYPE):
    """Send periodic greetings to active chats"""
    try:
        chats = eva.db.get_active_chats()
        
        for chat in chats:
            chat_id = chat['chat_id']
            
            if eva.should_send_greeting(chat_id):
                greeting = eva.get_periodic_greeting()
                
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=greeting,
                        parse_mode="Markdown"
                    )
                    
                    logger.info(f"Sent greeting to chat {chat_id}")
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error sending greeting to {chat_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in greeting scheduler: {e}")

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    eva.db.add_user(user.id, user.username or "Unknown")
    
    # Track chat for automated postings
    if update.message.chat.type in ['group', 'supergroup']:
        eva.db.track_chat(chat_id)
    
    greeting = eva.get_greeting()
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = f"""🇳🇦 *Eva Geises - Namibia Expert Bot*

{greeting} everyone! I'm Eva Geises, your AI-powered Namibia assistant! 🦁

*I can help with:*
• Real Estate Properties 🏠
• Tourism & Travel Planning 🏞️
• Wildlife & Safari Info 🦓
• Cultural Insights & History 👥
• Practical Travel Advice ℹ️
• Geography & Quick Facts 🗺️

*How to use me:*
• Ask questions naturally - I understand!
• Mention "Namibia" - I'll join in!
• Use /menu for organized topics
• I respond to greetings warmly!
• I welcome new members automatically!

*Try asking:*
• "Where is Namibia?"
• "Tell me about Etosha"
• "What properties are for sale?"
• "Best time to visit?"

*Quick Commands:*
/menu - Browse categories 📚
/properties - View real estate 🏠
/topics - List all topics 📋
/stats - Your statistics 📊
/help - Help info 🆘

🇳🇦 Let's explore Namibia together! 🏜️"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"👋 {greeting} {user.first_name}!\n\n"
            f"I'm Eva Geises, your Namibia expert! 🇳🇦\n\n"
            f"Add me to a group or ask me anything!\n\n"
            f"📱 Use /menu to explore topics! 🦁",
            parse_mode="Markdown"
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu"""
    await update.message.reply_text(
        "🇳🇦 *I am here to help learn Namibia*\n\nWhat would you like to explore?",
        parse_mode="Markdown",
        reply_markup=menu.main_menu()
    )

async def properties_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /properties - show all real estate listings"""
    properties = eva.kb.get_by_category("Real Estate")
    
    if properties:
        response = "🏠 *Available Properties in Namibia*\n\n"
        
        for i, prop in enumerate(properties, 1):
            response += f"*{i}. {prop['topic']}*\n"
            response += f"{prop['content']}\n\n"
        
        response += "📱 Use /menu → Real Estate for more details!"
    else:
        response = "No properties currently available."
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /topics"""
    topics = eva.kb.get_all_topics()
    
    if topics:
        response = "📚 *All Namibia Topics:*\n\n"
        for i, topic in enumerate(topics, 1):
            response += f"{i}. {topic}\n"
        
        response += f"\n*Total: {len(topics)} topics*\n\n"
        response += "💡 Ask me about any topic!\n"
        response += "📱 Or use /menu for organized categories"
    else:
        response = "No topics available."
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        all_users = eva.db.get_all_users()
        popular = eva.db.get_popular_queries(5)
        
        stats = f"""📊 *Eva Geises Statistics (Admin)*

*System:*
• Total users: {len(all_users)}
• Topics: {len(eva.kb.get_all_topics())}
• Categories: {len(eva.kb.get_categories())}

*Popular Questions:*
"""
        for i, q in enumerate(popular, 1):
            stats += f"{i}. \"{q['query'][:30]}...\" ({q['count']}x)\n"
        
        stats += "\n📱 Status: ✅ Active"
        await update.message.reply_text(stats, parse_mode="Markdown")
    else:
        user_stats = eva.db.get_user_stats(user_id)
        
        stats = f"""📊 *Your Statistics*

*Activity:*
• Questions: {user_stats['query_count']}
• Since: {user_stats['joined_date'][:10] if user_stats['joined_date'] else 'Recently'}

*Available:*
• Topics: {len(eva.kb.get_all_topics())}
• Categories: {len(eva.kb.get_categories())}

📱 Use /menu to explore! 🇳🇦"""
        
        await update.message.reply_text(stats, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    greeting = eva.get_greeting()
    
    help_text = f"""🆘 *Eva Geises - Help*

{greeting}! I'm Eva, your AI Namibia expert! 🇳🇦

*What I know:*
• Real estate properties 🏠
• Tourism & destinations 🏞️
• Wildlife & safaris 🦁
• Culture & people 👥
• History & heritage 📜
• Practical travel info ℹ️
• Geography & facts 🗺️

*How to use me:*
• Ask natural questions
• Use /menu for categories
• I respond to greetings!
• I join Namibia discussions!

*Examples:*
"Where is Namibia?"
"Tell me about Etosha"
"What properties for sale?"
"Best time to visit?"

*Commands:*
/menu - Categories 📚
/properties - Real estate 🏠
/topics - All topics 📋
/stats - Statistics 📊
/help - This message 🆘

🇳🇦 Ask me anything! 🦁"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: add knowledge"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return
    
    if not context.args or '|' not in ' '.join(context.args):
        await update.message.reply_text(
            "*Usage:* /add <topic> | <content> | <category> | <keywords>\n\n"
            "*Example:*\n"
            "`/add Skeleton Coast | Haunting coastline | Tourism | coast`",
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
        await update.message.reply_text(f"✅ Added: *{topic}*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages"""
    if update.message.from_user.id == context.bot.id or not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    
    eva.db.add_user(user_id, update.effective_user.username or "Unknown")
    eva.db.log_query(user_id, message)
    
    should_respond, response_type = eva.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        logger.info(f"Eva responding: {message[:50]}... ({response_type})")
        response = eva.generate_response(message, response_type)
        
        if response:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            try:
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                logger.info("✅ Response sent")
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
        response = "🔍 *Search Results:*\n\n"
        for i, r in enumerate(results, 1):
            response += f"*{i}. {r['topic']}*\n{r['content']}\n\n"
        response += "📱 Use /menu for organized browsing!"
    else:
        response = (
            "🤔 Ask me about Namibia.\n\n"
            "Try:\n"
            "• /menu to browse\n"
            "• Ask about Etosha, Himba, etc.\n"
            "• /properties for real estate\n\n"
            "🇳🇦 I know about tourism, wildlife, culture, and properties!"
        )
    
    eva.db.log_query(user_id, message)
    await update.message.reply_text(response, parse_mode="Markdown")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                # Bot was added to group
                chat_id = update.effective_chat.id
                chat_title = update.effective_chat.title
                eva.db.track_chat(chat_id, 'group', chat_title)
                continue
            
            if member.id not in eva.welcomed_users:
                welcome = eva.generate_welcome(member.first_name)
                eva.db.add_user(member.id, member.username or "Unknown", member.first_name)
                eva.welcomed_users.add(member.id)
                
                await asyncio.sleep(1)
                await update.message.reply_text(welcome, parse_mode="Markdown")

async def post_daily_property(context: ContextTypes.DEFAULT_TYPE):
    """Post daily property to all active groups"""
    try:
        logger.info("🏠 Starting daily property post...")
        active_chats = eva.db.get_active_chats()
        
        if not active_chats:
            logger.info("📭 No active chats for property posting")
            return
        
        # Get all real estate properties
        properties = eva.kb.get_by_category("Real Estate")
        
        if not properties:
            logger.warning("⚠️ No real estate properties found")
            return
        
        # Choose a random property or cycle through them
        for chat in active_chats:
            chat_id = chat['chat_id']
            
            # Rotate property selection based on day
            day_of_year = datetime.now().timetuple().tm_yday
            property_index = day_of_year % len(properties)
            property_data = properties[property_index]
            
            # Format property message
            message = f"🏠 *Featured Property of the Day*\n\n"
            message += f"**{property_data['topic']}**\n\n"
            message += f"{property_data['content']}\n\n"
            message += "💡 _Interested? Contact us for more details!_\n"
            message += "📱 Use /properties to see all listings!"
            
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Property posted to chat {chat_id}")
                await asyncio.sleep(2)  # Avoid rate limiting
            except Exception as e:
                logger.error(f"❌ Failed to post to chat {chat_id}: {e}")
                # Deactivate chat if bot was removed
                if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    eva.db.deactivate_chat(chat_id)
                    logger.info(f"🔇 Deactivated chat {chat_id}")
        
        logger.info("✅ Daily property posting complete")
    except Exception as e:
        logger.error(f"❌ Error in daily property post: {e}")

async def send_periodic_greetings(context: ContextTypes.DEFAULT_TYPE):
    """Send periodic greetings to active groups"""
    try:
        logger.info("👋 Starting periodic greetings...")
        active_chats = eva.db.get_active_chats()
        
        if not active_chats:
            logger.info("📭 No active chats for greetings")
            return
        
        for chat in active_chats:
            chat_id = chat['chat_id']
            
            # Check if this chat should receive greeting
            if eva.should_send_greeting(chat_id):
                greeting = eva.get_periodic_greeting()
                
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=greeting,
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Greeting sent to chat {chat_id}")
                    await asyncio.sleep(2)  # Avoid rate limiting
                except Exception as e:
                    logger.error(f"❌ Failed to send greeting to chat {chat_id}: {e}")
                    # Deactivate chat if bot was removed
                    if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                        eva.db.deactivate_chat(chat_id)
                        logger.info(f"🔇 Deactivated chat {chat_id}")
        
        logger.info("✅ Periodic greetings complete")
    except Exception as e:
        logger.error(f"❌ Error in periodic greetings: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Main menu
    if data == "menu_back":
        await query.edit_message_text(
            "🇳🇦 *I am here to help learn Namibia*\n\nWhat would you like to explore?",
            parse_mode="Markdown",
            reply_markup=menu.main_menu()
        )
    
    # Category selection - show submenu with topic buttons
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        content = menu.format_category(category)
        
        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=menu.create_submenu(category)
        )
    
    # Topic selection - show detailed information
    elif data.startswith("topic_"):
        # Parse: topic_Category_index
        parts = data.split("_")
        if len(parts) >= 3:
            category = "_".join(parts[1:-1])  # Handle "Real Estate" category
            try:
                topic_index = int(parts[-1])
            except:
                topic_index = 0
            
            topics = eva.kb.get_by_category(category)
            
            if topics and 0 <= topic_index < len(topics):
                topic = topics[topic_index]
                
                # Format detailed topic response
                emoji_map = {
                    "Real Estate": "🏠",
                    "Tourism": "🏞️", "History": "📜", "Culture": "👥",
                    "Practical": "ℹ️", "Wildlife": "🦁", "Facts": "🚀",
                    "Geography": "🗺️"
                }
                
                emoji = emoji_map.get(category, "📌")
                
                response = f"{emoji} *{topic['topic']}*\n\n"
                response += f"{topic['content']}\n\n"
                
                # Add keywords if available
                if topic.get('keywords'):
                    keywords = topic['keywords'].strip()
                    if keywords:
                        response += f"🏷️ *Keywords:* {keywords}\n\n"
                
                response += f"📂 *Category:* {category}\n\n"
                response += "💡 Ask me more questions or explore other topics!"
                
                await query.edit_message_text(
                    response,
                    parse_mode="Markdown",
                    reply_markup=menu.back_button(category)
                )
                return
        
        # Fallback if topic not found
        await query.edit_message_text(
            "❌ Topic not found. Please try another topic.",
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )

# =========================================================
# MAIN
# =========================================================
def main():
    """Run Eva"""
    logger.info("=" * 60)
    logger.info("🇳🇦 EVA GEISES - NAMIBIA EXPERT & REAL ESTATE AGENT")
    logger.info("=" * 60)
    logger.info(f"✅ Topics: {len(eva.kb.get_all_topics())}")
    logger.info(f"✅ Categories: {len(eva.kb.get_categories())}")
    logger.info("=" * 60)
    
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .connect_timeout(15) \
        .read_timeout(10) \
        .write_timeout(10) \
        .build()
    
    # Add handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('properties', properties_command))
    app.add_handler(CommandHandler('topics', topics_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('add', add_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message))
    
    # Schedule daily property posts (at 10 AM every day)
    job_queue = app.job_queue
    job_queue.run_daily(
        post_daily_property,
        time=datetime.strptime("10:00", "%H:%M").time(),
        name="daily_property_post"
    )
    
    # Schedule periodic greetings (every 2 hours)
    job_queue.run_repeating(
        send_periodic_greetings,
        interval=7200,  # 2 hours in seconds
        first=300,  # Start after 5 minutes
        name="periodic_greetings"
    )
    
    logger.info("🚀 Eva is running with automated features...")
    logger.info("📅 Daily property posts at 10:00 AM")
    logger.info("👋 Periodic greetings every 2 hours")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
            break
        except (TimedOut, NetworkError) as e:
            logger.error(f"Connection error (attempt {attempt + 1}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except KeyboardInterrupt:
            logger.info("🛑 Stopped")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            break

if __name__ == "__main__":
    main()
        
