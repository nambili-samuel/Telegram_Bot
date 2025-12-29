import os
import json
import random
import re
import asyncio
import requests
import logging
from datetime import datetime, timedelta
from rapidfuzz import fuzz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

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

# Knowledge Base URLs
KNOWLEDGE_BASE_GIST_URL = "https://gist.githubusercontent.com/nambili-samuel/a3bf79d67b2bd0c8d5aa9a830024417d/raw/a581e84507e48a1b35c586c9468de89f2fa35dea/namibia_knowledge_base.csv"
FALLBACK_KNOWLEDGE_URL = "https://raw.githubusercontent.com/nambili-samuel/Telegram_Bot/main/namibia_knowledge_base.csv"

# Data storage
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)
USER_PROFILES = os.path.join(DATA_DIR, "user_profiles.json")
GROUP_STATS = os.path.join(DATA_DIR, "group_stats.json")

# Admin configuration
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set(map(int, ADMIN_IDS_STR.split(','))) if ADMIN_IDS_STR else set()

GROUP_ID_STR = os.environ.get("GROUP_ID", "")
GROUP_ID = int(GROUP_ID_STR) if GROUP_ID_STR else None

# =========================================================
# USER PROFILES & ANALYTICS
# =========================================================
class UserProfile:
    def __init__(self):
        self.profiles = {}
        self.group_stats = {
            "total_messages": 0,
            "active_days": {},
            "conversation_starters": 0,
            "bot_launches": 0,
            "knowledge_queries": 0,
            "welcome_messages": 0,
            "new_members": []
        }
        self._load_data()
    
    def _load_data(self):
        """Load user profiles and statistics"""
        try:
            if os.path.exists(USER_PROFILES):
                with open(USER_PROFILES, 'r') as f:
                    self.profiles = json.load(f)
            if os.path.exists(GROUP_STATS):
                with open(GROUP_STATS, 'r') as f:
                    self.group_stats.update(json.load(f))
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def get_user(self, user_id):
        """Get or create user profile"""
        user_id_str = str(user_id)
        if user_id_str not in self.profiles:
            self.profiles[user_id_str] = {
                "first_seen": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "group_messages": 0,
                "bot_interactions": 0,
                "knowledge_queries": 0,
                "username": "",
                "full_name": ""
            }
            self.save()
        return self.profiles[user_id_str]
    
    def increment_group_message(self, user_id, username="", full_name=""):
        """Track group message"""
        profile = self.get_user(user_id)
        profile["group_messages"] += 1
        profile["last_active"] = datetime.now().isoformat()
        if username:
            profile["username"] = username
        if full_name:
            profile["full_name"] = full_name
        
        self.group_stats["total_messages"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        self.group_stats["active_days"][today] = self.group_stats["active_days"].get(today, 0) + 1
        self.save()
    
    def increment_bot_interaction(self, user_id):
        """Track bot interaction"""
        profile = self.get_user(user_id)
        profile["bot_interactions"] += 1
        self.save()
    
    def increment_knowledge_query(self):
        """Track knowledge query"""
        self.group_stats["knowledge_queries"] += 1
        self.save()
    
    def add_new_member(self, user_id, username, full_name):
        """Track new member"""
        self.group_stats["new_members"].append({
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "joined_at": datetime.now().isoformat()
        })
        self.group_stats["welcome_messages"] += 1
        self.save()
    
    def save(self):
        """Save to JSON files"""
        try:
            with open(USER_PROFILES, 'w') as f:
                json.dump(self.profiles, f, indent=2)
            with open(GROUP_STATS, 'w') as f:
                json.dump(self.group_stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

# =========================================================
# KNOWLEDGE BASE SYSTEM
# =========================================================
class IntelligentKnowledgeBase:
    def __init__(self):
        self.knowledge = []
        self.categories = {}
        self.synonyms = self._setup_synonyms()
        self.load_knowledge()
        logger.info(f"✅ Knowledge Base: {len(self.knowledge)} entries")
    
    def _setup_synonyms(self):
        """Setup synonym mappings"""
        return {
            'namibia': ['namibian', 'namibias', 'namib'],
            'windhoek': ['capital', 'city', 'main city'],
            'etosha': ['etosha park', 'national park', 'wildlife park'],
            'sossusvlei': ['sand dunes', 'namib desert', 'dunes'],
            'swakopmund': ['coastal town', 'german town', 'beach town'],
            'fish river': ['canyon', 'fish river canyon'],
            'himba': ['red people', 'ochre people', 'tribal'],
            'herero': ['victorian dress', 'traditional dress'],
            'wildlife': ['animals', 'safari', 'game', 'fauna'],
            'desert': ['arid', 'dry', 'sand', 'namib'],
            'elephant': ['elephants', 'pachyderm'],
            'lion': ['lions', 'big cat'],
            'cheetah': ['cheetahs', 'fastest animal']
        }
    
    def load_knowledge(self):
        """Load knowledge from remote URLs"""
        try:
            logger.info("📄 Loading knowledge base...")
            
            urls = [KNOWLEDGE_BASE_GIST_URL, FALLBACK_KNOWLEDGE_URL]
            content = None
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=15)
                    if response.status_code == 200:
                        content = response.text
                        logger.info(f"✅ Loaded from: {url}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to load from {url}: {e}")
            
            if content:
                self._parse_knowledge(content)
            else:
                self._load_embedded_knowledge()
                
        except Exception as e:
            logger.error(f"Error loading knowledge: {e}")
            self._load_embedded_knowledge()
    
    def _parse_knowledge(self, content):
        """Parse CSV content"""
        lines = content.strip().split('\n')
        
        for i, line in enumerate(lines[1:], 2):
            line = line.strip()
            if not line:
                continue
            
            try:
                parts = line.split(',', 2)
                if len(parts) < 3:
                    continue
                
                category, question, answer = parts[0].strip(), parts[1].strip().lower(), parts[2].strip()
                
                if category and question and answer:
                    entry = {
                        "category": category,
                        "question": question,
                        "answer": answer,
                        "keywords": self._extract_keywords(question)
                    }
                    self.knowledge.append(entry)
                    
                    if category not in self.categories:
                        self.categories[category] = []
                    self.categories[category].append(question)
                    
            except Exception as e:
                logger.warning(f"Error parsing line {i}: {e}")
        
        logger.info(f"✅ Parsed {len(self.knowledge)} entries")
    
    def _load_embedded_knowledge(self):
        """Load fallback knowledge"""
        embedded = """category,question,answer
Geography,capital of namibia,The capital of Namibia is Windhoek located in the central highlands.
Geography,where is namibia,Namibia is in southwestern Africa bordered by Angola Zambia Botswana South Africa and the Atlantic Ocean.
Tourism,etosha national park,Etosha is Namibia's premier wildlife destination with lions elephants rhinos and over 100 mammal species.
Tourism,sossusvlei,Sossusvlei features the world's highest sand dunes up to 380m in the Namib Desert.
Tourism,swakopmund,Swakopmund is a coastal town with German colonial architecture and adventure activities.
Culture,himba people,The Himba are semi-nomadic pastoralists known for their red ochre body paint and traditional lifestyle.
Culture,herero people,The Herero are known for their Victorian-style dresses and cattle-herding traditions.
Wildlife,desert elephants,Desert-adapted elephants have longer legs and can survive without water for days.
Wildlife,cheetahs,Namibia has the largest population of cheetahs in the world.
Facts,oldest desert,The Namib Desert is 55-80 million years old making it the world's oldest desert."""
        
        self._parse_knowledge(embedded)
    
    def _extract_keywords(self, text):
        """Extract keywords from text"""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are'}
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def intelligent_search(self, query, threshold=60):
        """Search with fuzzy matching and synonyms"""
        if not query.strip():
            return []
        
        query_lower = query.lower().strip()
        expanded = self._expand_query(query_lower)
        
        results = []
        seen = set()
        
        for exp_query in expanded:
            for item in self.knowledge:
                if item["answer"] in seen:
                    continue
                
                # Calculate similarity scores
                exact = 100 if exp_query == item["question"] else 0
                partial = fuzz.partial_ratio(exp_query, item["question"])
                token = fuzz.token_sort_ratio(exp_query, item["question"])
                
                # Keyword matching
                q_keywords = self._extract_keywords(exp_query)
                i_keywords = item["keywords"]
                keyword_score = 0
                if q_keywords and i_keywords:
                    common = set(q_keywords) & set(i_keywords)
                    if common:
                        keyword_score = (len(common) / max(len(q_keywords), len(i_keywords))) * 100
                
                best_score = max(exact, partial, token, keyword_score)
                
                if best_score > threshold:
                    results.append({
                        "item": item,
                        "score": best_score
                    })
                    seen.add(item["answer"])
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:3]
    
    def _expand_query(self, query):
        """Expand query with synonyms"""
        expanded = [query]
        for word, syns in self.synonyms.items():
            if word in query:
                for syn in syns:
                    exp = query.replace(word, syn)
                    if exp not in expanded:
                        expanded.append(exp)
        return expanded

