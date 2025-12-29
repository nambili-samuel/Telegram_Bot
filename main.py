#!/usr/bin/env python3
"""
Intelligent Namibia Chatbot with Database Integration
Main bot file that connects Telegram interface with database and knowledge base
"""

import os
import random
import re
import asyncio
from datetime import datetime, timedelta
from rapidfuzz import fuzz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Import Database and KnowledgeBase classes
from database import Database
from knowledge_base import KnowledgeBase

# =========================================================
# CONFIGURATION
# =========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set in Railway variables")
    exit(1)

# Parse admin IDs
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set()
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = set(map(int, ADMIN_IDS_STR.split(',')))
    except:
        pass

# =========================================================
# DATABASE INITIALIZATION
# =========================================================
print("📊 Initializing database...")
db = Database()
kb_db = KnowledgeBase()
print(f"✅ Database initialized: {db.db_path}")
print(f"✅ Knowledge Base: {len(kb_db.get_all_topics())} topics available")

# =========================================================
# USER PROFILES & GROUP STATISTICS
# =========================================================
class UserProfile:
    """User profile management using Database"""
    def __init__(self):
        print("👤 User profile system initialized")
    
    def get_user(self, user_id):
        """Get user stats from database"""
        return db.get_user_stats(user_id)
    
    def update_user_activity(self, user_id, username="", full_name=""):
        """Update user activity in database"""
        # Use username or full_name if available
        name_to_use = username or full_name or f"User_{user_id}"
        db.add_user(user_id, name_to_use)
    
    def increment_bot_interaction(self, user_id):
        """Log bot interaction"""
        db.log_query(user_id, "bot_interaction")
    
    def log_query(self, user_id, query):
        """Log user query to database"""
        if query and query.strip():
            db.log_query(user_id, query.strip())

user_profiles = UserProfile()

# =========================================================
# INTELLIGENT KNOWLEDGE BASE SYSTEM
# =========================================================
class IntelligentKnowledgeBase:
    """Enhanced knowledge base with fuzzy matching"""
    def __init__(self):
        print(f"🧠 Intelligent knowledge base initialized")
        self.setup_synonyms()
        self.all_topics = kb_db.get_all_topics()
        self.categories = kb_db.get_categories()
    
    def setup_synonyms(self):
        """Setup synonym dictionary for intelligent matching"""
        self.synonyms = {
            'namibia': ['namibian', 'namibias', 'namib'],
            'windhoek': ['capital', 'city', 'main city'],
            'etosha': ['etosha park', 'national park', 'wildlife park'],
            'sossusvlei': ['sand dunes', 'namib desert', 'dunes', 'red dunes'],
            'swakopmund': ['coastal town', 'german town', 'beach town', 'coast'],
            'fish river': ['canyon', 'fish river canyon', 'hiking canyon'],
            'himba': ['red people', 'ochre people', 'tribal people', 'indigenous'],
            'herero': ['victorian dress', 'traditional dress', 'herero women'],
            'visa': ['entry requirements', 'travel documents', 'permit'],
            'currency': ['money', 'cash', 'nad', 'namibian dollar'],
            'weather': ['climate', 'temperature', 'season', 'rain'],
            'wildlife': ['animals', 'safari', 'game', 'fauna'],
            'history': ['past', 'historical', 'heritage'],
            'culture': ['people', 'traditions', 'customs', 'ethnic'],
            'travel': ['tourism', 'visit', 'vacation', 'holiday', 'trip'],
            'desert': ['arid', 'dry', 'sand', 'namib'],
            'elephant': ['elephants', 'pachyderm'],
            'lion': ['lions', 'big cat', 'predator'],
            'cheetah': ['cheetahs', 'fastest animal']
        }
    
    def expand_query(self, query):
        """Expand query with synonyms"""
        query_lower = query.lower()
        expanded = [query_lower]
        
        for word, synonyms in self.synonyms.items():
            if word in query_lower:
                for synonym in synonyms:
                    expanded_query = query_lower.replace(word, synonym)
                    if expanded_query not in expanded:
                        expanded.append(expanded_query)
        
        return expanded
    
    def intelligent_search(self, query, threshold=60):
        """Intelligent search using database knowledge base"""
        if not query or not query.strip():
            return []
        
        clean_query = query.strip().lower()
        
        # Try direct search first
        results = kb_db.search(clean_query, limit=10)
        
        enhanced_results = []
        seen_content = set()
        
        for result in results:
            if result['content'] in seen_content:
                continue
            
            # Calculate relevance scores
            topic_match = fuzz.partial_ratio(clean_query, result['topic'].lower())
            content_match = fuzz.partial_ratio(clean_query, result['content'].lower())
            
            # Keyword matching
            keywords = result.get('keywords', '').split(',') if result.get('keywords') else []
            keyword_score = 0
            if keywords:
                query_words = set(re.findall(r'\b\w+\b', clean_query.lower()))
                keyword_set = set(k.strip().lower() for k in keywords if k.strip())
                common = query_words & keyword_set
                if common:
                    keyword_score = (len(common) / max(len(query_words), len(keyword_set))) * 100
            
            best_score = max(topic_match, content_match, keyword_score)
            
            if best_score > threshold:
                enhanced_results.append({
                    "item": {
                        "category": result['category'],
                        "question": result['topic'],
                        "answer": result['content'],
                        "keywords": keywords
                    },
                    "score": best_score,
                    "matched_query": clean_query
                })
                seen_content.add(result['content'])
        
        # If no results, try synonym expansion
        if not enhanced_results:
            expanded_queries = self.expand_query(clean_query)
            for expanded_query in expanded_queries:
                if expanded_query != clean_query:
                    synonym_results = kb_db.search(expanded_query, limit=5)
                    for result in synonym_results:
                        if result['content'] not in seen_content:
                            enhanced_results.append({
                                "item": {
                                    "category": result['category'],
                                    "question": result['topic'],
                                    "answer": result['content'],
                                    "keywords": result.get('keywords', '').split(',') if result.get('keywords') else []
                                },
                                "score": 75,  # Good match via synonym
                                "matched_query": expanded_query
                            })
                            seen_content.add(result['content'])
        
        # Sort by score
        enhanced_results.sort(key=lambda x: x["score"], reverse=True)
        return enhanced_results[:5]  # Return top 5 results
    
    def get_random_fact(self):
        """Get a random fact from knowledge base"""
        if self.all_topics:
            random_topic = random.choice(self.all_topics)
            results = kb_db.search(random_topic, limit=1)
            if results:
                return {
                    "question": results[0]['topic'],
                    "answer": results[0]['content'],
                    "category": results[0]['category']
                }
        return None
    
    def get_by_category(self, category):
        """Get all topics in a category"""
        return kb_db.get_by_category(category)

