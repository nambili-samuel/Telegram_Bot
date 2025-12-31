#!/usr/bin/env python3
"""
Eva - Namibia Chatbot
Simple, reliable chatbot that answers questions about Namibia
"""

import os
import random
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Import Database and KnowledgeBase
from database import Database
from knowledge_base import KnowledgeBase

# =========================================================
# CONFIGURATION
# =========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set")
    exit(1)

# =========================================================
# INITIALIZE DATABASE
# =========================================================
print("📊 Initializing database...")
db = Database()
kb = KnowledgeBase()
print(f"✅ Database ready: {db.db_path}")
print(f"✅ Knowledge base: {len(kb.get_all_topics())} topics")

# =========================================================
# SIMPLE QUESTION ANSWERING
# =========================================================
class SimpleNamibiaBot:
    def __init__(self):
        self.last_activity = {}
        print("🤖 Simple Namibia Bot initialized")
    
    def is_question_about_namibia(self, message):
        """Check if message is asking about Namibia"""
        message_lower = message.lower().strip()
        
        # Check for Namibia mentions
        if 'namibia' not in message_lower and 'namibian' not in message_lower:
            return False
        
        # Check for question patterns
        question_patterns = [
            r'where (?:is|are).*namibia',
            r'what (?:is|are).*namibia',
            r'when (?:is|was).*namibia',
            r'why (?:is|are).*namibia',
            r'how (?:to|do|can).*namibia',
            r'who (?:is|are).*namibia',
            r'tell me about.*namibia',
            r'explain.*namibia',
            r'describe.*namibia',
            r'capital of namibia',
            r'namibia capital',
            r'size of namibia',
            r'namibia size',
            r'population of namibia',
            r'namibia population',
            r'currency of namibia',
            r'namibia currency',
            r'language in namibia',
            r'namibia language',
            r'weather in namibia',
            r'namibia weather',
            r'visit namibia',
            r'travel to namibia',
            r'namibia tourism',
            r'etosha',
            r'sossusvlei',
            r'swakopmund',
            r'windhoek',
            r'himba',
            r'herero',
            r'fish river',
            r'namib desert',
            r'cheetah',
            r'elephant',
            r'lion',
            r'safari',
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, message_lower):
                return True
        
        # Check for question mark
        if '?' in message_lower:
            namibia_keywords = ['namibia', 'namibian', 'windhoek', 'etosha', 'sossusvlei', 'swakopmund', 'himba', 'herero']
            if any(keyword in message_lower for keyword in namibia_keywords):
                return True
        
        return False
    
    def find_answer(self, question):
        """Find answer in knowledge base"""
        # Clean the question
        clean_question = question.lower().strip()
        
        # Remove common prefixes
        prefixes = ['what is', 'what are', 'where is', 'where are', 'when is', 'when are', 
                   'why is', 'why are', 'how is', 'how are', 'who is', 'who are',
                   'tell me about', 'explain', 'describe', 'can you tell me']
        
        for prefix in prefixes:
            if clean_question.startswith(prefix):
                clean_question = clean_question[len(prefix):].strip()
        
        # Remove question mark
        clean_question = clean_question.rstrip('?')
        
        # Search in knowledge base
        results = kb.search(clean_question, limit=3)
        
        if results:
            # Return the best match
            return results[0]
        
        # Try searching for specific topics
        common_questions = {
            'where is namibia': 'Where is Namibia',
            'capital of namibia': 'Capital of Namibia',
            'what is the capital of namibia': 'Capital of Namibia',
            'size of namibia': 'Size of Namibia',
            'population of namibia': 'Population Density',
            'currency of namibia': 'Currency',
            'weather in namibia': 'Weather',
            'best time to visit namibia': 'Best time to visit Namibia',
            'etosha national park': 'Etosha National Park',
            'sossusvlei': 'Sossusvlei',
            'swakopmund': 'Swakopmund',
            'himba people': 'Himba People',
            'herero people': 'Herero People',
            'languages in namibia': 'Languages in Namibia',
            'visa requirements for namibia': 'Visa Requirements',
            'namib desert': 'Namib Desert',
            'fish river canyon': 'Fish River Canyon',
            'desert elephants': 'Desert Adapted Elephants',
            'desert lions': 'Namib Desert Lions',
            'cheetahs in namibia': 'Cheetahs',
            'independence day of namibia': 'Independence Day',
            'german colonization of namibia': 'German Colonization',
            'oldest desert': 'Oldest Desert',
            'dark sky reserve': 'Dark Sky Reserve',
            'conservation in namibia': 'Conservation',
        }
        
        for query, topic in common_questions.items():
            if query in clean_question:
                # Search for this specific topic
                topic_results = kb.search(topic, limit=1)
                if topic_results:
                    return topic_results[0]
        
        return None
    
    def format_answer(self, result, original_question):
        """Format the answer nicely"""
        response = f"🇳🇦 *{result['topic']}*\n\n"
        response += f"{result['content']}\n\n"
        
        # Add category
        response += f"📁 *Category:* {result['category']}\n"
        
        # Add keywords if available
        if result.get('keywords'):
            response += f"🏷️ *Tags:* {result['keywords']}\n"
        
        # Add suggestion for more info
        response += f"\n💡 *Want to know more?* Ask me another question or use /menu"
        
        return response