# =========================================================
# INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    @staticmethod
    def main_menu():
        """Main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("🏞️ Tourism", callback_data="menu_tourism"),
             InlineKeyboardButton("📜 History", callback_data="menu_history")],
            [InlineKeyboardButton("👥 Culture", callback_data="menu_culture"),
             InlineKeyboardButton("ℹ️ Practical", callback_data="menu_practical")],
            [InlineKeyboardButton("🦁 Wildlife", callback_data="menu_wildlife"),
             InlineKeyboardButton("🚀 Quick Facts", callback_data="menu_facts")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button():
        """Back to main menu button"""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")
        ]])
    
    @staticmethod
    def get_content(menu_id):
        """Get menu content"""
        content = {
            "menu_tourism": """🏞️ *Tourism & Travel*

**Top Destinations:**
• Etosha National Park - Wildlife paradise
• Sossusvlei - World's highest dunes  
• Swakopmund - Coastal adventures
• Fish River Canyon - Epic hiking
• Namib Desert - Oldest desert

**Travel Tips:**
• Best time: May-October
• Self-drive safaris popular
• Range from luxury to camping
• Must-see: Desert sunrise

Try asking: "Tell me about Etosha" or "Best time to visit Namibia"?""",

            "menu_history": """📜 *History & Heritage*

