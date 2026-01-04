"""
Smart Features Add-on for Eva Geises
Add this to your existing bot WITHOUT changing any other code
"""

import random
from datetime import datetime, timedelta
from collections import defaultdict

class SmartFeatures:
    """Additional smart features for Eva - ADD to existing bot"""
    
    def __init__(self):
        self.user_message_count = defaultdict(list)  # Track messages per user
        self.user_warnings = defaultdict(int)  # Track warnings
        self.last_greeting_time = {}  # Track when we last greeted
        self.chat_activity = defaultdict(int)  # Track chat activity
        
    def check_spam(self, user_id, chat_id):
        """Detect if user is spamming - Returns (is_spam, warning_level)"""
        now = datetime.now()
        chat_key = f"{chat_id}_{user_id}"
        
        # Clean old messages (older than 30 seconds)
        self.user_message_count[chat_key] = [
            msg_time for msg_time in self.user_message_count[chat_key]
            if now - msg_time < timedelta(seconds=30)
        ]
        
        # Add current message
        self.user_message_count[chat_key].append(now)
        
        # Check spam: more than 5 messages in 30 seconds
        message_count = len(self.user_message_count[chat_key])
        
        if message_count > 5:
            self.user_warnings[chat_key] += 1
            return True, self.user_warnings[chat_key]
        
        return False, 0
    
    def get_spam_warning(self, warning_level, username="friend"):
        """Get appropriate spam warning message"""
        warnings = {
            1: f"⚠️ Hey {username}, please slow down a bit! Let's keep the chat comfortable for everyone. 😊",
            2: f"🛑 {username}, that's quite a lot of messages! Please give others a chance to chat. 🙏",
            3: f"❌ {username}, please stop spamming. This is your final warning. Continued spam may result in action. ⛔"
        }
        
        return warnings.get(min(warning_level, 3), warnings[3])
    
    def should_greet_chat(self, chat_id, hours=2):
        """Check if we should greet the chat (every X hours)"""
        now = datetime.now()
        last_greeting = self.last_greeting_time.get(chat_id)
        
        if not last_greeting or now - last_greeting > timedelta(hours=hours):
            self.last_greeting_time[chat_id] = now
            return True
        
        return False
    
    def get_time_based_greeting(self):
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
    
    def get_varied_welcome(self, name):
        """Get varied welcome messages with different styles"""
        hour = datetime.now().hour
        greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening" if 17 <= hour < 21 else "Hello"
        
        welcomes = [
            # Style 1: Enthusiastic
            f"🎉 {greeting} {name}! Welcome to our Namibia community!\n\nI'm Eva Geises, your AI guide. Feel free to ask me anything about Namibia or use /menu to explore! 🇳🇦🦁",
            
            # Style 2: Friendly
            f"👋 {greeting} {name}! Great to have you here!\n\nI'm Eva, an AI assistant specializing in Namibia. Ask me questions or check out /menu for organized topics! 🏜️✨",
            
            # Style 3: Warm
            f"🌟 {greeting} and welcome, {name}!\n\nI'm Eva Geises, here to help with all things Namibia - from wildlife safaris to cultural insights! Use /menu or just ask! 🇳🇦💚",
            
            # Style 4: Informative
            f"👋 {greeting} {name}! Welcome aboard!\n\nI'm Eva, your Namibia expert AI. I know about tourism, wildlife, culture, and more. Try /menu or ask me anything! 🦓🏞️",
            
            # Style 5: Inviting
            f"✨ {greeting} {name}! So glad you joined us!\n\nI'm Eva Geises, ready to share amazing Namibia insights. Explore /menu or ask me questions anytime! 🇳🇦🌅",
            
            # Style 6: Casual
            f"Hey {name}! {greeting}! 🙌\n\nI'm Eva, your friendly Namibia AI. Whether it's safaris, culture, or travel tips - I've got you covered! Check /menu or ask away! 🦁✨"
        ]
        
        return random.choice(welcomes)
    
    def get_engagement_prompt(self):
        """Get engaging questions/prompts for the group"""
        prompts = [
            "💭 *Quick poll:* What's the first thing you'd do in Namibia?\n\nA) Safari at Etosha 🦁\nB) Climb Sossusvlei dunes 🏜️\nC) Explore Swakopmund 🏖️\nD) Meet the Himba people 👥\n\n📱 Learn more with /menu!",
            
            "🎯 *Discussion time:* Which Namibia destination surprises you most?\n\nShare your thoughts!\n\n💡 Not sure? Try /menu → Tourism!",
            
            "🌟 *Did you know?* Namibia has the world's oldest desert!\n\nWhat other Namibia facts would you like to know?\n\n📚 Check /menu for more!",
            
            "🦁 *Wildlife question:* Ever seen desert-adapted elephants?\n\nThey're incredible! Want to learn more?\n\n📱 Use /menu → Wildlife!",
            
            "🏜️ *Fun fact:* Sossusvlei's dunes can reach 380 meters high!\n\nWhat else interests you about Namibia?\n\n💡 Explore /menu!",
            
            "👥 *Cultural curiosity:* The Himba people use red ochre as cosmetics!\n\nInterested in more cultural insights?\n\n📚 Try /menu → Culture!"
        ]
        
        return random.choice(prompts)
    
    def detect_question_intent(self, message):
        """Detect if message is a question requiring help"""
        question_indicators = [
            "help", "how do i", "how can i", "what is", "where is", 
            "when should", "which", "recommend", "suggest", "advice",
            "tell me", "explain", "show me", "guide", "tips"
        ]
        
        msg_lower = message.lower()
        return any(indicator in msg_lower for indicator in question_indicators) or "?" in message
    
    def get_encouragement(self):
        """Get random encouragement messages"""
        encouragements = [
            "💡 *Reminder:* I'm here to help! Ask me anything about Namibia or use /menu!",
            "🌟 *Tip:* Use /menu to explore Namibia topics organized by category!",
            "📚 *Did you know?* I can answer questions about 24+ Namibia topics! Try /topics to see them all!",
            "🦁 *Pro tip:* Ask specific questions for the best answers! For example: \"Where is Etosha?\"",
            "✨ *Friendly reminder:* I respond to greetings! Say hi anytime! 👋"
        ]
        
        return random.choice(encouragements)