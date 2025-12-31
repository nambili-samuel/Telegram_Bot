[file name]: main.py
[file content begin]
#!/usr/bin/env python3
"""
Intelligent Namibia Chatbot with Enhanced Database Integration
Main bot file that connects Telegram interface with database and knowledge base
"""

import os
import random
import re
import asyncio
import logging
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
# SETUP LOGGING
# =========================================================
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
    """Enhanced user profile management using Database"""
    def __init__(self):
        print("👤 Enhanced user profile system initialized")
    
    def get_user(self, user_id):
        """Get user stats from database"""
        return db.get_user_stats(user_id)
    
    def update_user_activity(self, user_id, username="", full_name=""):
        """Update user activity in database"""
        name_to_use = username or full_name or f"User_{user_id}"
        db.add_user(user_id, name_to_use)
    
    def increment_bot_interaction(self, user_id):
        """Log bot interaction"""
        db.log_query(user_id, "bot_interaction")
    
    def log_query(self, user_id, query):
        """Log user query to database"""
        if query and query.strip():
            db.log_query(user_id, query.strip())
    
    def get_user_behavior(self, user_id):
        """Get user behavior patterns"""
        stats = self.get_user(user_id)
        return {
            "active_days": (datetime.now() - datetime.strptime(stats.get('joined_date', datetime.now().isoformat()), "%Y-%m-%d %H:%M:%S")).days if stats.get('joined_date') else 0,
            "query_frequency": stats.get('query_count', 0),
            "engagement_level": "high" if stats.get('query_count', 0) > 10 else "medium" if stats.get('query_count', 0) > 3 else "low"
        }

user_profiles = UserProfile()