**Timeline:**
• Ancient rock art (6,000+ years)
• German colonization (1884-1915)
• South African mandate (1915-1990)
• Independence: March 21, 1990

**Historical Sites:**
• Twyfelfontein rock art (UNESCO)
• Kolmanskop ghost town
• Heroes' Acre memorial
• Independence Museum

Ask me: "Tell me about Namibia's independence"?""",

            "menu_culture": """👥 *Culture & People*

**Major Groups:**
• Ovambo (largest population)
• Herero (distinctive dresses)
• Himba (traditional lifestyle)
• San (ancient hunter-gatherers)

**Experiences:**
• Himba village visits
• Herero Day celebrations
• Traditional craft markets
• Local cuisine

Ask: "Tell me about Himba people"?""",

            "menu_practical": """ℹ️ *Practical Information*

**Essentials:**
• Currency: Namibian Dollar (NAD)
• Languages: English, Afrikaans, German
• Visa: 90 days on arrival
• Driving: Left side

**Climate:**
• Dry season: May-Oct (cooler)
• Wet season: Nov-Apr (hotter)
• Desert: Extreme temperatures
• 300+ sunny days/year

Ask: "What's the currency?" or "Visa requirements"?""",

            "menu_wildlife": """🦁 *Wildlife & Nature*

