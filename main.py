import os
import logging
import random
import re
import asyncio
import time
import json
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
import aiohttp

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

GROK_API_KEY = os.environ.get("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# =========================================================
# CONVERSATION MEMORY SYSTEM
# =========================================================
class ConversationMemory:
    def __init__(self, max_history=10):
        self.memories = {}
        self.max_history = max_history
    
    def add_conversation(self, chat_id, user_id, message, response):
        """Store conversation history"""
        if chat_id not in self.memories:
            self.memories[chat_id] = []
        
        self.memories[chat_id].append({
            'user_id': user_id,
            'message': message,
            'response': response,
            'timestamp': datetime.now()
        })
        
        # Keep only recent conversations
        if len(self.memories[chat_id]) > self.max_history:
            self.memories[chat_id] = self.memories[chat_id][-self.max_history:]
    
    def get_context(self, chat_id, user_id=None, limit=5):
        """Get conversation context for Grok"""
        if chat_id not in self.memories:
            return ""
        
        context = []
        for conv in self.memories[chat_id][-limit:]:
            if user_id and conv['user_id'] != user_id:
                continue
            
            context.append(f"User: {conv['message']}")
            context.append(f"Eva: {conv['response']}")
        
        return "\n".join(context)
    
    def clear_chat(self, chat_id):
        """Clear chat history"""
        if chat_id in self.memories:
            del self.memories[chat_id]

# =========================================================
# GROUP MANAGEMENT SYSTEM
# =========================================================
class GroupManager:
    def __init__(self):
        self.group_data = {}
        self.scheduled_greetings = {}
    
    async def schedule_daily_greeting(self, context, chat_id):
        """Schedule daily greetings"""
        job = context.job_queue.run_daily(
            self.send_daily_greeting,
            time=datetime.time(datetime.now().replace(hour=9, minute=0, second=0)),
            data=chat_id,
            name=f"daily_greeting_{chat_id}"
        )
        self.scheduled_greetings[chat_id] = job
    
    async def send_daily_greeting(self, context):
        """Send daily greeting"""
        chat_id = context.job.data
        eva = context.bot_data.get('eva')
        
        if eva:
            greetings = [
                "🌅 *Good morning Namibia explorers!* Ready for another day of adventure? 🇳🇦",
                "☀️ *Morning everyone!* What's your Namibia question today? I'm here to help! 🦁",
                "🇳🇦 *Good morning!* Did you know Namibia has the world's oldest desert? Ask me anything! 🏜️",
                "🦓 *Rise and shine!* Perfect time to plan your Namibia safari! Use /menu to explore! 🌅"
            ]
            
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=random.choice(greetings),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Daily greeting error: {e}")
    
    def get_member_welcome(self, name, count):
        """Different welcome messages based on member count"""
        if count < 10:
            welcomes = [
                f"👋 Welcome {name}! You're helping us grow our Namibia community! 🇳🇦",
                f"🌟 {name}, welcome to our small but passionate Namibia group! 🦁",
                f"🇳🇦 Hello {name}! Great to have you in our Namibia circle! 🏜️"
            ]
        elif count < 50:
            welcomes = [
                f"👋 Welcome {name}! You're joining {count-1} other Namibia enthusiasts! 🇳🇦",
                f"🌟 {name}, welcome aboard! We're {count} strong now! 🦁",
                f"🇳🇦 Hello {name}! Great timing - we just hit {count} members! 🏜️"
            ]
        else:
            welcomes = [
                f"👋 Welcome {name}! You're member #{count} in our growing Namibia community! 🇳🇦",
                f"🌟 {name}, welcome! You're joining {count-1} fellow Namibia explorers! 🦁",
                f"🇳🇦 Hello {name}! Our community of {count} members welcomes you! 🏜️"
            ]
        
        return random.choice(welcomes)

# =========================================================
# GROK API INTEGRATION
# =========================================================
class GrokIntegration:
    def __init__(self, api_key, base_url=GROK_API_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self.enabled = bool(api_key)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_response(self, message, context="", system_prompt=None):
        """Get response from Grok API"""
        if not self.enabled or not self.api_key:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if system_prompt is None:
            system_prompt = """You are Eva Geises, an AI Namibia expert bot. You're friendly, knowledgeable, and passionate about Namibia. 
            You provide accurate information about Namibia's tourism, wildlife, culture, history, and geography.
            You're integrated with a knowledge base, so use that information when available.
            Keep responses conversational but informative.
            Always maintain a positive, welcoming tone.
            Use emojis occasionally but not excessively.
            Respond in Markdown format when helpful."""
        
        full_context = f"{system_prompt}\n\nContext from previous conversations:\n{context}\n\nCurrent question: {message}"
        
        payload = {
            "model": "grok-beta",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ],
            "max_tokens": 500,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        try:
            async with self.session.post(self.base_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    logger.error(f"Grok API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Grok API connection error: {e}")
            return None

# =========================================================
# ENHANCED EVA GEISES BOT
# =========================================================
class EvaGeisesBot:
    def __init__(self):
        self.db = Database()
        self.kb = KnowledgeBase()
        self.memory = ConversationMemory()
        self.group_manager = GroupManager()
        self.grok = GrokIntegration(GROK_API_KEY)
        self.last_activity = {}
        self.welcomed_users = set()
        self.conversation_state = {}
        logger.info(f"🇳🇦 Enhanced Eva Geises initialized with {len(self.kb.get_all_topics())} topics")
    
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
        """Enhanced message analysis with conversation understanding"""
        msg = message.lower().strip()
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Store conversation state
        chat_key = str(chat_id)
        if chat_key not in self.conversation_state:
            self.conversation_state[chat_key] = {
                'last_topic': None,
                'question_count': 0,
                'last_user': None
            }
        
        state = self.conversation_state[chat_key]
        
        response_types = []
        
        # 1. Direct mentions - 100%
        bot_mentions = ["@eva", "eva", "@namibiabot", "namibia bot", "hey bot", "hello bot", "hey eva", "eva,", "eva!"]
        if any(mention in msg for mention in bot_mentions):
            response_types.append(("search", 100))
        
        # 2. Questions - 90%
        question_words = ["what", "how", "where", "when", "why", "who", "which", 
                         "can you", "tell me", "explain", "show me", "is", "are", "do", "does"]
        if "?" in msg or any(msg.startswith(w) for w in question_words):
            response_types.append(("search", 90))
        
        # 3. Greetings - 80%
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", 
                    "moro", "greetings", "hallo", "howzit", "sup", "yo "]
        if any(g in msg.split() for g in greetings):
            response_types.append(("greeting", 80))
        
        # 4. Namibia mentions - 85%
        if "namibia" in msg or "namibian" in msg:
            response_types.append(("search", 85))
        
        # 5. Specific topics - 90%
        topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", 
                 "desert", "dunes", "fish river", "cheetah", "elephant", "lion", "wildlife",
                 "safari", "namib", "capital", "visa", "currency", "weather", "accommodation",
                 "hotel", "lodging", "tour", "guide", "car rental", "flight"]
        if any(t in msg for t in topics):
            response_types.append(("search", 90))
        
        # 6. Travel keywords - 80%
        travel = ["travel", "tour", "visit", "trip", "vacation", "holiday", 
                 "destination", "tourist", "booking", "flight", "hotel", "stay"]
        if any(w in msg for w in travel):
            response_types.append(("search", 80))
        
        # 7. Conversation continuation - Check if continuing same topic
        if state['last_user'] == user_id and state['question_count'] > 0:
            response_types.append(("conversation", 70))
        
        # 8. Quiet chat - 30%
        if self.is_chat_quiet(chat_id, minutes=15):
            response_types.append(("conversation_starter", 40))
        
        # 9. Group management keywords
        mgmt_keywords = ["rules", "welcome", "introduce", "about group", "group info"]
        if any(keyword in msg for keyword in mgmt_keywords):
            response_types.append(("group_info", 95))
        
        if response_types:
            response_types.sort(key=lambda x: x[1], reverse=True)
            top = response_types[0]
            
            # Update conversation state
            state['last_user'] = user_id
            if top[0] == "search":
                state['question_count'] += 1
            
            if random.random() < (top[1] / 100):
                return True, top[0]
        
        return False, None
    
    def is_chat_quiet(self, chat_id, minutes=15):
        """Check if chat quiet"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_activity:
            return True
        return datetime.now() - self.last_activity[chat_id_str] > timedelta(minutes=minutes)
    
    async def generate_response(self, message, response_type, user_id=None, chat_id=None):
        """Enhanced response generation with Grok integration"""
        clean_msg = re.sub(r'@[^\s]*', '', message.lower()).strip()
        clean_msg = re.sub(r'(hey|hello|hi)\s+(eva|bot|namibia)', '', clean_msg).strip()
        
        # Get conversation context for Grok
        context = ""
        if chat_id and user_id:
            context = self.memory.get_context(chat_id, user_id, limit=3)
        
        # Search knowledge base first
        if response_type in ["search", "conversation"] and clean_msg:
            results = self.kb.search(clean_msg, limit=3)
            
            if results:
                # Use Grok to enhance the response if available
                if self.grok.enabled:
                    knowledge_context = "\n".join([f"{r['topic']}: {r['content']}" for r in results])
                    grok_prompt = f"""Based on this Namibia knowledge:
                    {knowledge_context}
                    
                    The user asked: {message}
                    
                    Provide a helpful, conversational response that uses this information naturally."""
                    
                    try:
                        async with self.grok:
                            grok_response = await self.grok.get_response(grok_prompt, context)
                            if grok_response:
                                return grok_response
                    except Exception as e:
                        logger.error(f"Grok error: {e}")
                
                # Fallback to standard response
                best = results[0]
                
                response = f"🤔 *Based on your question:*\n\n"
                response += f"**{best['topic']}**\n"
                response += f"{best['content']}\n\n"
                
                if len(results) > 1:
                    response += "💡 *Related information:*\n"
                    for r in results[1:]:
                        response += f"• {r['topic']}\n"
                    response += "\n"
                
                response += f"📱 *Use /menu for more topics or ask another question!*"
                return response
        
        # Use Grok for natural conversation
        if self.grok.enabled and response_type in ["conversation", "group_info"]:
            system_prompt = """You are Eva Geises, managing a Namibia enthusiast group chat.
            Be friendly, helpful, and maintain positive group dynamics.
            Encourage discussions about Namibia.
            Keep responses concise and engaging."""
            
            try:
                async with self.grok:
                    grok_response = await self.grok.get_response(message, context, system_prompt)
                    if grok_response:
                        return grok_response
            except Exception as e:
                logger.error(f"Grok error: {e}")
        
        # Greeting responses
        greeting = self.get_greeting()
        
        if response_type == "greeting":
            greetings = [
                f"👋 {greeting}! How can I help you explore Namibia today?\n\n📱 Use /menu to browse topics!",
                f"🇳🇦 {greeting}! What would you like to know about Namibia?\n\n💡 Try /menu for categories!",
                f"🦁 {greeting}! I'm Eva, your Namibia guide. Ask away!\n\n📚 Check /menu for all topics!",
                f"🏜️ {greeting}! Ready to discover Namibia?\n\n✨ Use /menu to explore!",
                f"🌅 {greeting}! Beautiful day to talk about Namibia, isn't it? 😊"
            ]
            return random.choice(greetings)
        
        # Conversation starter
        if response_type == "conversation_starter":
            return self.get_conversation_starter()
        
        # Group info
        if response_type == "group_info":
            return self.get_group_info()
        
        return "🇳🇦 Ask me anything about Namibia!\n\n💡 Try: \"Where is Namibia?\" or use /menu"
    
    def get_conversation_starter(self):
        """Generate conversation starter"""
        starters = [
            "💭 *Question for everyone:* What's your dream Namibia destination?\n\n📱 Use /menu to explore destinations!",
            "🦁 *Wildlife talk:* Who has been on safari in Namibia?\n\n🦓 Check /menu → Wildlife for more!",
            "🏜️ *Fun fact:* The Namib Desert is 55-80 million years old!\n\n📚 Use /menu for more Namibia facts!",
            "👥 *Cultural question:* What interests you about Namibia's people?\n\n💡 Try /menu → Culture!",
            "🗺️ *Travel tip:* Best time to visit is May-October!\n\n✈️ Use /menu → Tourism for planning!",
            "🌅 *Amazing:* Sossusvlei has the world's highest dunes!\n\n📖 Discover more with /menu!",
            "🎯 *Discussion:* What's the most surprising thing you've learned about Namibia?",
            "🤔 *Curious:* Has anyone here visited Namibia? Share your experience!"
        ]
        return random.choice(starters)
    
    def get_group_info(self):
        """Provide group information"""
        info = [
            "👥 *About This Group:* We're a community of Namibia enthusiasts!\n\n"
            "🇳🇦 *Purpose:* Share knowledge, experiences, and love for Namibia\n"
            "🤝 *Rules:* Be respectful, helpful, and stay on topic\n"
            "🦁 *Topics:* Tourism, wildlife, culture, history, travel tips\n"
            "💡 *Use me:* Ask questions, use /menu, mention Namibia!\n\n"
            "Welcome to our Namibia family! 🏜️",
            
            "🌟 *Group Guidelines:*\n\n"
            "1. Respect all members\n"
            "2. Keep discussions Namibia-related\n"
            "3. Share photos and experiences\n"
            "4. Ask questions freely\n"
            "5. Help each other plan trips\n\n"
            "I'm Eva, here to assist! Use /menu or ask me anything! 🇳🇦",
            
            "🗺️ *Welcome to Namibia Explorers!*\n\n"
            "This group is for:\n"
            "• Planning Namibia trips\n"
            "• Sharing travel stories\n"
            "• Learning about culture\n"
            "• Wildlife discussions\n"
            "• Photo sharing\n\n"
            "I'm your AI guide Eva! Try /help for commands! 🦁"
        ]
        return random.choice(info)
    
    def generate_welcome(self, name, member_count):
        """Welcome new members with group manager"""
        return self.group_manager.get_member_welcome(name, member_count)

# =========================================================
# ENHANCED INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    def __init__(self, kb):
        self.kb = kb
        self.categories = kb.get_categories()
    
    def main_menu(self):
        """Create main menu"""
        keyboard = [
            [InlineKeyboardButton("🏞️ Tourism & Travel", callback_data="cat_Tourism")],
            [InlineKeyboardButton("📜 History & Heritage", callback_data="cat_History")],
            [InlineKeyboardButton("👥 Culture & People", callback_data="cat_Culture")],
            [InlineKeyboardButton("ℹ️ Practical Info", callback_data="cat_Practical")],
            [InlineKeyboardButton("🦁 Wildlife & Nature", callback_data="cat_Wildlife")],
            [InlineKeyboardButton("🚀 Quick Facts", callback_data="cat_Facts")],
            [InlineKeyboardButton("🗺️ Geography", callback_data="cat_Geography")],
            [InlineKeyboardButton("💬 Chat with Eva", callback_data="chat_mode")]
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
        
        # Add back button and chat option
        keyboard.append([
            InlineKeyboardButton("💬 Chat Mode", callback_data="chat_mode"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_back")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def back_button(self, category=None):
        """Create back button(s)"""
        if category:
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Category", callback_data=f"cat_{category}")],
                [InlineKeyboardButton("💬 Chat Mode", callback_data="chat_mode"),
                 InlineKeyboardButton("🏠 Main Menu", callback_data="menu_back")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("💬 Chat Mode", callback_data="chat_mode"),
                 InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")]
            ]
        
        return InlineKeyboardMarkup(keyboard)

# =========================================================
# INITIALIZE ENHANCED BOT
# =========================================================
eva = EvaGeisesBot()
menu = InteractiveMenu(eva.kb)

# =========================================================
# ENHANCED COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    eva.db.add_user(user.id, user.username or "Unknown")
    
    greeting = eva.get_greeting()
    
    if update.message.chat.type in ['group', 'supergroup']:
        # Initialize group management
        chat_id = update.effective_chat.id
        await eva.group_manager.schedule_daily_greeting(context, chat_id)
        
        welcome = f"""🇳🇦 *Eva Geises - Intelligent Namibia Expert Bot*

{greeting} everyone! I'm Eva Geises, your AI-powered Namibia assistant! 🦁

*Enhanced Features:*
• 🤖 AI-Powered natural conversations
• 🗣️ Context-aware discussions
• 👥 Smart group management
• 🌅 Daily greetings & engagement
• 🎯 Personalized responses

*I can help with:*
• Tourism & Travel Planning 🏞️
• Wildlife & Safari Info 🦓
• Cultural Insights & History 👥
• Practical Travel Advice ℹ️
• Geography & Quick Facts 🗺️

*How to use me:*
• Ask questions naturally - I understand context!
• Mention "Namibia" - I'll join intelligently!
• Use /menu for organized topics
• I welcome new members personally!
• I manage group conversations!

*Try asking:*
• "Where should I stay in Windhoek?"
• "Tell me about Etosha safaris"
• "What's special about Himba culture?"
• "Planning a 7-day Namibia trip"

*Quick Commands:*
/menu - Browse categories 📚
/topics - List all topics 📋
/stats - Your statistics 📊
/help - Help info 🆘
/chat - Direct conversation mode 💬

🇳🇦 Let's explore Namibia together intelligently! 🏜️"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"👋 {greeting} {user.first_name}!\n\n"
            f"I'm Eva Geises, your enhanced Namibia expert! 🇳🇦\n\n"
            f"*New Features:*\n"
            f"• AI-powered conversations\n"
            f"• Context understanding\n"
            f"• Natural language processing\n\n"
            f"Add me to a group or ask me anything!\n\n"
            f"📱 Use /menu to explore topics or /chat for conversation! 🦁",
            parse_mode="Markdown"
        )

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chat - Direct conversation mode"""
    await update.message.reply_text(
        "💬 *Chat Mode Activated*\n\n"
        "I'm now in conversational mode! Talk to me naturally about anything Namibia-related.\n\n"
        "*Tips:*\n"
        "• Ask follow-up questions\n"
        "• Share your thoughts\n"
        "• I'll remember our conversation\n"
        "• Use /menu to return to topics\n\n"
        "What's on your mind about Namibia? 🇳🇦",
        parse_mode="Markdown"
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu"""
    await update.message.reply_text(
        "🇳🇦 *Namibia Knowledge System*\n\nWhat would you like to explore?",
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
        response += "💡 Ask me about any topic naturally!\n"
        response += "📱 Or use /menu for organized categories\n"
        response += "💬 Try /chat for conversation mode"
    else:
        response = "No topics available."
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        all_users = eva.db.get_all_users()
        popular = eva.db.get_popular_queries(5)
        
        # Count active conversations
        active_chats = len(eva.conversation_state)
        
        stats = f"""📊 *Enhanced Eva Geises Statistics (Admin)*

*System:*
• Total users: {len(all_users)}
• Topics: {len(eva.kb.get_all_topics())}
• Categories: {len(eva.kb.get_categories())}
• Active conversations: {active_chats}
• Grok API: {'✅ Enabled' if eva.grok.enabled else '❌ Disabled'}

*Popular Questions:*
"""
        for i, q in enumerate(popular, 1):
            stats += f"{i}. \"{q['query'][:30]}...\" ({q['count']}x)\n"
        
        stats += "\n📱 Status: ✅ Intelligent Mode Active"
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

*Features:*
• AI Conversations: {'✅' if eva.grok.enabled else '❌'}
• Context Memory: ✅
• Group Management: ✅

📱 Use /menu to explore or /chat to talk! 🇳🇦"""
        
        await update.message.reply_text(stats, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    greeting = eva.get_greeting()
    
    help_text = f"""🆘 *Enhanced Eva Geises - Help*

{greeting}! I'm Eva, your intelligent AI Namibia expert! 🇳🇦

*Enhanced Capabilities:*
• Natural language understanding 🤖
• Conversation memory 🧠
• Context-aware responses 🗣️
• Group management 👥
• Daily engagement 🌅

*What I know:*
• Tourism & destinations 🏞️
• Wildlife & safaris 🦁
• Culture & people 👥
• History & heritage 📜
• Practical travel info ℹ️
• Geography & facts 🗺️

*How to use me:*
• Ask natural questions with context
• Use /menu for categories
• Try /chat for conversation mode
• I respond intelligently to greetings!
• I manage group dynamics!

*Examples:*
"Where should I stay in Swakopmund?"
"Tell me about Etosha during rainy season"
"Himba people traditions and lifestyle"
"Planning a 10-day self-drive Namibia trip"

*Commands:*
/menu - Categories 📚
/topics - All topics 📋
/chat - Conversation mode 💬
/stats - Statistics 📊
/help - This message 🆘

🇳🇦 I understand context - ask follow-up questions! 🦁"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced group message handling"""
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
        response = await eva.generate_response(message, response_type, user_id, chat_id)
        
        if response:
            # Store conversation in memory
            eva.memory.add_conversation(chat_id, user_id, message, response)
            
            await asyncio.sleep(random.uniform(0.3, 1.2))
            
            try:
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                logger.info("✅ Intelligent response sent")
            except Exception as e:
                logger.error(f"Error: {e}")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced private message handling with Grok"""
    if update.message.text.startswith('/'):
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    
    # Use Grok for enhanced responses in private chat
    if eva.grok.enabled:
        context = eva.memory.get_context(chat_id, user_id, limit=5)
        
        system_prompt = """You are Eva Geises in private chat mode. 
        Provide detailed, helpful information about Namibia.
        Be conversational and friendly.
        Ask follow-up questions to understand user needs.
        Use the knowledge base when relevant."""
        
        try:
            async with eva.grok:
                grok_response = await eva.grok.get_response(message, context, system_prompt)
                if grok_response:
                    eva.memory.add_conversation(chat_id, user_id, message, grok_response)
                    eva.db.log_query(user_id, message)
                    await update.message.reply_text(grok_response, parse_mode="Markdown")
                    return
        except Exception as e:
            logger.error(f"Grok private chat error: {e}")
    
    # Fallback to knowledge base
    results = eva.kb.search(message, limit=3)
    
    if results:
        response = "🔍 *Search Results:*\n\n"
        for i, r in enumerate(results, 1):
            response += f"*{i}. {r['topic']}*\n{r['content']}\n\n"
        response += "📱 Use /menu for organized browsing or /chat to talk naturally!"
    else:
        response = (
            "🤔 No specific info found.\n\n"
            "Try:\n"
            "• /menu to browse\n"
            "• /chat for conversation mode\n"
            "• Ask about Etosha, Himba, etc.\n\n"
            "🇳🇦 I understand natural language - ask in your own words!"
        )
    
    eva.memory.add_conversation(chat_id, user_id, message, response)
    eva.db.log_query(user_id, message)
    await update.message.reply_text(response, parse_mode="Markdown")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced new member welcome"""
    if update.message.new_chat_members:
        chat_id = update.effective_chat.id
        
        # Get member count for personalized welcome
        try:
            chat = await context.bot.get_chat(chat_id)
            member_count = await chat.get_member_count()
        except:
            member_count = 1
        
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                continue
            
            if member.id not in eva.welcomed_users:
                welcome = eva.generate_welcome(member.first_name, member_count)
                eva.db.add_user(member.id, member.username or "Unknown")
                eva.welcomed_users.add(member.id)
                
                # Add group info
                welcome += "\n\n💡 *Group Tips:*\n"
                welcome += "• Ask me questions about Namibia\n"
                welcome += "• Use /menu to explore topics\n"
                welcome += "• Share your Namibia experiences\n"
                welcome += "• Be part of our community!\n\n"
                welcome += "🇳🇦 Welcome aboard! 🦁"
                
                await asyncio.sleep(1.5)
                await update.message.reply_text(welcome, parse_mode="Markdown")
                
                # Send follow-up after 2 minutes
                async def send_followup(context):
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"👋 *Follow-up for {member.first_name}:*\n\n"
                                 f"Need help getting started? Try:\n"
                                 f"• \"/menu\" for Namibia topics\n"
                                 f"• Ask about specific places\n"
                                 f"• Share what interests you!\n\n"
                                 f"I'm here to help! 🇳🇦",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                
                context.job_queue.run_once(send_followup, 120, data=chat_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Main menu
    if data == "menu_back":
        await query.edit_message_text(
            "🇳🇦 *Namibia Knowledge System*\n\nWhat would you like to explore?",
            parse_mode="Markdown",
            reply_markup=menu.main_menu()
        )
    
    # Chat mode
    elif data == "chat_mode":
        await query.edit_message_text(
            "💬 *Switched to Chat Mode*\n\n"
            "Talk to me naturally! I'll use AI to understand and respond.\n\n"
            "*Examples:*\n"
            "\"What's the best safari route?\"\n"
            "\"Tell me about Namibia's culture\"\n"
            "\"Planning a trip in July\"\n\n"
            "What would you like to discuss? 🇳🇦",
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )
    
    # Category selection
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        content = menu.format_category(category)
        
        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=menu.create_submenu(category)
        )
    
    # Topic selection
    elif data.startswith("topic_"):
        parts = data.split("_")
        if len(parts) >= 3:
            category = parts[1]
            try:
                topic_index = int(parts[2])
            except:
                topic_index = 0
            
            topics = eva.kb.get_by_category(category)
            
            if topics and 0 <= topic_index < len(topics):
                topic = topics[topic_index]
                
                emoji_map = {
                    "Tourism": "🏞️", "History": "📜", "Culture": "👥",
                    "Practical": "ℹ️", "Wildlife": "🦁", "Facts": "🚀",
                    "Geography": "🗺️"
                }
                
                emoji = emoji_map.get(category, "📌")
                
                response = f"{emoji} *{topic['topic']}*\n\n"
                response += f"{topic['content']}\n\n"
                
                if topic.get('keywords'):
                    keywords = topic['keywords'].strip()
                    if keywords:
                        response += f"🏷️ *Keywords:* {keywords}\n\n"
                
                response += f"📂 *Category:* {category}\n\n"
                response += "💡 Want to discuss this further? Use /chat mode!"
                
                await query.edit_message_text(
                    response,
                    parse_mode="Markdown",
                    reply_markup=menu.back_button(category)
                )
                return
        
        await query.edit_message_text(
            "❌ Topic not found. Please try another topic.",
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )

# =========================================================
# DAILY TASKS
# =========================================================
async def daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Run daily maintenance tasks"""
    # Clear old conversation states
    cutoff = datetime.now() - timedelta(days=1)
    chat_keys = list(eva.conversation_state.keys())
    
    for key in chat_keys:
        # Simple cleanup - in production, track timestamps
        pass
    
    logger.info("Daily maintenance completed")

# =========================================================
# MAIN
# =========================================================
def main():
    """Run Enhanced Eva"""
    logger.info("=" * 60)
    logger.info("🇳🇦 ENHANCED EVA GEISES - INTELLIGENT NAMIBIA EXPERT")
    logger.info("=" * 60)
    logger.info(f"✅ Topics: {len(eva.kb.get_all_topics())}")
    logger.info(f"✅ Categories: {len(eva.kb.get_categories())}")
    logger.info(f"✅ Grok API: {'ENABLED' if eva.grok.enabled else 'DISABLED'}")
    logger.info(f"✅ Conversation Memory: ACTIVE")
    logger.info(f"✅ Group Management: ACTIVE")
    logger.info("=" * 60)
    
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .connect_timeout(20) \
        .read_timeout(15) \
        .write_timeout(15) \
        .build()
    
    # Store Eva instance in bot data
    app.bot_data['eva'] = eva
    
    # Add command handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('topics', topics_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('chat', chat_command))
    app.add_handler(CommandHandler('add', add_command))
    
    # Add callback and message handlers
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message))
    
    # Schedule daily tasks
    app.job_queue.run_daily(daily_tasks, time=datetime.time(datetime.now().replace(hour=3, minute=0, second=0)))
    
    logger.info("🚀 Enhanced Eva is running intelligently...")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False
            )
            break
        except (TimedOut, NetworkError) as e:
            logger.error(f"Connection error (attempt {attempt + 1}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except KeyboardInterrupt:
            logger.info("🛑 Intelligently stopped")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            break

if __name__ == "__main__":
    main()