# =========================================================
# ENHANCED INTELLIGENT KNOWLEDGE BASE SYSTEM
# =========================================================
class EnhancedKnowledgeBase:
    """Enhanced knowledge base with advanced fuzzy matching and memory"""
    def __init__(self):
        print(f"🧠 Enhanced intelligent knowledge base initialized")
        self.setup_synonyms()
        self.setup_personality()
        self.all_topics = kb_db.get_all_topics()
        self.categories = kb_db.get_categories()
        self.conversation_history = {}
        self.user_interests = {}
    
    def setup_synonyms(self):
        """Setup comprehensive synonym dictionary"""
        self.synonyms = {
            'namibia': ['namibian', 'namibias', 'namib', 'republic of namibia'],
            'windhoek': ['capital', 'city', 'main city', 'capital city'],
            'etosha': ['etosha park', 'national park', 'wildlife park', 'game reserve', 'etosha pan'],
            'sossusvlei': ['sand dunes', 'namib desert', 'dunes', 'red dunes', 'dead vlei', 'deadvlei'],
            'swakopmund': ['coastal town', 'german town', 'beach town', 'coast', 'swakop'],
            'fish river': ['canyon', 'fish river canyon', 'hiking canyon', 'canyon hike'],
            'himba': ['red people', 'ochre people', 'tribal people', 'indigenous', 'himba tribe'],
            'herero': ['victorian dress', 'traditional dress', 'herero women', 'herero tribe'],
            'visa': ['entry requirements', 'travel documents', 'permit', 'visa requirements'],
            'currency': ['money', 'cash', 'nad', 'namibian dollar', 'rands', 'exchange'],
            'weather': ['climate', 'temperature', 'season', 'rain', 'sunny', 'dry'],
            'wildlife': ['animals', 'safari', 'game', 'fauna', 'creatures', 'mammals'],
            'history': ['past', 'historical', 'heritage', 'colonial', 'independence'],
            'culture': ['people', 'traditions', 'customs', 'ethnic', 'tribal', 'society'],
            'travel': ['tourism', 'visit', 'vacation', 'holiday', 'trip', 'journey'],
            'desert': ['arid', 'dry', 'sand', 'namib', 'kalahari'],
            'elephant': ['elephants', 'pachyderm', 'african elephant'],
            'lion': ['lions', 'big cat', 'predator', 'king of jungle'],
            'cheetah': ['cheetahs', 'fastest animal', 'acinonyx jubatus'],
            'eva': ['your name', 'who are you', 'what are you called'],
            'geises': ['last name', 'surname', 'family name']
        }
    
    def setup_personality(self):
        """Setup bot personality traits"""
        self.personality = {
            "name": "Eva Geises",
            "role": "Namibia Group Supervisor",
            "qualities": ["helpful", "knowledgeable", "friendly", "professional", "observant"],
            "responsibilities": [
                "Managing group discussions",
                "Providing accurate information about Namibia",
                "Welcoming new members",
                "Monitoring group activity",
                "Facilitating conversations"
            ]
        }
    
    def expand_query(self, query):
        """Expand query with synonyms and related terms"""
        query_lower = query.lower()
        expanded = [query_lower]
        
        # Add personal queries
        if any(term in query_lower for term in ['your name', 'who are you', 'what are you called']):
            expanded.extend(['eva geises', 'my name is eva', 'i am eva geises'])
        
        for word, synonyms in self.synonyms.items():
            if word in query_lower:
                for synonym in synonyms:
                    expanded_query = query_lower.replace(word, synonym)
                    if expanded_query not in expanded:
                        expanded.append(expanded_query)
        
        # Add partial matches
        words = query_lower.split()
        if len(words) > 1:
            for i in range(len(words)):
                partial = ' '.join(words[:i+1])
                if partial not in expanded:
                    expanded.append(partial)
        
        return expanded
    
    def intelligent_search(self, query, user_id=None, threshold=60):
        """Enhanced intelligent search with context awareness"""
        if not query or not query.strip():
            return []
        
        clean_query = query.strip().lower()
        
        # Check for personal questions
        personal_response = self.check_personal_questions(clean_query)
        if personal_response:
            return [{
                "item": {
                    "category": "Personal",
                    "question": "About Eva Geises",
                    "answer": personal_response,
                    "keywords": ["eva", "geises", "name", "supervisor"]
                },
                "score": 100,
                "matched_query": clean_query,
                "is_personal": True
            }]
        
        # Try direct search first
        results = kb_db.search(clean_query, limit=15)
        
        enhanced_results = []
        seen_content = set()
        
        for result in results:
            if result['content'] in seen_content:
                continue
            
            # Calculate multiple relevance scores
            topic_match = fuzz.partial_ratio(clean_query, result['topic'].lower())
            content_match = fuzz.partial_ratio(clean_query, result['content'].lower())
            
            # Enhanced keyword matching
            keywords = result.get('keywords', '').split(',') if result.get('keywords') else []
            keyword_score = 0
            if keywords:
                query_words = set(re.findall(r'\b\w+\b', clean_query.lower()))
                keyword_set = set(k.strip().lower() for k in keywords if k.strip())
                common = query_words & keyword_set
                if common:
                    keyword_score = (len(common) / max(len(query_words), len(keyword_set))) * 100
            
            # Context weighting (if user has interests)
            context_weight = 1.0
            if user_id and user_id in self.user_interests:
                user_interest = self.user_interests[user_id]
                if result['category'].lower() in user_interest:
                    context_weight = 1.3  # 30% boost for user interests
            
            best_score = max(topic_match, content_match, keyword_score) * context_weight
            
            if best_score > threshold:
                enhanced_results.append({
                    "item": {
                        "category": result['category'],
                        "question": result['topic'],
                        "answer": result['content'],
                        "keywords": keywords
                    },
                    "score": best_score,
                    "matched_query": clean_query,
                    "is_personal": False
                })
                seen_content.add(result['content'])
        
        # If no results, try synonym expansion
        if not enhanced_results or best_score < 80:
            expanded_queries = self.expand_query(clean_query)
            for expanded_query in expanded_queries:
                if expanded_query != clean_query:
                    synonym_results = kb_db.search(expanded_query, limit=8)
                    for result in synonym_results:
                        if result['content'] not in seen_content:
                            score_adjustment = 85 if expanded_query != clean_query else 75
                            enhanced_results.append({
                                "item": {
                                    "category": result['category'],
                                    "question": result['topic'],
                                    "answer": result['content'],
                                    "keywords": result.get('keywords', '').split(',') if result.get('keywords') else []
                                },
                                "score": score_adjustment,
                                "matched_query": expanded_query,
                                "is_personal": False
                            })
                            seen_content.add(result['content'])
        
        # Sort by score
        enhanced_results.sort(key=lambda x: x["score"], reverse=True)
        return enhanced_results[:7]  # Return top 7 results
    
    def check_personal_questions(self, query):
        """Handle personal questions about the bot"""
        personal_queries = {
            r'.*(your name|who are you|what are you called).*': 
                "🇳🇦 I'm **Eva Geises**, your Namibia Group Supervisor! I'm here to help manage, inform, and supervise this group with accurate information about Namibia.",
            
            r'.*(what can you do|your capabilities|abilities).*': 
                "🤖 *As Eva Geises, I can:*\n• Provide detailed information about Namibia\n• Manage group discussions\n• Welcome and supervise new members\n• Answer questions about wildlife, culture, travel\n• Track group activity and engagement\n• Facilitate conversations about Namibia",
            
            r'.*(eva geises|geises).*': 
                "👤 That's me! **Eva Geises** - your dedicated Namibia expert and group supervisor. I'm here to ensure everyone has accurate information and engaging discussions about our beautiful country.",
            
            r'.*(supervisor|manage|monitor).*': 
                "👁️ As group supervisor, I monitor discussions, provide accurate information, welcome new members, track engagement, and ensure positive conversations about Namibia.",
            
            r'.*(created you|who made you|developer).*': 
                "👨‍💻 I was developed as an intelligent Namibia assistant to help groups learn and discuss Namibia. My knowledge comes from verified sources and continuous updates.",
            
            r'.*(hello|hi|hey) eva.*': 
                "👋 Hello! I'm Eva Geises, pleased to assist you with all things Namibia! How can I help you today?"
        }
        
        for pattern, response in personal_queries.items():
            if re.match(pattern, query, re.IGNORECASE):
                return response
        
        return None
    
    def track_user_interest(self, user_id, category):
        """Track user interests for personalized responses"""
        if user_id not in self.user_interests:
            self.user_interests[user_id] = {}
        
        if category not in self.user_interests[user_id]:
            self.user_interests[user_id][category] = 1
        else:
            self.user_interests[user_id][category] += 1
    
    def get_personalized_suggestion(self, user_id):
        """Get personalized suggestion based on user interests"""
        if user_id in self.user_interests:
            interests = self.user_interests[user_id]
            if interests:
                top_interest = max(interests.items(), key=lambda x: x[1])[0]
                topics = kb_db.get_by_category(top_interest)
                if topics:
                    random_topic = random.choice(topics)
                    return f"💡 Based on your interest in *{top_interest}*, you might like: **{random_topic['topic']}**"
        return None
    
    def get_random_fact(self, user_id=None):
        """Get a random fact, potentially personalized"""
        if user_id and user_id in self.user_interests:
            interests = self.user_interests[user_id]
            if interests:
                # Try to get fact from user's top interest
                top_interest = max(interests.items(), key=lambda x: x[1])[0]
                topics = kb_db.get_by_category(top_interest)
                if topics:
                    random_topic = random.choice(topics)
                    return {
                        "question": random_topic['topic'],
                        "answer": random_topic['content'],
                        "category": random_topic.get('category', top_interest),
                        "personalized": True
                    }
        
        # Fallback to random fact
        if self.all_topics:
            random_topic = random.choice(self.all_topics)
            results = kb_db.search(random_topic, limit=1)
            if results:
                return {
                    "question": results[0]['topic'],
                    "answer": results[0]['content'],
                    "category": results[0]['category'],
                    "personalized": False
                }
        return None
    
    def get_by_category(self, category):
        """Get all topics in a category"""
        return kb_db.get_by_category(category)