**Iconic Animals:**
• Desert-adapted elephants
• Black rhinos (conservation success)
• Desert lions
• Cheetahs (largest population)
• Oryx (national animal)

**Conservation:**
• 42% of land protected
• Community conservancies
• Rhino protection programs
• Eco-tourism focus

Ask: "Tell me about desert elephants"?""",

            "menu_facts": """🚀 *Quick Facts*

1. 🏜️ World's oldest desert (55-80M years)
2. 🌌 International Dark Sky Reserves
3. 👥 2nd lowest population density
4. 🦁 42% land under protection
5. ☀️ 300+ sunny days/year
6. 💎 4th largest uranium producer
7. 🎯 Last African colony independent
8. 🏞️ Desert to wetlands diversity
9. 🇳🇦 Named after Namib Desert

Ask me: "Namibia fun facts"?"""
        }
        
        return content.get(menu_id, "Information not available.")

# =========================================================
# INTELLIGENT BOT ENGINE
# =========================================================
class NamibiaBot:
    def __init__(self):
        self.kb = IntelligentKnowledgeBase()
        self.last_activity = {}
        self.welcomed_users = set()
        logger.info("🧠 Bot engine initialized")
    
    def analyze_message(self, message, user_id, chat_id):
        """Analyze if bot should respond"""
        msg = message.lower().strip()
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Direct mentions - 100%
        if any(x in msg for x in ["@namibiabot", "namibia bot", "hey bot"]):
            return True, "direct_mention"
        
        # Questions - 80%
        if "?" in msg or any(msg.startswith(w) for w in ["what", "how", "where", "when", "why", "who"]):
            return True, "question"
        
        # Greetings - 70%
        if any(g in msg.split() for g in ["hi", "hello", "hey", "morning", "evening"]):
            return random.random() < 0.7, "greeting"
        
        # Namibia mentions - 60%
        if "namibia" in msg:
            return random.random() < 0.6, "namibia_mention"
        
        # Specific topics - 75%
        topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", "desert"]
        if any(t in msg for t in topics):
            return random.random() < 0.75, "specific_topic"
        
        return False, None
    
    def generate_response(self, message, response_type, user_profiles_instance):
        """Generate intelligent response"""
        clean_msg = re.sub(r'@[^\s]*', '', message.lower()).strip()
        clean_msg = re.sub(r'(hey|hello)\s+(bot|namibia)', '', clean_msg).strip()
        
        # Search knowledge base
        if clean_msg and response_type in ["direct_mention", "question", "specific_topic", "namibia_mention"]:
            results = self.kb.intelligent_search(clean_msg)
            if results:
                best = results[0]
                user_profiles_instance.increment_knowledge_query()
                
                response = f"🤔 *{best['item']['question'].title()}*\n\n"
                response += f"{best['item']['answer']}\n\n"
                response += f"💡 *Category: {best['item']['category']}*\n"
                response += "Use /menu for more topics!"
                return response
        
        # Fallback responses
        responses = {
            "direct_mention": "🇳🇦 Yes! What would you like to know about Namibia?",
            "greeting": "👋 Hello! Ready to explore Namibia? Ask me anything!",
            "question": "💡 Try asking about specific topics like 'Etosha' or 'Himba culture'!",
            "namibia_mention": "🦁 Talking about Namibia? I have so much to share!",
            "specific_topic": "🎯 Use /menu for organized information about that topic!"
        }
        
        return responses.get(response_type, "🇳🇦 Ask me about Namibia!")
    
    def generate_welcome(self, name):
        """Welcome new members"""
        welcomes = [
            f"👋 Welcome {name}! I'm your AI Namibia expert. Ask me anything! 🇳🇦",
            f"🌟 Hello {name}! Ready to explore Namibia together? 🦁",
            f"🇳🇦 Welcome {name}! I'm here to answer all your Namibia questions! 🏜️"
        ]
        return random.choice(welcomes)

# =========================================================
# INITIALIZE GLOBAL INSTANCES
# =========================================================
user_profiles = UserProfile()
bot = NamibiaBot()
menu = InteractiveMenu()

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = """🇳🇦 *Intelligent NamibiaBot Activated!*

