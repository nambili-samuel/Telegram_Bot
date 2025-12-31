#!/usr/bin/env python3
"""
Intelligent Namibia Chatbot with Enhanced Question Answering
Main bot file with improved intelligence for direct question answering
"""

import os
import random
import re
import asyncio
from datetime import datetime, timedelta
from rapidfuzz import fuzz, process
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
# ENHANCED INTELLIGENT KNOWLEDGE BASE SYSTEM
# =========================================================
class EnhancedKnowledgeBase:
    """Enhanced knowledge base with better question answering"""
    def __init__(self):
        print(f"🧠 Enhanced knowledge base initialized")
        self.all_topics = kb_db.get_all_topics()
        self.categories = kb_db.get_categories()
        self.setup_synonyms()
        self.setup_question_patterns()
        self.load_all_knowledge()
    
    def load_all_knowledge(self):
        """Load all knowledge into memory for faster access"""
        self.knowledge_cache = {}
        for category in self.categories:
            self.knowledge_cache[category] = kb_db.get_by_category(category)
        print(f"📚 Loaded {sum(len(items) for items in self.knowledge_cache.values())} knowledge items to cache")
    
    def setup_synonyms(self):
        """Setup enhanced synonym dictionary"""
        self.synonyms = {
            'where': ['location', 'situated', 'located', 'place', 'found'],
            'what': ['which', 'tell me about', 'describe', 'explain'],
            'how': ['way', 'method', 'process', 'manner'],
            'when': ['time', 'date', 'period', 'year'],
            'why': ['reason', 'cause', 'purpose', 'because'],
            'who': ['person', 'people', 'individual', 'group'],
            'capital': ['main city', 'administrative center', 'seat of government'],
            'population': ['people', 'inhabitants', 'residents', 'citizens'],
            'currency': ['money', 'cash', 'dollar', 'financial'],
            'weather': ['climate', 'temperature', 'season', 'conditions'],
            'language': ['tongue', 'speech', 'dialect', 'communication'],
            'culture': ['customs', 'traditions', 'heritage', 'way of life'],
            'history': ['past', 'heritage', 'background', 'chronicle'],
            'tourism': ['travel', 'visiting', 'sightseeing', 'vacation'],
            'wildlife': ['animals', 'fauna', 'creatures', 'beasts'],
            'desert': ['arid', 'dry', 'sand', 'wasteland'],
            'namibia': ['namibian', 'namibias', 'republic of namibia'],
            'windhoek': ['capital city', 'main city', 'administrative capital'],
            'etosha': ['etosha park', 'national park', 'game reserve'],
            'sossusvlei': ['sand dunes', 'red dunes', 'namib desert dunes'],
            'himba': ['red ochre people', 'himba tribe', 'indigenous himba'],
            'herero': ['herero tribe', 'victorian dress people', 'herero women'],
        }
    
    def setup_question_patterns(self):
        """Setup common question patterns"""
        self.question_patterns = {
            'where': [
                r'where (?:is|are) (?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river)',
                r'location of (?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river)',
                r'(?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river) (?:located|situated)'
            ],
            'what': [
                r'what (?:is|are) (?:the )?(?:capital|population|currency|language|weather)',
                r'what (?:is|are) (?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river|himba|herero)',
                r'tell me about (?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river|himba|herero)',
                r'describe (?:namibia|windhoek|etosha|sossusvlei|swakopmund|fish river|himba|herero)'
            ],
            'when': [
                r'when (?:is|was) (?:independence|best time to visit)',
                r'what time (?:to visit|for safari)',
                r'best season (?:for|to)'
            ],
            'how': [
                r'how (?:to get|to travel|big|large|old)',
                r'how (?:many|much|long|far)'
            ],
            'why': [
                r'why (?:visit|go to|is namibia)',
                r'what makes (?:namibia|etosha|sossusvlei)'
            ]
        }
    
    def extract_keywords(self, query):
        """Extract keywords from query"""
        words = re.findall(r'\b[a-z]+\b', query.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'do', 'does', 'did', 'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must'}
        return [word for word in words if word not in stop_words and len(word) > 2]
    
    def expand_query(self, query):
        """Expand query with synonyms and variations"""
        query_lower = query.lower()
        expanded = [query_lower]
        
        # Add question mark variations
        if query_lower.endswith('?'):
            expanded.append(query_lower[:-1].strip())
        else:
            expanded.append(query_lower + '?')
        
        # Add synonym expansions
        for word, synonyms in self.synonyms.items():
            if word in query_lower:
                for synonym in synonyms:
                    expanded_query = query_lower.replace(word, synonym)
                    if expanded_query not in expanded:
                        expanded.append(expanded_query)
        
        # Add common variations
        variations = [
            query_lower,
            query_lower.replace("what's", "what is"),
            query_lower.replace("where's", "where is"),
            query_lower.replace("when's", "when is"),
            query_lower.replace("how's", "how is"),
            query_lower.replace("why's", "why is"),
            query_lower.replace("who's", "who is"),
        ]
        
        for variation in variations:
            if variation not in expanded:
                expanded.append(variation)
        
        return expanded
    
    def match_question_pattern(self, query):
        """Match query against known question patterns"""
        query_lower = query.lower()
        
        for pattern_type, patterns in self.question_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return pattern_type
        
        # Check for question words
        question_words = ['what', 'where', 'when', 'why', 'how', 'who', 'which', 'can you', 'tell me', 'explain']
        for word in question_words:
            if query_lower.startswith(word) or f" {word} " in query_lower:
                return word
        
        return None
    
    def find_direct_answer(self, query):
        """Find direct answer to query in knowledge base"""
        # First try exact topic match
        for category, items in self.knowledge_cache.items():
            for item in items:
                if query.lower() in item['topic'].lower():
                    return {
                        'answer': item['content'],
                        'topic': item['topic'],
                        'category': category,
                        'confidence': 95
                    }
        
        # Try search with multiple strategies
        search_strategies = [
            self.search_by_keywords,
            self.search_by_fuzzy_matching,
            self.search_by_question_pattern,
            self.search_by_synonyms
        ]
        
        for strategy in search_strategies:
            result = strategy(query)
            if result and result['confidence'] > 70:
                return result
        
        return None
    
    def search_by_keywords(self, query):
        """Search by keyword matching"""
        keywords = self.extract_keywords(query)
        if not keywords:
            return None
        
        best_match = None
        best_score = 0
        
        for category, items in self.knowledge_cache.items():
            for item in items:
                # Extract item keywords from topic and content
                item_text = f"{item['topic']} {item.get('content', '')}".lower()
                item_keywords = self.extract_keywords(item_text)
                
                # Calculate keyword overlap
                common_keywords = set(keywords) & set(item_keywords)
                if common_keywords:
                    score = (len(common_keywords) / len(keywords)) * 100
                    
                    # Bonus for exact matches
                    for keyword in keywords:
                        if keyword in item['topic'].lower():
                            score += 20
                        if keyword in item.get('content', '').lower():
                            score += 10
                    
                    if score > best_score:
                        best_score = score
                        best_match = {
                            'answer': item['content'],
                            'topic': item['topic'],
                            'category': category,
                            'confidence': min(score, 100)
                        }
        
        return best_match if best_score > 50 else None
    
    def search_by_fuzzy_matching(self, query):
        """Search using fuzzy matching"""
        best_match = None
        best_score = 0
        
        # Collect all topics for matching
        all_topics = []
        for category, items in self.knowledge_cache.items():
            for item in items:
                all_topics.append((item['topic'], item['content'], category))
        
        # Use rapidfuzz for fuzzy matching
        for topic, content, category in all_topics:
            # Check direct topic match
            topic_score = fuzz.ratio(query.lower(), topic.lower())
            
            # Check if query contains topic keywords
            topic_words = set(topic.lower().split())
            query_words = set(query.lower().split())
            keyword_score = len(topic_words & query_words) / max(len(topic_words), 1) * 100
            
            # Combine scores
            score = max(topic_score, keyword_score)
            
            if score > best_score and score > 60:
                best_score = score
                best_match = {
                    'answer': content,
                    'topic': topic,
                    'category': category,
                    'confidence': score
                }
        
        return best_match
    
    def search_by_question_pattern(self, query):
        """Search based on question pattern"""
        pattern_type = self.match_question_pattern(query)
        if not pattern_type:
            return None
        
        # Map pattern to likely topics
        pattern_to_topic = {
            'where': ['Where is Namibia', 'Capital of Namibia', 'Location'],
            'what': ['What is', 'Capital', 'Population', 'Currency', 'Language'],
            'when': ['Best time to visit', 'Independence Day', 'When is'],
            'how': ['How to get', 'How big', 'How old'],
            'why': ['Why visit', 'What makes Namibia special']
        }
        
        likely_topics = pattern_to_topic.get(pattern_type, [])
        
        for topic_start in likely_topics:
            for category, items in self.knowledge_cache.items():
                for item in items:
                    if item['topic'].startswith(topic_start):
                        return {
                            'answer': item['content'],
                            'topic': item['topic'],
                            'category': category,
                            'confidence': 80
                        }
        
        return None
    
    def search_by_synonyms(self, query):
        """Search using synonym expansion"""
        expanded_queries = self.expand_query(query)
        
        for expanded_query in expanded_queries:
            if expanded_query == query.lower():
                continue
            
            result = self.find_direct_answer(expanded_query)
            if result:
                result['confidence'] = result['confidence'] * 0.9  # Slightly lower confidence for synonym matches
                return result
        
        return None