# =========================================================
# ENHANCED INTELLIGENT CHATBOT ENGINE
# =========================================================
class EnhancedNamibiaBot:
    """Enhanced chatbot engine with supervision capabilities"""
    def __init__(self):
        self.knowledge_base = EnhancedKnowledgeBase()
        self.conversation_context = {}
        self.last_activity = {}
        self.welcomed_users = set()
        self.group_analytics = {}
        self.supervision_mode = True
        print("🤖 Enhanced Namibia Bot (Eva Geises) initialized")
    
    def analyze_message(self, message, user_id, chat_id):
        """Enhanced message analysis with supervision"""
        message_lower = message.lower().strip()
        
        # Update activity
        self.last_activity[str(chat_id)] = datetime.now()
        
        # Update group analytics
        self.update_group_analytics(chat_id, user_id, message)
        
        # Get response decision
        return self.decide_response(message_lower, user_id, chat_id)
    
    def update_group_analytics(self, chat_id, user_id, message):
        """Track group analytics for supervision"""
        chat_str = str(chat_id)
        if chat_str not in self.group_analytics:
            self.group_analytics[chat_str] = {
                "total_messages": 0,
                "active_users": set(),
                "last_message_time": datetime.now(),
                "message_topics": {}
            }
        
        analytics = self.group_analytics[chat_str]
        analytics["total_messages"] += 1
        analytics["active_users"].add(user_id)
        analytics["last_message_time"] = datetime.now()
        
        # Analyze message topics
        words = message.lower().split()
        for word in words:
            if len(word) > 3:  # Ignore short words
                if word in analytics["message_topics"]:
                    analytics["message_topics"][word] += 1
                else:
                    analytics["message_topics"][word] = 1
    
    def decide_response(self, message, user_id, chat_id):
        """Enhanced decision making with supervision"""
        response_types = []
        
        # Personal identification (100% response)
        if any(term in message for term in ["your name", "who are you", "eva", "geises", "supervisor"]):
            response_types.append(("personal_id", 100))
        
        # Direct mentions (95% response)
        bot_mentions = ["@namibiabot", "@namibia_bot", "namibia bot", "eva", "geises", "hey eva", "hello eva"]
        if any(mention in message for mention in bot_mentions):
            response_types.append(("direct_mention", 95))
        
        # Greetings (75% response)
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "moro", "greetings"]
        if any(greeting in message.lower().split() for greeting in greetings):
            response_types.append(("greeting", 75))
        
        # Questions (85% response)
        question_words = ["what", "how", "where", "when", "why", "who", "which", "can you", "tell me", "explain"]
        if "?" in message or any(message.lower().startswith(word) for word in question_words):
            response_types.append(("question", 85))
        
        # Namibia mentions (70% response)
        if "namibia" in message.lower() or "namibian" in message.lower():
            response_types.append(("namibia_mention", 70))
        
        # Knowledge base topics (80% response)
        kb_topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", "desert", "dunes", "fish river", "cheetah", "elephant", "lion", "visa", "currency", "weather"]
        if any(topic in message.lower() for topic in kb_topics):
            response_types.append(("specific_topic", 80))
        
        # Travel keywords (65% response)
        travel_words = ["travel", "tour", "visit", "trip", "vacation", "holiday", "safari", "destination", "tourist", "flight", "hotel"]
        if any(word in message.lower() for word in travel_words):
            response_types.append(("travel", 65))
        
        # Supervision triggers (90% response)
        supervision_triggers = ["help me", "i need", "can someone", "does anyone know", "looking for", "searching for"]
        if any(trigger in message.lower() for trigger in supervision_triggers):
            response_types.append(("supervision", 90))
        
        # If chat is quiet and we're in supervision mode
        if self.supervision_mode and self.is_chat_quiet(chat_id, minutes=30):
            if random.random() < 0.5:  # 50% chance if chat is quiet
                response_types.append(("conversation_starter", 60))
        
        # Sort by priority
        if response_types:
            response_types.sort(key=lambda x: x[1], reverse=True)
            top_response = response_types[0]
            
            # Calculate response probability with engagement factor
            user_behavior = user_profiles.get_user_behavior(user_id)
            engagement_factor = 1.2 if user_behavior["engagement_level"] == "high" else 1.0 if user_behavior["engagement_level"] == "medium" else 0.8
            
            adjusted_probability = (top_response[1] / 100) * engagement_factor
            
            if top_response[1] >= 40 and random.random() < adjusted_probability:
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
    
    def generate_response(self, message, response_type, user_id=None, chat_id=None):
        """Generate enhanced intelligent response"""
        message_lower = message.lower().strip()
        
        # Clean message for knowledge search
        clean_message = re.sub(r'@[^\s]*', '', message_lower)
        clean_message = re.sub(r'(hey|hello)\s+(bot|namibia|eva)', '', clean_message).strip()
        
        # Log the query to database
        if user_id and clean_message:
            user_profiles.log_query(user_id, clean_message)
        
        # Handle personal identification
        if response_type == "personal_id":
            return self.handle_personal_identification(message_lower)
        
        # Try knowledge base search for relevant response types
        should_search = response_type in ["direct_mention", "question", "specific_topic", "namibia_mention", "travel", "supervision"]
        
        if clean_message and should_search:
            results = self.knowledge_base.intelligent_search(clean_message, user_id)
            if results:
                best_result = results[0]
                
                # Track user interest
                if user_id and not best_result.get('is_personal', False):
                    self.knowledge_base.track_user_interest(user_id, best_result['item']['category'])
                
                # Format enhanced response
                response = self.format_knowledge_response(best_result, response_type)
                
                # Add personalized suggestion if available
                if user_id and random.random() < 0.3:
                    personalized = self.knowledge_base.get_personalized_suggestion(user_id)
                    if personalized:
                        response += f"\n\n{personalized}"
                
                return response
        
        # Generate appropriate response based on type
        responses = {
            "direct_mention": self.get_direct_mention_responses(),
            "greeting": self.get_greeting_responses(user_id),
            "question": self.get_question_responses(),
            "namibia_mention": self.get_namibia_responses(),
            "specific_topic": self.get_topic_responses(),
            "travel": self.get_travel_responses(),
            "supervision": self.get_supervision_responses(),
            "conversation_starter": self.get_conversation_starter(chat_id)
        }
        
        if response_type in responses:
            response = responses[response_type]
            if callable(response):
                response = response()
            
            # Add knowledge base suggestion
            if random.random() < 0.4 and response_type not in ["conversation_starter"]:
                response += "\n\n" + self.get_knowledge_suggestion(user_id)
            
            return response
        
        return None
    
    def handle_personal_identification(self, message):
        """Handle personal identification queries"""
        if "supervisor" in message or "manage" in message:
            return "👁️ *As Group Supervisor Eva Geises, I:*\n• Monitor discussions for accuracy\n• Welcome and guide new members\n• Provide verified information\n• Track engagement and activity\n• Facilitate positive conversations\n• Ensure everyone feels included"
        
        if "capabilities" in message or "what can you do" in message:
            return "🤖 *My capabilities as Eva Geises:*\n• Database-powered knowledge with 30+ topics\n• Full-text search with intelligent matching\n• User behavior analysis\n• Group activity supervision\n• Personalized responses\n• Conversation management\n• Query logging and analytics"
        
        return "🇳🇦 I'm **Eva Geises**, your Namibia Group Supervisor! I manage, inform, and supervise this group with accurate Namibia information. How can I assist you today?"
    
    def format_knowledge_response(self, result, response_type):
        """Format knowledge response with supervision context"""
        item = result['item']
        
        response = f"🔍 *{response_type.replace('_', ' ').title()} Response:*\n\n"
        
        if result.get('is_personal'):
            response = "👤 "  # Personal response indicator
        
        response += f"**{item['question'].title()}**\n"
        response += f"{item['answer']}\n\n"
        
        # Add supervision context
        if response_type == "supervision":
            response += "👁️ *Supervision Note:* I'm monitoring this topic to ensure accurate information.\n\n"
        
        # Add related info
        related = self.get_related_info(item['category'], item['question'])
        if related:
            response += f"💡 *Related Topics:*\n{related}\n\n"
        
        # Add interactive element with supervision
        response += self.get_supervised_interactive_suggestion(item['category'])
        
        return response
    
    def get_related_info(self, category, current_question):
        """Get related information from same category"""
        related_items = []
        category_items = self.knowledge_base.get_by_category(category)
        
        if category_items:
            for item in category_items:
                if isinstance(item, dict) and 'topic' in item:
                    if item['topic'].lower() != current_question.lower() and len(related_items) < 3:
                        related_items.append(f"• {item['topic'].title()}")
        
        if related_items:
            return "\n".join(related_items)
        return ""
    
    def get_supervised_interactive_suggestion(self, category):
        """Get interactive suggestion with supervision context"""
        suggestions = {
            "Tourism": "🌍 *Supervised Travel Tip:* Use /menu → Tourism for verified travel information.",
            "Culture": "👥 *Cultural Supervision:* I monitor cultural discussions for accuracy. Try /menu → Culture.",
            "History": "📜 *Historical Accuracy:* All historical info is verified. Try /menu → History.",
            "Geography": "🗺️ *Geographical Supervision:* Maps and locations are verified. Try /menu → Geography.",
            "Wildlife": "🦓 *Wildlife Monitoring:* Conservation info is updated regularly. Try /menu → Wildlife.",
            "Practical": "ℹ️ *Practical Supervision:* Travel advice is regularly reviewed. Try /menu → Practical.",
            "Facts": "🚀 *Fact Verification:* All facts are cross-checked. Try /menu → Quick Facts.",
            "Personal": "👤 *About Me:* I'm Eva Geises, your group supervisor. Ask me anything!"
        }
        
        return suggestions.get(category, "📱 *Supervised Information:* Use /menu for verified categories")
    
    def get_direct_mention_responses(self):
        responses = [
            "🇳🇦 Yes, Eva Geises here! How can I supervise and assist you today?",
            "🦁 Hello! I'm Eva, your Namibia supervisor. What would you like to know?",
            "🏜️ Eva Geises at your service! How can I help manage your Namibia discussion?",
            "🇳🇦 Supervisor Eva reporting! Ready to provide accurate Namibia information."
        ]
        return random.choice(responses)
    
    def get_greeting_responses(self, user_id=None):
        if user_id:
            user_stats = user_profiles.get_user(user_id)
            if user_stats['query_count'] > 5:
                return f"👋 Welcome back! As your supervisor Eva, I notice you're quite engaged. How can I assist today?"
        
        responses = [
            "🇳🇦 Hello there! I'm Eva Geises, your Namibia supervisor. Ready to assist!",
            "👋 Hi! I'm Eva, excited to supervise our Namibia discussions today!",
            "🇳🇦 Moro! (That's hello in Oshiwambo) I'm Eva Geises, your supervisor. 🇳🇦",
            "👋 Welcome! Supervisor Eva here to help with all Namibia topics!"
        ]
        return random.choice(responses)
    
    def get_question_responses(self):
        responses = [
            "💡 That's an excellent question! As supervisor Eva, let me provide accurate information...",
            "🤔 Interesting inquiry! I'll supervise the response to ensure accuracy.",
            "🇳🇦 Great question! Supervisor Eva checking the knowledge base...",
            "🧐 I'm supervising this topic to give you the most accurate answer."
        ]
        return random.choice(responses)
    
    def get_namibia_responses(self):
        responses = [
            "🌟 You mentioned Namibia! My specialty as supervisor Eva!",
            "🦁 Talking about Namibia? I supervise all discussions to ensure accuracy.",
            "🏜️ Namibia is amazing! As supervisor, I ensure all info is verified.",
            "🇳🇦 Ah, Namibia discussions! I'm here to supervise and inform."
        ]
        return random.choice(responses)
    
    def get_topic_responses(self):
        responses = [
            "🎯 Specific topic detected! Supervisor Eva verifying information...",
            "📚 I supervise this topic closely for accuracy. Let me check...",
            "🔍 Good topic choice! Supervisor Eva ensuring accurate details.",
            "🎯 That's a key Namibia topic! I'm supervising the response."
        ]
        return random.choice(responses)
    
    def get_travel_responses(self):
        responses = [
            "🗺️ Travel planning? Supervisor Eva here with verified information!",
            "🦓 Safari planning is exciting! I supervise travel advice for accuracy.",
            "🌅 Travel to Namibia will be unforgettable! Supervisor Eva ensuring good info.",
            "🎒 Need travel tips? I'm supervising all travel recommendations."
        ]
        return random.choice(responses)
    
    def get_supervision_responses(self):
        responses = [
            "👁️ *Supervision Activated:* I'm monitoring this request for accuracy.",
            "🔍 *Supervising Response:* Ensuring information is verified and helpful.",
            "📋 *Under Supervision:* This topic is monitored for accuracy.",
            "👤 *Eva Supervising:* I'm ensuring the information provided is correct."
        ]
        return random.choice(responses)
    
    def get_knowledge_suggestion(self, user_id=None):
        """Get knowledge suggestion with supervision context"""
        if user_id:
            personalized = self.knowledge_base.get_personalized_suggestion(user_id)
            if personalized:
                return f"💡 *Personalized Suggestion:*\n{personalized}"
        
        suggestions = [
            "💡 *Supervisor Suggestion:* Ask me specific questions for accurate responses.",
            "🔍 *Eva's Tip:* I supervise 30+ Namibia topics. What interests you?",
            "📚 *Knowledge Base:* As supervisor, I ensure all 30+ topics are accurate.",
            "🤔 *Supervised Question:* What Namibia topic would you like verified info on?"
        ]
        return random.choice(suggestions)
    
    def get_conversation_starter(self, chat_id=None):
        """Get intelligent conversation starter with supervision"""
        if chat_id and str(chat_id) in self.group_analytics:
            analytics = self.group_analytics[str(chat_id)]
            if analytics["message_topics"]:
                # Find most discussed topic
                top_topic = max(analytics["message_topics"].items(), key=lambda x: x[1])[0]
                starters = [
                    f"💭 *Supervisor Observation:* We've been discussing '{top_topic}' a lot. What specific aspect interests you?",
                    f"👁️ *Group Monitoring:* I notice '{top_topic}' is popular. Want to dive deeper?",
                    f"🔍 *Supervision Insight:* Based on our discussions, '{top_topic}' seems important. Any questions?",
                    f"📊 *Activity Analysis:* '{top_topic}' has been trending. Should we explore it more?"
                ]
                return random.choice(starters)
        
        starters = [
            "💭 *Supervisor's Thought:* What Namibia topic should we explore together?",
            "🦁 *Supervised Discussion:* Who has questions about Namibia's wildlife?",
            "🏜️ *Group Supervision:* What fascinates you about Namibia's landscapes?",
            "👥 *Cultural Supervision:* Which Namibia culture would you like to learn about?",
            "🗺️ *Travel Supervision:* What's surprising about Namibia travel?",
            "🌅 *Supervised Experience:* Has anyone experienced Namibia's unique attractions?"
        ]
        return random.choice(starters)
    
    def generate_welcome_message(self, new_member_name, chat_id=None):
        """Generate personalized welcome message with supervision"""
        welcomes = [
            f"👋 Welcome {new_member_name}! I'm **Eva Geises**, your Namibia Group Supervisor. I'm here to manage, inform, and supervise all Namibia discussions! 🇳🇦",
            f"🌟 Hello {new_member_name}! I'm Supervisor Eva Geises, here to ensure accurate Namibia information and engaging discussions! 🦁",
            f"🇳🇦 Welcome {new_member_name}! I'm Eva Geises, your group supervisor for all things Namibia. I monitor discussions for accuracy and helpfulness! 🏜️",
            f"🦓 Greetings {new_member_name}! I'm Supervisor Eva Geises, here to facilitate and supervise our Namibia conversations. Ask me anything! 🌅"
        ]
        
        welcome = random.choice(welcomes)
        
        # Add group context if available
        if chat_id and str(chat_id) in self.group_analytics:
            analytics = self.group_analytics[str(chat_id)]
            member_count = len(analytics.get("active_users", set()))
            welcome += f"\n\n👥 *Group Status:* {member_count} active members discussing Namibia"
        
        return welcome
    
    def get_group_report(self, chat_id):
        """Generate group supervision report"""
        chat_str = str(chat_id)
        if chat_str not in self.group_analytics:
            return None
        
        analytics = self.group_analytics[chat_str]
        
        report = f"📊 *Group Supervision Report*\n\n"
        report += f"• Total Messages: {analytics['total_messages']}\n"
        report += f"• Active Users: {len(analytics['active_users'])}\n"
        report += f"• Last Activity: {analytics['last_message_time'].strftime('%H:%M')}\n"
        
        # Top topics
        if analytics['message_topics']:
            sorted_topics = sorted(analytics['message_topics'].items(), key=lambda x: x[1], reverse=True)[:5]
            report += f"\n🔝 *Top Discussion Topics:*\n"
            for topic, count in sorted_topics:
                report += f"  {topic}: {count} mentions\n"
        
        report += f"\n👤 *Supervisor:* Eva Geises\n"
        report += f"📈 *Status:* Actively monitoring"
        
        return report