# =========================================================
# HANDLERS
# =========================================================
bot = SimpleNamibiaBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Add user to database
    db.add_user(user.id, user.username or user.first_name)
    
    welcome = f"""👋 *Hello! I'm Eva, your Namibia assistant!*

I can answer your questions about Namibia.

*Try asking me:*
• "Where is Namibia?"
• "What is the capital of Namibia?"
• "Tell me about Etosha National Park"
• "Best time to visit Namibia?"
• "Who are the Himba people?"

*I know about:*
• Geography & location
• Wildlife & national parks  
• Culture & people
• Tourism & travel tips
• History & heritage
• Practical information

*Commands:*
/help - Show help
/menu - Browse topics
/about - About me

Ask me anything about Namibia! 🇳🇦"""
    
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🆘 *How to use Eva*

*To ask questions:*
Just type your question! For example:
• "Where is Namibia?"
• "What is Windhoek?"
• "Tell me about Etosha"

*Commands:*
/start - Start conversation
/menu - Browse topics by category
/help - This help message
/about - Learn about me

*What I can answer:*
• Where questions (location)
• What questions (facts, information)
• When questions (dates, times)
• Why questions (reasons)
• How questions (methods, processes)
• Tell me about... (explanations)

*Examples of good questions:*
• "Where is Namibia located?"
• "What is the capital city?"
• "When is the best time to visit?"
• "Why visit Namibia?"
• "How do I get a visa?"
• "Tell me about Himba culture"