# =========================================================
# ENHANCED CHATBOT ENGINE
# =========================================================
class EnhancedNamibiaBot:
    """Enhanced chatbot engine with better question answering"""
    def __init__(self):
        self.knowledge_base = EnhancedKnowledgeBase()
        self.conversation_context = {}
        self.user_interests = {}
        self.last_activity = {}
        self.welcomed_users = set()
        print("🤖 Enhanced Namibia Bot initialized")
    
    def analyze_message(self, message, user_id, chat_id):
        """Enhanced message analysis"""
        message_lower = message.lower().strip()
        
        # Update activity
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Check if this is a question that needs answering
        is_question = self.is_question(message_lower)
        
        if is_question:
            # Always respond to direct questions
            response_type = "direct_question"
            return True, response_type
        
        # Check other triggers
        return self.check_response_triggers(message_lower, chat_id)
    
    def is_question(self, message):
        """Check if message is a question"""
        # Check for question mark
        if '?' in message:
            return True
        
        # Check for question words at start
        question_starts = ['what', 'where', 'when', 'why', 'how', 'who', 'which', 'can you', 'tell me', 'explain', 'is there', 'are there']
        for start in question_starts:
            if message.startswith(start):
                return True
        
        # Check for question patterns
        question_patterns = [
            r'what (?:is|are)',
            r'where (?:is|are)',
            r'when (?:is|was)',
            r'why (?:is|are)',
            r'how (?:to|do|can)',
            r'who (?:is|are)',
            r'which (?:is|are)',
            r'tell me about',
            r'explain',
            r'describe'
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def check_response_triggers(self, message, chat_id):
        """Check other response triggers"""
        response_types = []
        
        # 1. Direct bot mentions (100% response)
        bot_mentions = ["@namibiabot", "@namibia_bot", "namibia bot", "hey bot", "hello bot", "bot,", "bot!", "eva"]
        if any(mention in message for mention in bot_mentions):
            response_types.append(("direct_mention", 100))
        
        # 2. Greetings (80% response)
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "moro", "greetings", "hi there"]
        if any(greeting in message.lower().split() for greeting in greetings):
            response_types.append(("greeting", 80))
        
        # 3. Namibia mentions (70% response)
        if "namibia" in message.lower() or "namibian" in message.lower():
            response_types.append(("namibia_mention", 70))
        
        # 4. Specific topics (85% response)
        kb_topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", "desert", "dunes", "fish river", "cheetah", "elephant", "lion", "safari", "tour", "travel", "visit"]
        if any(topic in message.lower() for topic in kb_topics):
            response_types.append(("specific_topic", 85))
        
        # 5. If chat is quiet, start conversation (40% chance)
        if self.is_chat_quiet(chat_id, minutes=15):
            if random.random() < 0.4:
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
        """Generate enhanced intelligent response"""
        message_lower = message.lower().strip()
        
        # Clean message for search
        clean_message = re.sub(r'@[^\s]*', '', message_lower)
        clean_message = re.sub(r'(hey|hello)\s+(bot|namibia|eva)', '', clean_message).strip()
        
        # Log query to database
        if user_id and clean_message:
            db.log_query(user_id, clean_message)
        
        # Handle direct questions with knowledge base answers
        if response_type == "direct_question":
            result = self.knowledge_base.find_direct_answer(clean_message)
            
            if result and result['confidence'] > 65:
                # Format answer nicely
                response = self.format_answer(result, message)
                return response
            else:
                # If we don't have a good answer, respond helpfully
                return self.get_helpful_response(clean_message)
        
        # Handle other response types
        if response_type == "direct_mention":
            # Try to answer even if not a formal question
            result = self.knowledge_base.find_direct_answer(clean_message)
            if result and result['confidence'] > 60:
                response = self.format_answer(result, message)
                return response
        
        # Generate appropriate response based on type
        responses = self.get_response_templates(response_type, clean_message)
        
        if responses:
            response = random.choice(responses) if isinstance(responses, list) else responses
            
            # Add knowledge suggestion 30% of time
            if random.random() < 0.3 and response_type not in ["conversation_starter"]:
                suggestion = self.get_knowledge_suggestion(clean_message)
                if suggestion:
                    response += "\n\n" + suggestion
            
            return response
        
        return None
    
    def format_answer(self, result, original_question):
        """Format answer nicely"""
        response = f"🇳🇦 *{result['topic']}*\n\n"
        response += f"{result['answer']}\n\n"
        
        # Add emoji based on category
        category_emoji = {
            'Geography': '🗺️',
            'Tourism': '🏞️',
            'Culture': '👥',
            'History': '📜',
            'Wildlife': '🦓',
            'Practical': 'ℹ️',
            'Facts': '🌟'
        }
        
        emoji = category_emoji.get(result['category'], '💡')
        response += f"{emoji} *Category:* {result['category']}\n"
        
        # Add related information suggestion
        related = self.get_related_suggestion(result['category'], result['topic'])
        if related:
            response += f"\n💡 *Related:* {related}"
        
        # Add conversation continuation
        continuation = self.get_conversation_continuation(result['category'])
        if continuation:
            response += f"\n\n{continuation}"
        
        return response
    
    def get_helpful_response(self, query):
        """Get helpful response when we don't know the answer"""
        responses = [
            f"🤔 I'm not sure about \"{query}\". Try asking about Namibia's geography, culture, tourism, or wildlife!",
            f"🧐 I'm still learning about \"{query}\". You can ask me about Namibia's capital, Etosha National Park, Himba culture, or travel tips!",
            f"💡 I don't have information about \"{query}\" yet. Try /menu to explore what I do know about Namibia!",
            f"🇳🇦 That's an interesting question! While I learn more about \"{query}\", you can ask me about:\n• Namibia's location\n• Best time to visit\n• Etosha National Park\n• Himba people"
        ]
        
        return random.choice(responses)
    
    def get_response_templates(self, response_type, query):
        """Get response templates for different types"""
        templates = {
            "direct_mention": [
                "🇳🇦 Yes, I'm Eva! What would you like to know about Namibia?",
                "🦁 Hello! I'm your Namibia expert. Ask me anything!",
                "🏜️ Eva at your service! How can I help you learn about Namibia today?",
            ],
            "greeting": [
                "🇳🇦 Hello there! I'm Eva, your Namibia assistant. Ready to explore together?",
                "👋 Hi! I'm excited to chat about Namibia with you!",
                "🇳🇦 Moro! (That's hello in Oshiwambo) I'm Eva, your Namibia guide! 🇳🇦",
            ],
            "namibia_mention": [
                "🌟 You mentioned Namibia! That's my favorite topic! What would you like to know?",
                "🦁 Talking about Namibia? I have so much to share!",
                "🏜️ Namibia is truly amazing, isn't it? What aspect interests you most?",
            ],
            "specific_topic": [
                "🎯 Great topic! I have information about that. What specifically would you like to know?",
                "📚 I know about many Namibia topics. Ask me more!",
                "🔍 Good choice! For detailed information, try asking a specific question or use /menu",
            ],
            "conversation_starter": self.get_conversation_starter()
        }
        
        return templates.get(response_type, [])
    
    def get_knowledge_suggestion(self, query):
        """Get relevant knowledge suggestion"""
        suggestions = [
            "💡 *Did you know?* I can answer questions about Namibia's geography, culture, and wildlife!",
            "🔍 *Curious?* Ask me about Windhoek, Etosha, Sossusvlei, or Himba culture!",
            "📚 *Explore more:* Use /menu to see all Namibia topics I can help with!",
        ]
        return random.choice(suggestions)
    
    def get_related_suggestion(self, category, current_topic):
        """Get suggestion for related topics"""
        related_suggestions = {
            'Geography': 'Windhoek location, Namibia size, borders',
            'Tourism': 'Etosha National Park, Sossusvlei dunes, Swakopmund',
            'Culture': 'Himba people, Herero culture, languages',
            'History': 'Independence Day, German colonization',
            'Wildlife': 'Desert elephants, cheetahs, desert lions',
            'Practical': 'Visa requirements, currency, weather'
        }
        
        return related_suggestions.get(category, '')
    
    def get_conversation_continuation(self, category):
        """Get conversation continuation based on category"""
        continuations = {
            'Geography': "Want to know more about Namibia's geography?",
            'Tourism': "Planning a trip to Namibia? I can help with travel tips!",
            'Culture': "Interested in Namibia's diverse cultures? Ask me more!",
            'History': "Fascinated by Namibia's history? I have more stories!",
            'Wildlife': "Love wildlife? Namibia has amazing animals to discover!",
            'Practical': "Need practical travel advice? I'm here to help!"
        }
        
        continuation = continuations.get(category, "Want to know more about Namibia?")
        question_starter = random.choice(["What else", "Is there anything else", "Would you like to know"])
        
        return f"{question_starter} about {category.lower()}?"
    
    def get_conversation_starter(self):
        """Get intelligent conversation starter"""
        starters = [
            "💭 *Thought for the group:* What's your dream destination in Namibia?",
            "🦁 *Wildlife question:* Who would like to see desert-adapted elephants?",
            "🏜️ *Desert discussion:* What fascinates you most about the Namib Desert?",
            "👥 *Cultural curiosity:* What Namibia culture would you like to learn about?",
            "🗺️ *Travel talk:* What's the most surprising thing you've heard about Namibia?",
        ]
        return random.choice(starters)
    
    def generate_welcome_message(self, new_member_name):
        """Generate personalized welcome message"""
        welcomes = [
            f"👋 Welcome to the group, {new_member_name}! I'm Eva, an AI Assistant here to help with all things Namibia! 🇳🇦",
            f"🌟 Hello {new_member_name}! Great to have you here. I'm Eva - ask me anything about Namibia's wildlife, culture, or travel tips! 🦁",
            f"🇳🇦 Welcome {new_member_name}! I'm Eva, ready to explore Namibia together. Ask me about our beautiful country! 🏜️",
            f"🦓 Greetings {new_member_name}! I'm Eva, here to make your Namibia discussions more engaging. Feel free to ask questions! 🌅"
        ]
        return random.choice(welcomes)

