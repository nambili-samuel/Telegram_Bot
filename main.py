import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import Database
from knowledge_base import KnowledgeBase

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.kb = KnowledgeBase()
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            logger.info(f"Received /start from user {update.effective_user.id}")
            user = update.effective_user
            self.db.add_user(user.id, user.username or "Unknown")
            
            keyboard = [
                [InlineKeyboardButton("📚 Browse Topics", callback_data='browse_topics')],
                [InlineKeyboardButton("🔍 Search Knowledge", callback_data='search_knowledge')],
                [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_msg = (
                f"👋 Welcome {user.first_name}!\n\n"
                "I'm an intelligent bot with a knowledge database. "
                "I can help you find information, answer questions, and more.\n\n"
                "What would you like to do?"
            )
            
            await update.message.reply_text(welcome_msg, reply_markup=reply_markup)
            logger.info(f"Sent welcome message to user {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error in start command: {e}", exc_info=True)
            await update.message.reply_text("Sorry, something went wrong. Please try again.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🤖 *Bot Commands:*\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/search <query> - Search the knowledge base\n"
            "/topics - List all available topics\n"
            "/stats - Show your usage statistics\n"
            "/add <topic> | <content> - Add knowledge (admin only)\n\n"
            "💡 *Tips:*\n"
            "• Just send me a message to search the knowledge base\n"
            "• Use buttons for quick navigation\n"
            "• Ask questions naturally!"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
            user_id = update.effective_user.id
            query = update.message.text
            
            # Log the query
            self.db.log_query(user_id, query)
            
            # Search knowledge base
            results = self.kb.search(query)
            
            if results:
                response = "🔍 *Found relevant information:*\n\n"
                for i, result in enumerate(results[:3], 1):
                    response += f"*{i}. {result['topic']}*\n{result['content']}\n\n"
                
                response += f"_Found {len(results)} result(s)_"
            else:
                response = (
                    "😕 I couldn't find anything matching your query.\n\n"
                    "Try:\n"
                    "• Using different keywords\n"
                    "• Browsing available topics with /topics\n"
                    "• Asking in a different way"
                )
            
            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"Sent response to user {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I encountered an error processing your message.")
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text("Usage: /search <your query>")
            return
        
        query = ' '.join(context.args)
        user_id = update.effective_user.id
        
        self.db.log_query(user_id, query)
        results = self.kb.search(query)
        
        if results:
            response = "🔍 *Search Results:*\n\n"
            for i, result in enumerate(results, 1):
                response += f"*{i}. {result['topic']}*\n{result['content']}\n\n"
        else:
            response = "No results found for your query."
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def topics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /topics command"""
        topics = self.kb.get_all_topics()
        
        if topics:
            response = "📚 *Available Topics:*\n\n"
            for topic in topics:
                response += f"• {topic}\n"
            
            response += "\n_Send me a message to learn more about any topic!_"
        else:
            response = "No topics available yet."
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        stats = self.db.get_user_stats(user_id)
        
        response = (
            "📊 *Your Statistics:*\n\n"
            f"Total queries: {stats['query_count']}\n"
            f"Member since: {stats['joined_date']}\n"
            f"Last active: {stats['last_query'] or 'Never'}"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command (admin only)"""
        user_id = update.effective_user.id
        admin_ids = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
        
        if user_id not in admin_ids:
            await update.message.reply_text("⛔ This command is admin-only.")
            return
        
        if not context.args or '|' not in ' '.join(context.args):
            await update.message.reply_text(
                "Usage: /add <topic> | <content>\n"
                "Example: /add Python | Python is a programming language"
            )
            return
        
        text = ' '.join(context.args)
        topic, content = text.split('|', 1)
        topic = topic.strip()
        content = content.strip()
        
        self.kb.add_knowledge(topic, content)
        await update.message.reply_text(f"✅ Added knowledge about '{topic}'!")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'browse_topics':
            topics = self.kb.get_all_topics()
            if topics:
                response = "📚 *Available Topics:*\n\n" + '\n'.join(f"• {t}" for t in topics)
            else:
                response = "No topics available yet."
            await query.edit_message_text(response, parse_mode='Markdown')
        
        elif query.data == 'search_knowledge':
            await query.edit_message_text(
                "🔍 Just send me a message with your question or topic, "
                "and I'll search the knowledge base for you!"
            )
        
        elif query.data == 'help':
            help_text = (
                "🤖 *How to use this bot:*\n\n"
                "1. Send me any question\n"
                "2. Use /search <query> for specific searches\n"
                "3. Use /topics to browse available topics\n"
                "4. Check /stats for your usage statistics\n\n"
                "I'm here to help! 💡"
            )
            await query.edit_message_text(help_text, parse_mode='Markdown')
    
    def run(self):
        """Start the bot"""
        try:
            logger.info(f"Initializing bot with token: {self.token[:10]}...")
            app = Application.builder().token(self.token).build()
            
            # Command handlers
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("help", self.help_command))
            app.add_handler(CommandHandler("search", self.search_command))
            app.add_handler(CommandHandler("topics", self.topics_command))
            app.add_handler(CommandHandler("stats", self.stats_command))
            app.add_handler(CommandHandler("add", self.add_command))
            
            # Message handler
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Button callback handler
            app.add_handler(CallbackQueryHandler(self.button_callback))
            
            logger.info("Bot started successfully! Waiting for messages...")
            logger.info("Bot handlers registered. Starting polling...")
            
            # Run with proper error handling
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                poll_interval=1.0,
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to start bot: {e}", exc_info=True)
            raise

if __name__ == '__main__':
    try:
        logger.info("Starting Telegram Bot...")
        logger.info(f"Python version: {__import__('sys').version}")
        
        bot = TelegramBot()
        logger.info("Bot instance created successfully")
        
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        import sys
        sys.exit(1)