I'm here to help you learn about beautiful Namibia! 🦁"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /about command"""
    about_text = f"""👋 *About Eva - Namibia Assistant*

*Who I am:*
I'm Eva, an AI assistant created to help people learn about Namibia. I'm powered by a knowledge base with information about Namibia's geography, culture, wildlife, tourism, and history.

*What I know:*
• {len(kb.get_all_topics())} topics about Namibia
• {len(kb.get_categories())} categories
• Information from reliable sources

*My purpose:*
To make learning about Namibia easy and accessible to everyone!

*How I work:*
1. You ask a question about Namibia
2. I search my knowledge base
3. I provide the most relevant answer
4. I learn from our conversation

*Features:*
• Answers questions in natural language
• Provides detailed information
• Suggests related topics
• Tracks conversation context

Ask me anything about Namibia! I'm excited to share with you. 🌟"""
    
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command"""
    categories = kb.get_categories()
    
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(f"📌 {category}", callback_data=f"cat_{category}")])
    
    keyboard.append([InlineKeyboardButton("❓ How to ask questions", callback_data="help_questions")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 *Namibia Knowledge Menu*\n\nSelect a category to explore:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ALL messages - both group and private"""
    # Skip if no text
    if not update.message or not update.message.text:
        return
    
    # Skip bot's own messages
    if update.message.from_user.id == context.bot.id:
        return
    
    user = update.effective_user
    message = update.message.text
    
    print(f"📩 Received message from {user.first_name}: {message[:50]}...")
    
    # Add user to database
    db.add_user(user.id, user.username or user.first_name)
    
    # Check if it's a command
    if message.startswith('/'):
        # Let command handlers handle it
        return
    
    # Check if this is a question about Namibia
    is_namibia_question = bot.is_question_about_namibia(message)
    
    if is_namibia_question:
        print(f"🔍 Detected Namibia question: {message[:50]}...")
        
        # Log the query
        db.log_query(user.id, message)
        
        # Find answer
        answer = bot.find_answer(message)
        
        if answer:
            print(f"✅ Found answer for: {message[:50]}...")
            # Format and send answer
            response = bot.format_answer(answer, message)
            await update.message.reply_text(response, parse_mode="Markdown")
        else:
            print(f"❌ No answer found for: {message[:50]}...")
            # Suggest similar questions
            response = f"🤔 *I'm not sure about:* \"{message}\"\n\n"
            response += "*Try asking about:*\n"
            response += "• Where Namibia is located\n"
            response += "• Namibia's capital city\n"
            response += "• Best time to visit\n"
            response += "• Etosha National Park\n"
            response += "• Himba culture\n\n"
            response += "Or use /menu to browse topics!"
            await update.message.reply_text(response, parse_mode="Markdown")
    
    elif update.message.chat.type == 'private':
        # In private chat, respond even if not clearly about Namibia
        print(f"💬 Private message: {message[:50]}...")
        
        # Check for greetings
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        if any(message.lower().startswith(greet) for greet in greetings):
            response = f"👋 Hello {user.first_name}! I'm Eva, your Namibia assistant.\n\nAsk me anything about Namibia! For example:\n• \"Where is Namibia?\"\n• \"What is the capital?\"\n• \"Tell me about Etosha\"\n\nI'm here to help! 🇳🇦"
            await update.message.reply_text(response, parse_mode="Markdown")
        
        # Check if it's a question (has ?)
        elif '?' in message.lower():
            response = f"🤔 *I'm Eva, your Namibia assistant!*\n\n"
            response += f"It looks like you asked: \"{message}\"\n\n"
            response += "*I specialize in questions about Namibia.* Try asking:\n"
            response += "• \"Where is Namibia?\"\n"
            response += "• \"What is Windhoek?\"\n"
            response += "• \"Best time to visit Namibia?\"\n"
            response += "• \"Tell me about Himba culture\"\n\n"
            response += "Or use /menu to see all topics I know!"
            await update.message.reply_text(response, parse_mode="Markdown")
        
        else:
            # Generic private response
            response = f"👋 Hi {user.first_name}! I'm Eva.\n\n"
            response += "I'm an AI assistant that helps people learn about Namibia.\n\n"
            response += "*To get started, ask me a question like:*\n"
            response += "• \"Where is Namibia?\"\n"
            response += "• \"What is the capital of Namibia?\"\n"
            response += "• \"Tell me about Etosha National Park\"\n\n"
            response += "Or use /help for more information!"
            await update.message.reply_text(response, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("cat_"):
        category = data[4:]  # Remove "cat_" prefix
        topics = kb.get_by_category(category)
        
        if topics:
            response = f"📚 *{category}*\n\n"
            for i, topic in enumerate(topics[:10], 1):  # Show first 10
                response += f"{i}. {topic['topic']}\n"
            
            if len(topics) > 10:
                response += f"\n... and {len(topics) - 10} more topics\n"
            
            response += "\n💡 *Ask me about any of these topics!* Example: \"Tell me about [topic name]\""
            
            # Add back button
            keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                response,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    
    elif data == "help_questions":
        response = """❓ *How to ask questions*

*Good question formats:*
1. **Where** questions:
   • "Where is Namibia?"
   • "Where is Windhoek located?"

2. **What** questions:
   • "What is the capital of Namibia?"
   • "What currency does Namibia use?"

3. **When** questions:
   • "When is the best time to visit?"
   • "When did Namibia gain independence?"

4. **Tell me about** questions:
   • "Tell me about Etosha National Park"
   • "Tell me about Himba culture"

5. **How** questions:
   • "How do I get a visa for Namibia?"
   • "How big is Namibia?"

*Just ask naturally!* I'll understand. 🦁"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            response,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    elif data == "back_menu":
        categories = kb.get_categories()
        
        keyboard = []
        for category in categories:
            keyboard.append([InlineKeyboardButton(f"📌 {category}", callback_data=f"cat_{category}")])
        
        keyboard.append([InlineKeyboardButton("❓ How to ask questions", callback_data="help_questions")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📚 *Namibia Knowledge Menu*\n\nSelect a category to explore:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# =========================================================
# MAIN APPLICATION
# =========================================================
def main():
    """Start the bot"""
    print("=" * 60)
    print("🇳🇦 EVA - NAMIBIA CHATBOT")
    print("=" * 60)
    print(f"✅ Bot Token: {'Set' if TELEGRAM_BOT_TOKEN else 'NOT SET!'}")
    print(f"✅ Database: {db.db_path}")
    print(f"✅ Knowledge: {len(kb.get_all_topics())} topics")
    print(f"✅ Categories: {kb.get_categories()}")
    print("=" * 60)
    print("✨ Features:")
    print("   • Direct question answering")
    print("   • Natural language understanding")
    print("   • Knowledge base with 25+ topics")
    print("   • Interactive menu")
    print("=" * 60)
    
    # Create application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('about', about_command))
    app.add_handler(CommandHandler('menu', menu_command))
    
    # Add button handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handler - HANDLES ALL MESSAGES
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    print("🤖 Eva is running...")
    print("💡 Test with these questions:")
    print("   • 'Where is Namibia?'")
    print("   • 'What is the capital of Namibia?'")
    print("   • 'Tell me about Etosha'")
    print("   • 'Best time to visit Namibia?'")
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