# =========================================================
# BOT INSTANCES
# =========================================================
bot_instance = EnhancedNamibiaBot()

# =========================================================
# SIMPLIFIED MENU SYSTEM
# =========================================================
class SimpleMenu:
    """Simple menu system"""
    def __init__(self):
        self.categories = kb_db.get_categories()
    
    def create_main_menu(self):
        """Create simple main menu"""
        keyboard = []
        
        for category in self.categories:
            keyboard.append([
                InlineKeyboardButton(f"📌 {category}", callback_data=f"menu_{category.lower()}")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_category_topics(self, category):
        """Get topics for a category"""
        topics = kb_db.get_by_category(category)
        return topics[:5]  # Return first 5 topics

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Add user to database
    db.add_user(user.id, user.username or user.first_name)
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = f"""👋 *Hello everyone! I'm Eva, your Namibia AI Assistant!*

*I can help you learn about:*
• 🇳🇦 Namibia's geography and location
• 🦁 Wildlife and national parks
• 👥 Culture and people
• 🏞️ Tourism and travel tips
• 📜 History and heritage
• ℹ️ Practical information

*How to use me:*
1. Ask questions directly (like "Where is Namibia?")
2. Use /menu for organized topics
3. Tag me (@{context.bot.username}) for attention
4. I'll welcome new members automatically

*Try asking:*
• "What is the capital of Namibia?"
• "Tell me about Etosha National Park"
• "Best time to visit Namibia?"
• "Who are the Himba people?"

*Commands:*
/menu - Browse topics
/help - Get help
/about - Learn about me

Let's explore Namibia together! 🌟"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        # Private message - BE DIRECT AND ANSWER QUESTIONS
        response = f"""👋 *Hi {user.first_name}! I'm Eva, your Namibia assistant.*

I'm here to answer your questions about Namibia!

*Ask me anything about:*
• 🇳🇦 Geography: "Where is Namibia?", "What's the capital?"
• 🦁 Wildlife: "Tell me about Etosha", "Namibia's animals"
• 👥 Culture: "Who are the Himba people?", "Namibia cultures"
• 🏞️ Tourism: "Best time to visit", "Travel tips"
• 📜 History: "When did Namibia gain independence?"
• ℹ️ Practical: "Visa requirements", "Currency"

*Try asking me a question right now!* 
Example: "Where is Namibia?" or "What is Windhoek?"

I'm ready to help you learn about our beautiful country! 🇳🇦"""
        
        await update.message.reply_text(response, parse_mode="Markdown")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages - ANSWER QUESTIONS DIRECTLY"""
    if update.message.chat.type == 'private':
        user = update.effective_user
        message = update.message.text
        
        # Skip if it's a command
        if message and message.startswith('/'):
            return
        
        # Add user to database
        db.add_user(user.id, user.username or user.first_name)
        
        # Check if this is a question
        message_lower = message.lower().strip() if message else ""
        
        if message_lower:
            # Log the query
            db.log_query(user.id, message_lower)
            
            # Try to answer the question
            result = bot_instance.knowledge_base.find_direct_answer(message_lower)
            
            if result and result['confidence'] > 60:
                # We have a good answer
                response = bot_instance.format_answer(result, message)
                await update.message.reply_text(response, parse_mode="Markdown")
            else:
                # Don't know the answer or not a clear question
                if bot_instance.is_question(message_lower):
                    # It's a question but we don't have answer
                    response = f"🤔 I'm not sure about \"{message}\". Try asking about:\n• Where Namibia is located\n• Namibia's capital city\n• Best time to visit\n• Etosha National Park\n• Himba culture\n\nOr use /menu to browse topics!"
                else:
                    # Not a clear question
                    response = f"👋 Hi {user.first_name}! I'm Eva, your Namibia assistant.\n\nAsk me questions about Namibia! For example:\n• \"Where is Namibia?\"\n• \"What is the capital?\"\n• \"Tell me about Etosha\"\n• \"Best time to visit Namibia?\"\n\nI'm here to help you learn! 🇳🇦"
                
                await update.message.reply_text(response, parse_mode="Markdown")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages intelligently"""
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
    db.add_user(user_id, username or full_name)
    
    # Analyze message and decide response
    should_respond, response_type = bot_instance.analyze_message(message, user_id, chat_id)
    
    if should_respond and response_type:
        # Generate response
        response = bot_instance.generate_response(message, response_type, user_id)
        
        if response:
            # Add small delay for natural feel
            delay = random.uniform(0.3, 1.5)
            await asyncio.sleep(delay)
            
            try:
                await update.message.reply_text(
                    response,
                    parse_mode="Markdown",
                    reply_to_message_id=update.message.message_id
                )
            except Exception as e:
                print(f"Error sending response: {e}")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining"""
    if update.message.new_chat_members:
        for new_member in update.message.new_chat_members:
            if new_member.id == context.bot.id:
                continue
            
            # Add to database
            db.add_user(new_member.id, new_member.username or new_member.first_name)
            
            # Generate welcome
            welcome_msg = bot_instance.generate_welcome_message(new_member.first_name)
            
            # Send welcome
            await asyncio.sleep(1)
            await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🆘 *Eva - Namibia Assistant Help*

*I'm Eva, your AI assistant for Namibia!*

*How to interact with me:*
1. **Ask questions directly** - I'll answer if I know
2. Use **/menu** to browse topics
3. **Tag me** (@{}) in groups
4. I **welcome new members** automatically

*Example questions I can answer:*
• "Where is Namibia?"
• "What is the capital of Namibia?"
• "Tell me about Etosha National Park"
• "Best time to visit Namibia?"
• "Who are the Himba people?"
• "Namibia visa requirements?"

*Available commands:*
/start - Introduction
/menu - Browse topics
/help - This help message
/about - About me

*What I know about:*
• Geography & location
• Wildlife & national parks
• Culture & people
• Tourism & travel
• History & heritage
• Practical information

Ask me anything about Namibia! 🇳🇦""".format(context.bot.username)
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /about command"""
    about_text = """👋 *About Eva - Your Namibia AI Assistant*

*Who I am:*
I'm Eva, an AI assistant created to help people learn about Namibia. I'm powered by a knowledge base with information about Namibia's geography, culture, wildlife, tourism, and history.

*What I can do:*
• Answer questions about Namibia
• Provide detailed information on various topics
• Welcome new members to groups
• Help with travel planning
• Start conversations about Namibia

*My knowledge includes:*
• {} topics about Namibia
• {} different categories
• Information updated regularly

*My mission:*
To make learning about Namibia easy, engaging, and accessible to everyone!

*Created with:* Python, SQLite, and lots of Namibia love! 🇳🇦""".format(
        len(kb_db.get_all_topics()),
        len(kb_db.get_categories())
    )
    
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command"""
    menu = SimpleMenu()
    await update.message.reply_text(
        "📚 *Namibia Topics*\n\nSelect a category to explore:",
        parse_mode="Markdown",
        reply_markup=menu.create_main_menu()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    user_stats = db.get_user_stats(user_id)
    
    stats = f"""📊 *Your Eva Statistics*

*Your Activity:*
• Questions asked: {user_stats['query_count']}
• First seen: {user_stats['joined_date'][:10] if user_stats['joined_date'] != 'Unknown' else 'Recently'}
• Last question: {user_stats['last_query'][:19] if user_stats['last_query'] else 'Now'}

*Knowledge Base:*
• Topics available: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}

Keep asking questions about Namibia! 🦁"""
    
    await update.message.reply_text(stats, parse_mode="Markdown")

# =========================================================
# MAIN APPLICATION
# =========================================================
def main():
    """Main application entry point"""
    print("=" * 60)
    print("🇳🇦 EVA - INTELLIGENT NAMIBIA ASSISTANT")
    print("=" * 60)
    print(f"✅ Bot: Eva")
    print(f"✅ Database: {db.db_path}")
    print(f"✅ Knowledge: {len(kb_db.get_all_topics())} topics")
    print(f"✅ Categories: {len(kb_db.get_categories())}")
    print("=" * 60)
    print("✨ Enhanced Features:")
    print("   • Direct question answering")
    print("   • Intelligent query understanding")
    print("   • Context-aware responses")
    print("   • Personal name: Eva")
    print("=" * 60)
    print("🚀 Starting Eva...")
    
    # Create application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('about', about_command))
    app.add_handler(CommandHandler('stats', stats_command))
    
    # Message handlers
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_members
    ))
    
    # Group message handler
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS,
        handle_group_message
    ))
    
    # Private message handler - IMPORTANT: Must be after group handler
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        handle_private_message
    ))
    
    # Start bot
    print("🤖 Eva is running... Press Ctrl+C to stop")
    print("💡 Now you can ask questions like:")
    print("   • \"Where is Namibia?\"")
    print("   • \"What is the capital of Namibia?\"")
    print("   • \"Tell me about Etosha National Park\"")
    print("   • \"Best time to visit Namibia?\"")
    print("=" * 60)
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