# =========================================================
# INTELLIGENT CHATBOT ENGINE
# =========================================================
class IntelligentNamibiaBot:
    """Main chatbot engine"""
    def __init__(self):
        self.knowledge_base = IntelligentKnowledgeBase()
        self.conversation_context = {}
        self.user_interests = {}
        self.last_activity = {}
        self.welcomed_users = set()
        print("🤖 Intelligent Namibia Bot initialized")
    
    def analyze_message(self, message, user_id, chat_id):
        """Intelligently analyze message for response"""
        message_lower = message.lower().strip()
        
        # Update activity
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Get response decision
        return self.decide_response(message_lower, user_id, chat_id)
    
    def decide_response(self, message, user_id, chat_id):
        """Intelligently decide whether and how to respond"""
        response_types = []
        
        # 1. Direct mentions (100% response)
        bot_mentions = ["@namibiabot", "@namibia_bot", "namibia bot", "hey bot", "hello bot", "bot,", "bot!"]
        if any(mention in message for mention in bot_mentions):
            response_types.append(("direct_mention", 100))
        
        # 2. Greetings (70% response)
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "moro", "greetings"]
        if any(greeting in message.lower().split() for greeting in greetings):
            response_types.append(("greeting", 70))
        
        # 3. Questions with ? or question words (80% response)
        question_words = ["what", "how", "where", "when", "why", "who", "which", "can you", "tell me", "explain"]
        if "?" in message or any(message.lower().startswith(word) for word in question_words):
            response_types.append(("question", 80))
        
        # 4. Namibia mentions (60% response)
        if "namibia" in message.lower() or "namibian" in message.lower():
            response_types.append(("namibia_mention", 60))
        
        # 5. Knowledge base topics (75% response)
        kb_topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", "desert", "dunes", "fish river", "cheetah", "elephant", "lion"]
        if any(topic in message.lower() for topic in kb_topics):
            response_types.append(("specific_topic", 75))
        
        # 6. Travel keywords (50% response)
        travel_words = ["travel", "tour", "visit", "trip", "vacation", "holiday", "safari", "destination", "tourist"]
        if any(word in message.lower() for word in travel_words):
            response_types.append(("travel", 50))
        
        # 7. If no specific triggers, check for conversation starter
        if self.is_chat_quiet(chat_id, minutes=20):
            if random.random() < 0.4:  # 40% chance if chat is quiet
                response_types.append(("conversation_starter", 40))
        
        # Sort by priority
        if response_types:
            response_types.sort(key=lambda x: x[1], reverse=True)
            top_response = response_types[0]
            
            # Check if we should respond based on probability
            if top_response[1] >= 40 and random.random() < (top_response[1] / 100):
                return True, top_response[0]
        
        return False, None
    
    def is_chat_quiet(self, chat_id, minutes=5):
        """Check if chat has been quiet"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_activity:
            return True
        
        last_active = self.last_activity[chat_id_str]
        quiet_time = datetime.now() - last_active
        
        return quiet_time > timedelta(minutes=minutes)
    
    def generate_response(self, message, response_type, user_id=None):
        """Generate intelligent response based on type"""
        message_lower = message.lower().strip()
        
        # Clean message for knowledge search
        clean_message = re.sub(r'@[^\s]*', '', message_lower)
        clean_message = re.sub(r'(hey|hello)\s+(bot|namibia)', '', clean_message).strip()
        
        # Log the query to database
        if user_id and clean_message:
            user_profiles.log_query(user_id, clean_message)
        
        # Always try knowledge base search for relevant response types
        should_search = response_type in ["direct_mention", "question", "specific_topic", "namibia_mention", "travel"]
        
        if clean_message and should_search:
            results = self.knowledge_base.intelligent_search(clean_message)
            if results:
                best_result = results[0]
                
                # Format response
                response = f"🤔 *Based on your question:*\n\n"
                response += f"**{best_result['item']['question'].title()}**\n"
                response += f"{best_result['item']['answer']}\n\n"
                
                # Add related info if available
                related = self.get_related_info(best_result['item']['category'], best_result['item']['question'])
                if related:
                    response += f"💡 *Related information:*\n{related}\n\n"
                
                # Add interactive element
                response += self.get_interactive_suggestion(best_result['item']['category'])
                return response
        
        # Generate appropriate response based on type
        responses = {
            "direct_mention": [
                "🇳🇦 Yes, I'm here! What would you like to know about Namibia?",
                "🦁 Hello! I'm your Namibia expert. Ask me anything!",
                "🏜️ NamibiaBot at your service! How can I help you today?",
                "🇳🇦 Heard my name! Ready to explore Namibia together?"
            ],
            "greeting": [
                "🇳🇦 Hello there! Ready to explore Namibia together?",
                "👋 Hi! I'm excited to chat about Namibia with you!",
                "🇳🇦 Moro! (That's hello in Oshiwambo) 🇳🇦",
                "👋 Welcome to the Namibia discussion! How can I assist you today?"
            ],
            "question": [
                "💡 That's an interesting question about Namibia! Let me share what I know...",
                "🤔 I might have information about that. Could you try rephrasing?",
                "🇳🇦 Interesting question! Try asking about specific topics like 'Etosha National Park' or 'Himba culture'.",
                "🧐 I'm learning more about Namibia every day! For now, try /menu for organized information."
            ],
            "namibia_mention": [
                "🌟 You mentioned Namibia! My favorite topic!",
                "🦁 Talking about Namibia? I have so much to share!",
                "🏜️ Namibia is truly amazing, isn't it?",
                "🇳🇦 Ah, talking about my favorite country! What would you like to know?"
            ],
            "specific_topic": [
                "🎯 That's a specific Namibia topic! I might have information on that.",
                "📚 I know about many Namibia topics. Try asking more specifically!",
                "🔍 Good topic! For detailed information, try /menu → Wildlife & Nature",
                "🎯 That's one of Namibia's highlights! Use /menu for organized info."
            ],
            "travel": [
                "🗺️ Planning a Namibia adventure? I can help!",
                "🦓 Safari planning is exciting! Namibia has incredible wildlife.",
                "🌅 Travel to Namibia will be unforgettable!",
                "🎒 Need travel tips for Namibia? I'm your guide!"
            ],
            "conversation_starter": self.get_conversation_starter()
        }
        
        if response_type in responses:
            if isinstance(responses[response_type], list):
                response = random.choice(responses[response_type])
            else:
                response = responses[response_type]
            
            # Add knowledge base suggestion 40% of time
            if random.random() < 0.4 and response_type not in ["conversation_starter"]:
                response += "\n\n" + self.get_knowledge_suggestion()
            
            return response
        
        return None
    
    def get_related_info(self, category, current_question):
        """Get related information from same category"""
        related_items = []
        category_items = self.knowledge_base.get_by_category(category)
        
        if category_items:
            for item in category_items:
                if isinstance(item, dict) and 'topic' in item:
                    if item['topic'].lower() != current_question.lower() and len(related_items) < 2:
                        related_items.append(f"• {item['topic'].title()}")
        
        if related_items:
            return "\n".join(related_items)
        return ""
    
    def get_interactive_suggestion(self, category):
        """Get interactive suggestion based on category"""
        suggestions = {
            "Tourism": "🌍 *Want more travel tips?* Try /menu → Tourism",
            "Culture": "👥 *Interested in people?* Try /menu → Culture",
            "History": "📜 *More history?* Try /menu → History",
            "Geography": "🗺️ *Geography questions?* Try /menu → Quick Facts",
            "Wildlife": "🦓 *Wildlife lover?* Try /menu → Wildlife & Nature",
            "Practical": "ℹ️ *Practical questions?* Try /menu → Practical Info",
            "Facts": "🚀 *More facts?* Try /menu → Quick Facts"
        }
        
        return suggestions.get(category, "📱 *Explore more:* Use /menu for categories")
    
    def get_knowledge_suggestion(self):
        """Get random knowledge base suggestion"""
        suggestions = [
            "💡 *Did you know?* I can answer specific questions about Namibia! Try asking me anything.",
            "🔍 *Curious?* Ask me about Namibia's wildlife, culture, or travel tips!",
            "📚 *Knowledge base:* I have information on 20+ Namibia topics. What interests you?",
            "🤔 *Question time:* What would you like to know about Namibia today?"
        ]
        return random.choice(suggestions)
    
    def get_conversation_starter(self):
        """Get intelligent conversation starter"""
        starters = [
            "💭 *Thought for the group:* What's your dream Namibia destination?",
            "🦁 *Wildlife question:* Who has seen desert-adapted animals in Namibia?",
            "🏜️ *Desert discussion:* What fascinates you most about the Namib Desert?",
            "👥 *Cultural curiosity:* What Namibia culture would you like to learn about?",
            "🗺️ *Travel talk:* What's the most surprising thing about Namibia travel?",
            "🌅 *Sunrise question:* Has anyone experienced sunrise at Sossusvlei?"
        ]
        return random.choice(starters)
    
    def generate_welcome_message(self, new_member_name):
        """Generate personalized welcome message"""
        welcomes = [
            f"👋 Welcome to the group, {new_member_name}! I'm an AI Assistant, here to help with all things Namibia! 🇳🇦",
            f"🌟 Hello {new_member_name}! Great to have you here. Ask me anything about Namibia's wildlife, culture, or travel tips! 🦁",
            f"🇳🇦 Welcome {new_member_name}! Ready to explore Namibia together? I'm your AI assistant for all Namibia topics! 🏜️",
            f"🦓 Greetings {new_member_name}! I'm here to make your Namibia discussions more engaging. Feel free to ask questions! 🌅"
        ]
        return random.choice(welcomes)

# =========================================================
# INTERACTIVE MENU SYSTEM
# =========================================================
class InteractiveMenu:
    """Interactive menu system using database categories"""
    def __init__(self):
        self.categories = kb_db.get_categories()
        print(f"📋 Menu system initialized with {len(self.categories)} categories")
    
    def create_main_menu(self):
        """Create enhanced main menu using database categories"""
        keyboard = []
        
        # Map database categories to menu items with emojis
        category_emojis = {
            "Tourism": "🏞️",
            "History": "📜",
            "Culture": "👥",
            "Practical": "ℹ️",
            "Wildlife": "🦓",
            "Geography": "🗺️",
            "Facts": "🚀"
        }
        
        # Add database categories
        for category in self.categories:
            emoji = category_emojis.get(category, "📌")
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {category}", 
                    callback_data=f"menu_{category.lower()}"
                )
            ])
        
        # Add admin button if user is admin
        keyboard.append([
            InlineKeyboardButton("📊 Statistics", callback_data="menu_stats"),
            InlineKeyboardButton("❓ Help", callback_data="menu_help")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_category_menu(self, category):
        """Create submenu for a specific category"""
        topics = kb_db.get_by_category(category)
        keyboard = []
        
        if topics:
            # Add up to 8 topics as buttons
            for i, topic in enumerate(topics[:8]):
                topic_name = topic['topic'][:25] + "..." if len(topic['topic']) > 25 else topic['topic']
                keyboard.append([
                    InlineKeyboardButton(
                        f"📌 {topic_name}", 
                        callback_data=f"topic_{i}_{category.lower()}"
                    )
                ])
        
        # Add navigation buttons
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="menu_back"),
            InlineKeyboardButton("🏠 Home", callback_data="menu_home")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_category_info(self, category):
        """Get information about a category"""
        topics = kb_db.get_by_category(category)
        
        if topics:
            response = f"*{category}*\n\n"
            response += f"*Total Topics:* {len(topics)}\n\n"
            
            # Show first 3 topics as examples
            for i, topic in enumerate(topics[:3]):
                response += f"• {topic['topic']}\n"
            
            if len(topics) > 3:
                response += f"\n... and {len(topics) - 3} more topics\n\n"
            
            response += "Select a topic below for detailed information:"
            
            return response
        else:
            return f"*{category}*\n\nNo topics found in this category."

# =========================================================
# BOT INSTANCES
# =========================================================
bot_instance = IntelligentNamibiaBot()
menu_system = InteractiveMenu()

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Add user to database
    user_profiles.update_user_activity(user.id, user.username, user.first_name)
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = f"""🇳🇦 *Intelligent NamibiaBot v2.0*