I'm your AI-powered Namibia assistant! 🧠

*I can help with:*
• Answering questions about Namibia
• Travel planning & recommendations
• Cultural insights & history
• Wildlife information
• Practical travel advice

*How to use:*
• Ask questions naturally
• Use /menu for categories
• Tag me for specific answers
• I'll join conversations too!

*Try:* "Best time to visit Namibia?" or "Tell me about Etosha"

*Commands:*
/menu - Interactive knowledge
/stats - Statistics (admin)
/help - Help information"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! Add me to a group to explore Namibia together! 🇳🇦",
            parse_mode="Markdown"
        )
    
    user_profiles.get_user(user.id)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu"""
    await update.message.reply_text(
        "🧠 *Namibia Knowledge System*\n\nSelect a category:",
        parse_mode="Markdown",
        reply_markup=menu.main_menu()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        stats = f"""📊 *Bot Statistics*

*Engagement:*
• Total users: {len(user_profiles.profiles)}
• Active users: {sum(1 for p in user_profiles.profiles.values() if p.get('group_messages', 0) > 0)}
• Bot interactions: {sum(p.get('bot_interactions', 0) for p in user_profiles.profiles.values())}
• Knowledge queries: {user_profiles.group_stats.get('knowledge_queries', 0)}
• Total messages: {user_profiles.group_stats.get('total_messages', 0)}

*System:*
• Knowledge entries: {len(bot.kb.knowledge)}
• Categories: {len(bot.kb.categories)}
• Status: ✅ Active"""
        
        await update.message.reply_text(stats, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "🇳🇦 I'm your Namibia assistant! Use /menu or ask me anything!",
            parse_mode="Markdown"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    help_text = """🆘 *NamibiaBot Help*

*I'm an AI-powered Namibia expert!*

*I can:*
• Answer questions intelligently
• Provide travel information
• Share cultural insights
• Help with trip planning
• Welcome new members

*Usage:*
• Ask natural questions
• Use /menu for categories  
• Tag me for specific help

*Examples:*
"Best safari in Namibia?"
"Tell me about Himba culture"
"Namibia visa requirements"

*Commands:*
/menu - Knowledge system
/stats - Statistics
/help - This message"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages"""
    if update.message.from_user.id == context.bot.id:
        return
    
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name
    
    # Track message
    user_profiles.increment_group_message(user_id, username, full_name)
    
    # Analyze and respond
    should_respond, response_type = bot.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        response = bot.generate_response(message, response_type, user_profiles)
        
        if response:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            try:
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                user_profiles.increment_bot_interaction(user_id)
            except Exception as e:
                logger.error(f"Error sending response: {e}")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                continue
            
            welcome = bot.generate_welcome(member.first_name)
            user_profiles.add_new_member(member.id, member.username or "", member.full_name)
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
            "🧠 *Namibia Knowledge System*\n\nSelect a category:",
            parse_mode="Markdown",
            reply_markup=menu.main_menu()
        )
    elif data.startswith("menu_"):
        content = menu.get_content(data)
        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=menu.back_button()
        )

# =========================================================
# MAIN APPLICATION
# =========================================================
def main():
    """Run the bot"""
    logger.info("=" * 60)
    logger.info("🧠 INTELLIGENT NAMIBIA BOT")
    logger.info("=" * 60)
    logger.info(f"✅ Knowledge: {len(bot.kb.knowledge)} entries")
    logger.info(f"✅ Categories: {len(bot.kb.categories)}")
    logger.info(f"✅ Admins: {len(ADMIN_IDS)}")
    logger.info("=" * 60)
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers (order matters!)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    
    logger.info("🚀 Bot running...")
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()