# =========================================================
# ENHANCED INTERACTIVE MENU SYSTEM
# =========================================================
class EnhancedInteractiveMenu:
    """Enhanced interactive menu with supervision"""
    def __init__(self):
        self.categories = kb_db.get_categories()
        print(f"📋 Enhanced menu system with {len(self.categories)} categories")
    
    def create_main_menu(self, user_id=None):
        """Create enhanced main menu with supervision"""
        keyboard = []
        
        # Map database categories to menu items with emojis
        category_emojis = {
            "Tourism": "🏞️",
            "History": "📜",
            "Culture": "👥",
            "Practical": "ℹ️",
            "Wildlife": "🦓",
            "Geography": "🗺️",
            "Facts": "🚀",
            "Personal": "👤"
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
        
        # Add About Eva button
        keyboard.append([
            InlineKeyboardButton("👤 About Eva", callback_data="menu_about_eva")
        ])
        
        # Add statistics and supervision buttons
        keyboard.append([
            InlineKeyboardButton("📊 Statistics", callback_data="menu_stats"),
            InlineKeyboardButton("👁️ Supervision", callback_data="menu_supervision")
        ])
        
        # Add help button
        keyboard.append([
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
            response += f"*Supervised by:* Eva Geises\n"
            response += f"*Verified Topics:* {len(topics)}\n\n"
            
            # Show first 3 topics as examples
            for i, topic in enumerate(topics[:3]):
                response += f"• {topic['topic']}\n"
            
            if len(topics) > 3:
                response += f"\n... and {len(topics) - 3} more supervised topics\n\n"
            
            response += "Select a topic for verified information:"
            
            return response
        else:
            return f"*{category}*\n\nNo supervised topics found in this category."

# =========================================================
# BOT INSTANCES
# =========================================================
bot_instance = EnhancedNamibiaBot()
menu_system = EnhancedInteractiveMenu()

# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Add user to database
    user_profiles.update_user_activity(user.id, user.username, user.first_name)
    
    if update.message.chat.type in ['group', 'supergroup']:
        welcome = f"""🇳🇦 *Intelligent NamibiaBot v3.0 - Eva Geises*

Hello everyone! I'm **Eva Geises**, your AI-powered Namibia Group Supervisor with enhanced database integration! 🧠👤

*Supervision Features:*
• 👁️ Group activity monitoring
• 📊 User behavior analysis
• 🔍 Enhanced full-text search (FTS5)
• 📚 {len(kb_db.get_all_topics())} supervised knowledge topics
• 🏷️ {len(kb_db.get_categories())} organized categories

*As Eva Geises, I can:*
1. Supervise group discussions for accuracy
2. Provide verified information about Namibia
3. Welcome and guide new members
4. Monitor engagement and activity
5. Facilitate positive conversations
6. Track user interests for personalized responses

*How to interact with me:*
• Ask questions about Namibia
• Use /menu for organized categories
• Tag me (@namibiabot) for direct supervision
• I'll welcome new members automatically
• Use /supervise for group reports

*Try asking:*
• "What is your name?" (I'm Eva Geises!)
• "Best time to visit Namibia?"
• "Tell me about Etosha National Park"
• "What makes you a supervisor?"

*Supervision Commands:*
/menu - Interactive knowledge system
/stats - View your statistics
/supervise - Group supervision report
/help - Help information
/start - Restart bot

🇳🇦 Let's explore Namibia together under my supervision! 🦁"""
        
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        # Private message response
        response = f"""🇳🇦 Hi {user.first_name}! I'm **Eva Geises**, an AI Group Supervisor.

I'm designed to supervise group conversations about Namibia.

*Enhanced Features:*
• Persistent storage with SQLite
• Supervised knowledge base with verification
• User activity tracking and analysis
• Group engagement monitoring
• Personalized response system

*To use my supervision:*
1. Add me to a Telegram group
2. Use /start in the group
3. I'll supervise discussions automatically

*Group Supervision Features:*
• Intelligent response system
• Interactive menus (/menu)
• Automatic member welcoming
• Conversation engagement
• Activity monitoring
• Accuracy verification

Add me to your group for supervised Namibia discussions!"""
        
        await update.message.reply_text(response, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🧠 *Namibia Knowledge System - Supervised by Eva Geises*\n\nSelect a category to explore:",
        parse_mode="Markdown",
        reply_markup=menu_system.create_main_menu(user_id)
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
    
    # Get user behavior
    user_behavior = user_profiles.get_user_behavior(user_id)
    
    if ADMIN_IDS and user_id in ADMIN_IDS:
        # Admin stats
        stats = f"""📊 *Supervision Statistics (Admin View)*

*User Statistics:*
• Total users: {len(all_users)}
• Active users: {sum(1 for user in all_users)}
• Your query count: {user_stats['query_count']}
• Your engagement: {user_behavior['engagement_level'].title()}

*Knowledge Supervision:*
• Supervised topics: {len(kb_db.get_all_topics())}
• Verified categories: {len(kb_db.get_categories())}
• Database: {db.db_path}

*Popular Supervised Queries:*
"""
        for i, query in enumerate(popular_queries, 1):
            stats += f"{i}. {query['query'][:30]}... ({query['count']}x)\n"
        
        stats += f"\n*Supervision Status:* Active ✅\n*Supervisor:* Eva Geises"
    else:
        # User stats
        stats = f"""📊 *Your NamibiaBot Statistics*

*Supervised by:* Eva Geises

*Your Activity:*
• Queries made: {user_stats['query_count']}
• Engagement level: {user_behavior['engagement_level'].title()}
• Active days: {user_behavior['active_days']}
• Joined: {user_stats['joined_date'][:10] if user_stats['joined_date'] != 'Unknown' else 'Recently'}
• Last active: {user_stats['last_query'][:19] if user_stats['last_query'] else 'Now'}

*Supervised Knowledge:*
• Topics: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}

Keep exploring Namibia under my supervision! 🦁"""
    
    await update.message.reply_text(stats, parse_mode="Markdown")

async def supervise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /supervise command for group reports"""
    chat_id = update.effective_chat.id
    
    if update.message.chat.type in ['group', 'supergroup']:
        report = bot_instance.get_group_report(chat_id)
        
        if report:
            await update.message.reply_text(report, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "👁️ *Supervision Report*\n\nNo group activity data available yet.\n\n"
                "Start discussing Namibia and I'll begin supervision monitoring!",
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            "👤 This command is for group supervision only.\n\n"
            "Add me to a group to use supervision features!",
            parse_mode="Markdown"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🆘 *NamibiaBot Help - Supervised by Eva Geises*

*Enhanced Supervision Features:*
• SQLite database with FTS5 search
• Group activity monitoring
• User behavior analysis
• Verified information system
• Personalized response engine
• Conversation management

*How to interact with Supervisor Eva:*
1. Ask questions about Namibia
2. Use /menu for organized categories
3. Tag me (@namibiabot) for direct answers
4. I'll welcome and supervise new members
5. Use /supervise for group reports

*Available Commands:*
/start - Start or restart the bot
/menu - Interactive knowledge system
/stats - View your statistics
/supervise - Group supervision report
/help - This help message
/add_knowledge - Add new knowledge (admin)

*Supervised Topics:*
• Wildlife & Nature 🦓 (verified)
• Tourism & Travel 🏞️ (verified)
• Culture & People 👥 (verified)
• History & Heritage 📜 (verified)
• Practical Information ℹ️ (verified)
• Geography & Facts 🗺️ (verified)

*About Supervisor:*
I'm Eva Geises, ensuring all information is accurate and helpful!"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_knowledge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to add knowledge"""
    user_id = update.effective_user.id
    
    if ADMIN_IDS and user_id in ADMIN_IDS:
        if not context.args:
            await update.message.reply_text(
                "👤 *Supervisor Knowledge Addition*\n\n"
                "Usage: /add_knowledge <topic> | <content> | [category] | [keywords]\n\n"
                "Example: /add_knowledge Windhoek | Capital city of Namibia | Geography | capital, city\n\n"
                "All additions are supervised by Eva Geises for accuracy.",
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
            f"✅ *Knowledge Added Under Supervision*\n\n"
            f"**Supervisor:** Eva Geises\n"
            f"**Topic:** {topic}\n"
            f"**Category:** {category}\n"
            f"**Keywords:** {keywords}\n\n"
            f"*Content preview:*\n{content[:200]}...\n\n"
            f"*Status:* Added to verified knowledge base",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👤 This command is for administrators only.\n"
            "Supervisor Eva Geises manages knowledge verification.",
            parse_mode="Markdown"
        )

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
        logger.info(f"🤖 Response triggered: {response_type} for user {user_id}: {message[:50]}...")
        
        # Generate intelligent response
        response = bot_instance.generate_response(message, response_type, user_id, chat_id)
        
        if response:
            # Natural delay for realistic interaction
            delay = random.uniform(0.5, 1.5)
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
                
                logger.info(f"✅ Sent response: {response_type}")
            except Exception as e:
                logger.error(f"❌ Error sending response: {e}")

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
            
            # Generate welcome message with supervision
            welcome_msg = bot_instance.generate_welcome_message(new_member.first_name, update.effective_chat.id)
            
            # Add to welcomed users set
            bot_instance.welcomed_users.add(new_member.id)
            
            # Send welcome message with delay
            await asyncio.sleep(1)
            await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages"""
    if update.message.chat.type == 'private':
        user = update.effective_user
        
        response = f"""🇳🇦 *Hi {user.first_name}! I'm Eva Geises*

I'm an AI Group Supervisor designed for group conversations about Namibia.

*Current Supervision Features:*
• Database-powered knowledge verification
• Full-text search with intelligent matching
• User activity tracking and analysis
• Group engagement monitoring
• Interactive menu system
• Personalized response engine

*To use my supervision:*
1. Add me to your Telegram group
2. Type /start in the group
3. I'll begin supervising discussions automatically

*In groups, I supervise:*
• Answering questions intelligently
• Providing verified information
• Welcoming and guiding new members
• Monitoring conversation quality
• Tracking user engagement
• Ensuring accurate information

Add me to a group and I'll supervise your Namibia discussions! 🦁"""
        
        await update.message.reply_text(response, parse_mode="Markdown")

# =========================================================
# ENHANCED BUTTON HANDLER
# =========================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button interactions"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_back":
        # Return to main menu
        await query.edit_message_text(
            "🧠 *Namibia Knowledge System - Supervised by Eva Geises*\n\nSelect a category to explore:",
            parse_mode="Markdown",
            reply_markup=menu_system.create_main_menu(query.from_user.id)
        )
    
    elif data == "menu_home":
        # Return to start
        await query.edit_message_text(
            "🏠 *Main Menu*\n\nUse /menu to explore categories or ask me anything about Namibia!\n\n"
            "*Supervisor:* Eva Geises",
            parse_mode="Markdown"
        )
    
    elif data == "menu_stats":
        # Show statistics
        user_id = query.from_user.id
        user_stats = db.get_user_stats(user_id)
        user_behavior = user_profiles.get_user_behavior(user_id)
        
        stats_text = f"""📊 *Your Statistics*

*Supervised by:* Eva Geises

*Your Activity:*
• Queries: {user_stats['query_count']}
• Engagement: {user_behavior['engagement_level'].title()}
• Active days: {user_behavior['active_days']}
• Last active: Now

*Supervised Knowledge:*
• Topics: {len(kb_db.get_all_topics())}
• Categories: {len(kb_db.get_categories())}"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
        
        await query.edit_message_text(
            stats_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "menu_supervision":
        # Show supervision info
        supervision_text = """👁️ *Group Supervision by Eva Geises*

*What I supervise:*
• Discussion accuracy and quality
• User engagement and activity
• Information verification
• New member integration
• Conversation flow

*Supervision Features:*
• Activity monitoring
• Behavior analysis
• Topic trending
• Engagement tracking
• Accuracy verification

*Commands:*
/supervise - Group activity report
/menu - Knowledge exploration
/stats - Your personal stats

I ensure productive Namibia discussions!"""
        
        keyboard = [
            [InlineKeyboardButton("📊 Group Report", callback_data="group_report")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]
        ]
        
        await query.edit_message_text(
            supervision_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "group_report":
        # Generate group report
        chat_id = query.message.chat.id
        report = bot_instance.get_group_report(chat_id)
        
        if report:
            response = report
        else:
            response = "👁️ *Supervision Report*\n\nNo group activity data available yet."
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Supervision", callback_data="menu_supervision")]]
        
        await query.edit_message_text(
            response,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "menu_about_eva":
        # Show about Eva
        about_text = """👤 *About Eva Geises*

*Who I am:*
I'm **Eva Geises**, your Namibia Group Supervisor AI.

*My Role:*
• Supervising group discussions
• Providing accurate Namibia information
• Managing conversation quality
• Welcoming and guiding members
• Monitoring engagement

*My Capabilities:*
• Database-powered knowledge (30+ topics)
• Intelligent response system
• User behavior analysis
• Full-text search with FTS5
• Personalized suggestions
• Activity monitoring

*My Goal:*
Ensuring productive, accurate, and engaging Namibia discussions for everyone!

Ask me anything about Namibia! 🇳🇦"""
        
        keyboard = [
            [InlineKeyboardButton("🦁 Ask About Namibia", callback_data="menu_back")],
            [InlineKeyboardButton("🏠 Home", callback_data="menu_home")]
        ]
        
        await query.edit_message_text(
            about_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "menu_help":
        # Show help
        help_text = """❓ *Quick Help - Supervised by Eva Geises*

*How to use:*
• Ask questions about Namibia
• Use buttons to explore categories
• Tag me for direct answers
• I supervise discussions automatically

*Commands:*
/menu - Show this menu
/stats - Your statistics
/supervise - Group report
/help - Detailed help

*Supervision:*
I monitor all discussions for accuracy and quality.

Select a category to explore supervised topics!"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
        
        await query.edit_message_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("menu_"):
        # Handle category menu
        category_name = data.replace("menu_", "").capitalize()
        
        # Handle special categories
        if category_name.lower() == "about_eva":
            await button_handler(update, context)
            return
        
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
                
                response += f"*Category:* {category}\n"
                response += f"*Supervised by:* Eva Geises"
                
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
            "Supervised topic information not found. Please try another topic.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]])
        )

# =========================================================
# MAIN APPLICATION WITH TIMEOUT FIX
# =========================================================
def main():
    """Main application entry point with timeout handling"""
    print("=" * 60)
    print("🇳🇦 ENHANCED INTELLIGENT NAMIBIA CHATBOT - EVA GEISES")
    print("=" * 60)
    print(f"✅ Bot Token: {'Set' if TELEGRAM_BOT_TOKEN else 'Not Set'}")
    print(f"✅ Database: {db.db_path}")
    print(f"✅ Knowledge Base: {len(kb_db.get_all_topics())} supervised topics")
    print(f"✅ Categories: {len(kb_db.get_categories())}")
    print(f"✅ Admin IDs: {len(ADMIN_IDS)} configured")
    print(f"✅ Supervisor: Eva Geises initialized")
    print("=" * 60)
    print("✨ Enhanced Features Enabled:")
    print("   • SQLite database with FTS5 search")
    print("   • Intelligent response system with supervision")
    print("   • Enhanced interactive menu system")
    print("   • User activity tracking and analysis")
    print("   • Group supervision and monitoring")
    print("   • Personalized response engine")
    print("   • Conversation management")
    print("=" * 60)
    print("🚀 Starting bot with timeout protection...")
    
    # Create application with timeout protection
    try:
        app = ApplicationBuilder() \
            .token(TELEGRAM_BOT_TOKEN) \
            .read_timeout(30) \
            .write_timeout(30) \
            .connect_timeout(30) \
            .pool_timeout(30) \
            .build()
    except Exception as e:
        print(f"❌ Failed to create application: {e}")
        return
    
    # Add command handlers (highest priority)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('supervise', supervise_command))
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
    
    # Start bot with error handling
    print("🤖 Bot is running... Press Ctrl+C to stop")
    print("💡 Test commands in a group:")
    print("   • /start - Initialize supervisor Eva")
    print("   • /menu - Show interactive menu")
    print("   • 'What is your name?' (I'm Eva Geises!)")
    print("   • 'Tell me about Etosha National Park'")
    print("   • /supervise - Get group report")
    print("=" * 60)
    
    try:
        # Run with timeout protection
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            poll_interval=0.5,
            timeout=20
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        import traceback
        traceback.print_exc()
        
        # Attempt graceful restart
        print("\n🔄 Attempting to restart bot...")
        try:
            app.stop()
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False
            )
        except:
            print("❌ Failed to restart bot")

if __name__ == "__main__":
    # Add error handling for imports
    try:
        main()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install required packages: pip install python-telegram-bot rapidfuzz")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
[file content end]