Hello everyone! I'm Eva Geises your AI assistant with developed by ScienceTechniz! 🧠

*Database Features:*
• 📊 User tracking with SQLite
• 🔍 Full-text search (FTS5)
• 📚 {len(kb_db.get_all_topics())} knowledge topics
• 🏷️ {len(kb_db.get_categories())} organized categories

*How to use me:*
1. Ask questions about Namibia
2. Use /menu for organized categories
3. Tag me (@namibiabot) for direct answers
4. I'll welcome new members automatically

*Try asking:*
• "What is the best time to visit Namibia?"
• "Tell me about Etosha National Park"
• "What's unique about Himba culture?"
• "Namibia travel tips"

*Commands:*
/menu - Interactive system
/stats - View statistics
/help - Help information
/start - Restart me

🇳🇦 Let's explore Namibia together!"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        # Private message response
        response = f"""🇳🇦 Hi {user.first_name}! I'm an AI Assistant.

I'm designed for group conversations about Namibia.

*My Roles:*
• Help you learning about Namibia
• Act as Tour Guide
• Handling normal FAQs
• Discovery Opportunities in Namibia

*To use me:*
1. Add me to a Telegram group
2. Use /start in the group
3. Start asking questions!

*Group Features:*
• I can respond to any question
• Check my interactive menus here (/menu)
• I can welcome new members
• Conversation engagement

Add me to your group now!"""
        
        await update.message.reply_text(response, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command"""
    await update.message.reply_text(
        "🧠 *Namibia Knowledge System*\n\nSelect a category to explore:",
        parse_mode="Markdown",
        reply_markup=menu_system.create_main_menu()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    
    # Get user stats from database
    user_stats = db.get_user_stats(user_id)
    
    # Get popular queries
    popular_queries = db.get_popular_queries(5)
    
    # Get all users
    all_users = db.get_all_users()
    
    if ADMIN_IDS and user_id in ADMIN_IDS:
        # Admin stats
        stats = f"""📊 *Database Statistics (Admin View)*

*User Statistics:*
• Total users: {len(all_users)}
• Active users: {sum(1 for user in all_users)}
• Your query count: {user_stats['query_count']}

*Knowledge Base:*
• Topics: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}
• Database: {db.db_path}

