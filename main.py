#!/usr/bin/env python3
"""
Intelligent Namibia Chatbot with Grok AI Integration
KEEPS ALL ORIGINAL FEATURES - ONLY ADDS GROK FOR NATURAL CONVERSATIONS
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

# Import existing modules (UNCHANGED)
from database import Database
from knowledge_base import KnowledgeBase

# Import NEW Grok AI module
from grok_ai import GrokAI

# =========================================================
# CONFIGURATION (UNCHANGED)
# =========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set")
    exit(1)

ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set()
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = set(map(int, ADMIN_IDS_STR.split(',')))
    except:
        pass

# =========================================================
# DATABASE INITIALIZATION (UNCHANGED)
# =========================================================
print("📊 Initializing database...")
db = Database()
kb_db = KnowledgeBase()
grok_ai = GrokAI()  # NEW: Initialize Grok AI
print(f"✅ Database: {db.db_path}")
print(f"✅ Knowledge Base: {len(kb_db.get_all_topics())} topics")
print(f"✅ Grok AI: {'Enabled' if grok_ai.enabled else 'Disabled'}")

# =========================================================
# USER PROFILES (UNCHANGED)
# =========================================================
class UserProfile:
    """User profile management - UNCHANGED"""
    def __init__(self):
        print("👤 User profile system initialized")
    
    def get_user(self, user_id):
        return db.get_user_stats(user_id)
    
    def update_user_activity(self, user_id, username="", full_name=""):
        name_to_use = username or full_name or f"User_{user_id}"
        db.add_user(user_id, name_to_use)
    
    def increment_bot_interaction(self, user_id):
        db.log_query(user_id, "bot_interaction")
    
    def log_query(self, user_id, query):
        if query and query.strip():
            db.log_query(user_id, query.strip())

user_profiles = UserProfile()

# =========================================================
# INTELLIGENT KNOWLEDGE BASE (UNCHANGED)
# =========================================================
class IntelligentKnowledgeBase:
    """Enhanced knowledge base - UNCHANGED"""
    def __init__(self):
        print(f"🧠 Intelligent knowledge base initialized")
        self.setup_synonyms()
        self.all_topics = kb_db.get_all_topics()
        self.categories = kb_db.get_categories()
    
    def setup_synonyms(self):
        self.synonyms = {
            'namibia': ['namibian', 'namibias', 'namib'],
            'windhoek': ['capital', 'city', 'main city'],
            'etosha': ['etosha park', 'national park', 'wildlife park'],
            'sossusvlei': ['sand dunes', 'namib desert', 'dunes'],
            'swakopmund': ['coastal town', 'german town', 'beach town'],
            'fish river': ['canyon', 'fish river canyon'],
            'himba': ['red people', 'ochre people', 'tribal people'],
            'herero': ['victorian dress', 'traditional dress'],
            'visa': ['entry requirements', 'travel documents'],
            'currency': ['money', 'cash', 'nad'],
            'weather': ['climate', 'temperature', 'season'],
            'wildlife': ['animals', 'safari', 'game'],
            'history': ['past', 'historical', 'heritage'],
            'culture': ['people', 'traditions', 'customs'],
            'travel': ['tourism', 'visit', 'vacation', 'holiday'],
            'desert': ['arid', 'dry', 'sand', 'namib'],
            'elephant': ['elephants', 'pachyderm'],
            'lion': ['lions', 'big cat'],
            'cheetah': ['cheetahs', 'fastest animal']
        }
    
    def expand_query(self, query):
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
        if not query or not query.strip():
            return []
        
        clean_query = query.strip().lower()
        results = kb_db.search(clean_query, limit=10)
        enhanced_results = []
        seen_content = set()
        
        for result in results:
            if result['content'] in seen_content:
                continue
            
            topic_match = fuzz.partial_ratio(clean_query, result['topic'].lower())
            content_match = fuzz.partial_ratio(clean_query, result['content'].lower())
            
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
                    "score": best_score
                })
                seen_content.add(result['content'])
        
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
                                "score": 75
                            })
                            seen_content.add(result['content'])
        
        enhanced_results.sort(key=lambda x: x["score"], reverse=True)
        return enhanced_results[:5]
    
    def get_by_category(self, category):
        return kb_db.get_by_category(category)

# =========================================================
# ENHANCED CHATBOT ENGINE (WITH GROK INTEGRATION)
# =========================================================
class IntelligentNamibiaBot:
    """Enhanced bot engine with Grok AI - KEEPS ALL ORIGINAL FEATURES"""
    def __init__(self):
        self.knowledge_base = IntelligentKnowledgeBase()
        self.grok = grok_ai
        self.last_activity = {}
        self.welcomed_users = set()
        print("🤖 Enhanced Namibia Bot with Grok AI initialized")
    
    def get_greeting(self):
        """Time-appropriate greeting"""
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
        """UNCHANGED message analysis"""
        message_lower = message.lower().strip()
        self.last_activity[str(chat_id)] = datetime.now()
        return self.decide_response(message_lower, user_id, chat_id)
    
    def decide_response(self, message, user_id, chat_id):
        """UNCHANGED response decision logic"""
        response_types = []
        
        bot_mentions = ["@namibiabot", "@namibia_bot", "namibia bot", "hey bot", "hello bot", "eva"]
        if any(mention in message for mention in bot_mentions):
            response_types.append(("direct_mention", 100))
        
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "moro"]
        if any(greeting in message.lower().split() for greeting in greetings):
            response_types.append(("greeting", 70))
        
        question_words = ["what", "how", "where", "when", "why", "who", "which", "can you", "tell me", "explain"]
        if "?" in message or any(message.lower().startswith(word) for word in question_words):
            response_types.append(("question", 80))
        
        if "namibia" in message.lower() or "namibian" in message.lower():
            response_types.append(("namibia_mention", 60))
        
        kb_topics = ["etosha", "sossusvlei", "swakopmund", "windhoek", "himba", "herero", "desert", "dunes", "fish river", "cheetah", "elephant", "lion"]
        if any(topic in message.lower() for topic in kb_topics):
            response_types.append(("specific_topic", 75))
        
        travel_words = ["travel", "tour", "visit", "trip", "vacation", "holiday", "safari", "destination", "tourist"]
        if any(word in message.lower() for word in travel_words):
            response_types.append(("travel", 50))
        
        if self.is_chat_quiet(chat_id, minutes=20):
            if random.random() < 0.4:
                response_types.append(("conversation_starter", 40))
        
        if response_types:
            response_types.sort(key=lambda x: x[1], reverse=True)
            top_response = response_types[0]
            if top_response[1] >= 40 and random.random() < (top_response[1] / 100):
                return True, top_response[0]
        
        return False, None
    
    def is_chat_quiet(self, chat_id, minutes=20):
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_activity:
            return True
        return datetime.now() - self.last_activity[chat_id_str] > timedelta(minutes=minutes)
    
    async def generate_response(self, message, response_type, user_id=None):
        """ENHANCED with Grok AI - Falls back to original responses"""
        message_lower = message.lower().strip()
        clean_message = re.sub(r'@[^\s]*', '', message_lower)
        clean_message = re.sub(r'(hey|hello)\s+(bot|namibia)', '', clean_message).strip()
        
        if user_id and clean_message:
            user_profiles.log_query(user_id, clean_message)
        
        # STEP 1: Try Knowledge Base first (ORIGINAL BEHAVIOR)
        should_search = response_type in ["direct_mention", "question", "specific_topic", "namibia_mention", "travel"]
        kb_results = []
        
        if clean_message and should_search:
            kb_results = self.knowledge_base.intelligent_search(clean_message)
            
            if kb_results:
                best_result = kb_results[0]
                response = f"🤔 *Based on your question:*\n\n"
                response += f"**{best_result['item']['question'].title()}**\n"
                response += f"{best_result['item']['answer']}\n\n"
                
                related = self.get_related_info(best_result['item']['category'], best_result['item']['question'])
                if related:
                    response += f"💡 *Related information:*\n{related}\n\n"
                
                response += self.get_interactive_suggestion(best_result['item']['category'])
                return response
        
        # STEP 2: Try Grok AI for natural conversation (NEW FEATURE)
        if self.grok.enabled and clean_message:
            context = {'kb_results': [r['item'] for r in kb_results[:2]]} if kb_results else None
            grok_response = await self.grok.chat(clean_message, context)
            
            if grok_response:
                return grok_response
        
        # STEP 3: Fall back to original responses (UNCHANGED)
        responses = {
            "direct_mention": [
                "🇳🇦 Yes, I'm here! What would you like to know about Namibia?",
                "🦁 Hello! I'm Eva, your Namibia expert. Ask me anything!",
                "🏜️ Eva at your service! How can I help you today?",
                "🇳🇦 Ready to explore Namibia together!"
            ],
            "greeting": [
                f"🇳🇦 {self.get_greeting()}! Ready to explore Namibia?\n\n📱 Use /menu to browse topics!",
                f"👋 {self.get_greeting()}! I'm Eva. What would you like to know?\n\n💡 Try /menu!",
                f"🦁 {self.get_greeting()}! Ask me anything about Namibia!\n\n📚 Check /menu!",
                f"🏜️ {self.get_greeting()}! Let's discover Namibia!\n\n✨ Use /menu!"
            ],
            "question": [
                "💡 Interesting question! Try asking about specific topics like 'Etosha' or 'Himba culture'.\n\n📱 Or use /menu!",
                "🤔 I might have info on that. Try /menu for organized topics!",
                "🇳🇦 Great question! Use /menu → Categories for detailed info!",
                "🧐 For organized information, try /menu!"
            ],
            "namibia_mention": [
                "🌟 Namibia! My favorite topic! What would you like to know?\n\n📱 Use /menu!",
                "🦁 Talking about Namibia? I have so much to share!\n\n💡 Try /menu!",
                "🏜️ Namibia is incredible! How can I help?\n\n📚 Check /menu!",
                "🇳🇦 Namibia discussion! Use /menu for topics!"
            ],
            "specific_topic": [
                "🎯 Great topic! Ask me more or use /menu for details!",
                "📍 I know about that! What specifically?\n\n📱 Or use /menu!",
                "🦓 Excellent choice! Use /menu for comprehensive info!",
                "🏞️ Use /menu → Categories for detailed information!"
            ],
            "travel": [
                "🗺️ Planning a trip? Exciting! Use /menu for travel info!",
                "🦓 Namibia travel! I can help! Try /menu → Tourism!",
                "🌅 Travel to Namibia is unforgettable! Use /menu!",
                "🎒 Check /menu → Practical Info for travel tips!"
            ],
            "conversation_starter": await self.get_conversation_starter()
        }
        
        if response_type in responses:
            if isinstance(responses[response_type], list):
                response = random.choice(responses[response_type])
            else:
                response = responses[response_type]
            
            if random.random() < 0.4 and response_type not in ["conversation_starter"]:
                response += "\n\n" + self.get_knowledge_suggestion()
            
            return response
        
        return None
    
    def get_related_info(self, category, current_question):
        """UNCHANGED"""
        related_items = []
        category_items = self.knowledge_base.get_by_category(category)
        
        if category_items:
            for item in category_items:
                if isinstance(item, dict) and 'topic' in item:
                    if item['topic'].lower() != current_question.lower() and len(related_items) < 2:
                        related_items.append(f"• {item['topic'].title()}")
        
        return "\n".join(related_items) if related_items else ""
    
    def get_interactive_suggestion(self, category):
        """UNCHANGED"""
        suggestions = {
            "Tourism": "🌍 *Want more?* Try /menu → Tourism",
            "Culture": "👥 *Interested in people?* Try /menu → Culture",
            "History": "📜 *More history?* Try /menu → History",
            "Geography": "🗺️ *Geography?* Try /menu → Geography",
            "Wildlife": "🦁 *Wildlife lover?* Try /menu → Wildlife",
            "Practical": "ℹ️ *Practical info?* Try /menu → Practical",
            "Facts": "🚀 *More facts?* Try /menu → Facts"
        }
        return suggestions.get(category, "📱 *Explore more:* Use /menu")
    
    def get_knowledge_suggestion(self):
        """UNCHANGED"""
        suggestions = [
            "💡 Ask me specific questions about Namibia!",
            "🔍 Try asking about wildlife, culture, or travel!",
            "📚 I have 24+ Namibia topics. What interests you?",
            "🤔 What would you like to know about Namibia?"
        ]
        return random.choice(suggestions)
    
    async def get_conversation_starter(self):
        """ENHANCED with Grok AI"""
        # Try Grok first
        if self.grok.enabled:
            grok_starter = await self.grok.generate_conversation_starter()
            if grok_starter:
                return grok_starter
        
        # Fall back to original starters
        starters = [
            "💭 *Question:* What's your dream Namibia destination?\n\n📱 Use /menu to explore!",
            "🦁 *Wildlife talk:* Who has been on safari?\n\n🦓 Check /menu → Wildlife!",
            "🏜️ *Fun fact:* Namib Desert is 55-80 million years old!\n\n📚 Use /menu!",
            "👥 *Cultural question:* What interests you about Namibia's people?\n\n💡 Try /menu!",
            "🗺️ *Travel tip:* Best time is May-October!\n\n✈️ Use /menu → Tourism!",
            "🌅 *Amazing:* Sossusvlei has the world's highest dunes!\n\n📖 /menu for more!"
        ]
        return random.choice(starters)
    
    async def generate_welcome_message(self, new_member_name):
        """ENHANCED with Grok AI"""
        greeting = self.get_greeting()
        
        # Try Grok first
        if self.grok.enabled:
            grok_welcome = await self.grok.generate_welcome(new_member_name, greeting)
            if grok_welcome:
                return grok_welcome
        
        # Fall back to original welcomes
        welcomes = [
            f"👋 {greeting} {new_member_name}! I'm Eva Geises, your AI Namibia expert.\n\n💡 Ask me anything or use /menu! 🇳🇦",
            f"🌟 Welcome {new_member_name}! I'm Eva, here for all things Namibia!\n\n📱 Try /menu or ask questions! 🦁",
            f"🇳🇦 {greeting} {new_member_name}! Ready to explore Namibia?\n\n✨ Use /menu to start! 🏜️",
            f"🦓 {greeting} {new_member_name}! I'm Eva, your Namibia guide!\n\n📚 /menu or ask away! 🌅"
        ]
        return random.choice(welcomes)

# [REST OF THE CODE REMAINS EXACTLY THE SAME - Menu system, handlers, etc.]
# I'll include just the bot instance initialization to show it's connected

bot_instance = IntelligentNamibiaBot()

# ALL OTHER CODE (InteractiveMenu, handlers, main) STAYS EXACTLY AS IN YOUR ORIGINAL FILE
# Just replace bot_instance = IntelligentNamibiaBot() with the enhanced version above