*Popular Queries:*
"""
        for i, query in enumerate(popular_queries, 1):
            stats += f"{i}. {query['query'][:30]}... ({query['count']}x)\n"
        
        stats += f"\n*System Status:* Active ✅"
    else:
        # User stats
        stats = f"""📊 *Your NamibiaBot Statistics*

*Your Activity:*
• Queries made: {user_stats['query_count']}
• Joined: {user_stats['joined_date'][:10] if user_stats['joined_date'] != 'Unknown' else 'Recently'}
• Last active: {user_stats['last_query'][:19] if user_stats['last_query'] else 'Now'}

*Knowledge Available:*
• Topics: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}

Keep exploring Namibia! Ask me anything about our beautiful country, in Africa."""
    
    await update.message.reply_text(stats, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🆘 *NamibiaBot Help*

*Database-Powered Features:*
• SQLite database for persistence
• Full-text search with FTS5
• User activity tracking
• Query history logging

*How to interact:*
1. Ask questions about Namibia
2. Use /menu for organized categories
3. Tag me (@namibiabot) for direct answers
4. Welcome new members automatically

*Available Commands:*
/start - Start or restart the bot
/menu - Interactive knowledge system
/stats - View your statistics
/help - This help message
/add_knowledge - Add new knowledge (admin)

*Ask about:*
• Wildlife & Nature 🦓
• Tourism & Travel 🏞️
• Culture & People 👥
• History & Heritage 📜
• Practical Information ℹ️
• Geography & Facts 🗺️

All your interactions are stored in our database for better assistance!"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_knowledge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to add knowledge"""
    user_id = update.effective_user.id
    
    if ADMIN_IDS and user_id in ADMIN_IDS:
        if not context.args:
            await update.message.reply_text(
                "Usage: /add_knowledge <topic> | <content> | [category] | [keywords]\n\n"
                "Example: /add_knowledge Windhoek | Capital city of Namibia | Geography | capital, city",
                parse_mode="Markdown"
            )
            return
        
        # Parse arguments
        text = ' '.join(context.args)
        parts = text.split('|')
        
        if len(parts) < 2:
            await update.message.reply_text("Error: Need at least topic and content separated by |")
            return
        
        topic = parts[0].strip()
        content = parts[1].strip()
        category = parts[2].strip() if len(parts) > 2 else "General"
        keywords = parts[3].strip() if len(parts) > 3 else ""
        
        # Add to knowledge base
        kb_db.add_knowledge(topic, content, category, keywords)
        
        await update.message.reply_text(
            f"✅ *Knowledge Added Successfully*\n\n"
            f"**Topic:** {topic}\n"
            f"**Category:** {category}\n"
            f"**Keywords:** {keywords}\n\n"
            f"*Content preview:*\n{content[:200]}...",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("This command is for administrators only.")

# =========================================================
# MESSAGE HANDLERS
# =========================================================
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all group messages intelligently"""
    # Skip bot's own messages
    if update.message.from_user.id == context.bot.id:
        return
    
    # Skip non-text messages
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name
    
    # Update user in database
    user_profiles.update_user_activity(user_id, username, full_name)
    
    # Analyze message and decide response
    should_respond, response_type = bot_instance.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        print(f"🤖 Response triggered: {response_type} for: {message[:50]}...")
        
        # Generate intelligent response
        response = bot_instance.generate_response(message, response_type, user_id)
        
        if response:
            # Natural delay for realistic interaction
            delay = random.uniform(0.5, 2.0)
            await asyncio.sleep(delay)
            
            # Send response
            try:
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
                
                # Track interaction
                user_profiles.increment_bot_interaction(user_id)
                
                print(f"✅ Sent response: {response_type}")
            except Exception as e:
                print(f"❌ Error sending response: {e}")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining the group"""
    if update.message.new_chat_members:
        for new_member in update.message.new_chat_members:
            # Skip if the new member is the bot itself
            if new_member.id == context.bot.id:
                continue
            
            # Add to database
            user_profiles.update_user_activity(
                new_member.id, 
                new_member.username or "", 
                new_member.full_name
            )
            
            # Generate welcome message
            welcome_msg = bot_instance.generate_welcome_message(new_member.first_name)
            
            # Add to welcomed users set
            bot_instance.welcomed_users.add(new_member.id)
            
            # Send welcome message with delay
            await asyncio.sleep(1)
            await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages"""
    if update.message.chat.type == 'private':
        user = update.effective_user
        
        response = """🇳🇦 *Hi! I'm NamibiaBot*

I'm an AI assistant designed for group conversations about Namibia.

*Current Features:*
• Database-powered knowledge base
• Full-text search capabilities
• User activity tracking
• Interactive menu system

*To use me:*
1. Add me to your Telegram group
2. Type /start in the group
3. Start asking questions about Namibia!

*In groups, I can:*
• Answer questions intelligently
• Provide detailed information
• Welcome new members
• Start conversations
• Help with travel planning

Add me to a group and let's explore Namibia together! 🦁"""
        
        await update.message.reply_text(response, parse_mode="Markdown")

# =========================================================
# BUTTON HANDLER
# =========================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button interactions"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_back":
        # Return to main menu
        await query.edit_message_text(
            "🧠 *Namibia Knowledge System*\n\nSelect a category to explore:",
            parse_mode="Markdown",
            reply_markup=menu_system.create_main_menu()
        )
    
    elif data == "menu_home":
        # Return to start
        await query.edit_message_text(
            "🏠 *Main Menu*\n\nUse /menu to explore categories or ask me anything about Namibia!",
            parse_mode="Markdown"
        )
    
    elif data == "menu_stats":
        # Show statistics
        user_id = query.from_user.id
        user_stats = db.get_user_stats(user_id)
        
        stats_text = f"""📊 *Your Statistics*

*Activity:*
• Queries: {user_stats['query_count']}
• Joined: {user_stats['joined_date'][:10] if user_stats['joined_date'] != 'Unknown' else 'Recently'}
• Last active: Now

*Knowledge Base:*
• Topics: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
        
        await query.edit_message_text(
            stats_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "menu_help":
        # Show help
        help_text = """❓ *Quick Help*

*How to use:*
• Ask questions about Namibia
• Use buttons to explore categories
• Tag me for direct answers

*Commands:*
/menu - Show this menu
/stats - Your statistics
/help - Detailed help

Select a category to explore!"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
        
        await query.edit_message_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("menu_"):
        # Handle category menu
        category_name = data.replace("menu_", "").capitalize()
        category_info = menu_system.get_category_info(category_name)
        
        await query.edit_message_text(
            category_info,
            parse_mode="Markdown",
            reply_markup=menu_system.create_category_menu(category_name)
        )
    
    elif data.startswith("topic_"):
        # Handle topic selection
        parts = data.split("_")
        if len(parts) >= 3:
            topic_index = int(parts[1])
            category = parts[2].capitalize()
            
            topics = kb_db.get_by_category(category)
            
            if topics and 0 <= topic_index < len(topics):
                topic = topics[topic_index]
                
                response = f"**{topic['topic']}**\n\n"
                response += f"{topic['content']}\n\n"
                
                if topic.get('keywords'):
                    response += f"*Keywords:* {topic['keywords']}\n\n"
                
                response += f"*Category:* {category}"
                
                keyboard = [
                    [InlineKeyboardButton("⬅️ Back to Category", callback_data=f"menu_{category.lower()}")],
                    [InlineKeyboardButton("🏠 Home", callback_data="menu_home")]
                ]
                
                await query.edit_message_text(
                    response,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
        
        # Fallback
        await query.edit_message_text(
            "Topic information not found. Please try another topic.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]])
        )

# =========================================================
# MAIN APPLICATION
# =========================================================
def main():
    """Main application entry point"""
    print("=" * 60)
    print("🇳🇦 INTELLIGENT NAMIBIA CHATBOT")
    print("=" * 60)
    print(f"✅ Bot Token: {'Set' if TELEGRAM_BOT_TOKEN else 'Not Set'}")
    print(f"✅ Database: {db.db_path}")
    print(f"✅ Knowledge Base: {len(kb_db.get_all_topics())} topics")
    print(f"✅ Categories: {len(kb_db.get_categories())}")
    print(f"✅ Admin IDs: {len(ADMIN_IDS)} configured")
    print("=" * 60)
    print("✨ Features Enabled:")
    print("   • SQLite database with FTS5 search")
    print("   • Intelligent response system")
    print("   • Interactive menu system")
    print("   • User activity tracking")
    print("   • Query logging and analytics")
    print("=" * 60)
    print("🚀 Starting bot...")
    
    # Create application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers (highest priority)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('add_knowledge', add_knowledge_command))
    
    # Button handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # New member handler
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_members
    ))
    
    # Group message handler
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS,
        handle_group_message
    ))
    
    # Private message handler (lowest priority)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        handle_private_message
    ))
    
    # Start bot
    print("🤖 Bot is running... Press Ctrl+C to stop")
    print("💡 Test commands in a group:")
    print("   • /start - Initialize bot")
    print("   • /menu - Show interactive menu")
    print("   • Ask 'What is the capital of Namibia?'")
    print("   • Try 'Tell me about Etosha'")
    print("=" * 60)
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
