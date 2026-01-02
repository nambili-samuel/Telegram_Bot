import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

class GrokAI:
    """Grok AI integration for natural conversations"""
    
    def __init__(self):
        self.api_key = os.environ.get("GROK_API_KEY", "")
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info("✅ Grok AI enabled")
        else:
            logger.warning("⚠️ Grok AI disabled (no API key)")
    
    async def chat(self, user_message, context=None):
        """
        Chat with Grok AI
        
        Args:
            user_message: The user's message
            context: Optional context (knowledge base results, conversation history)
        
        Returns:
            Grok's response or None if disabled/error
        """
        if not self.enabled:
            return None
        
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(context)
            
            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Call Grok API using requests
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"Grok API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Grok AI error: {e}")
            return None
    
    def _build_system_prompt(self, context=None):
        """Build system prompt for Grok"""
        prompt = """You are Eva Geises, an AI assistant specializing in Namibia.

Your personality:
- Friendly, warm, and enthusiastic about Namibia
- Use emojis naturally (🇳🇦, 🦁, 🏜️, etc.)
- Keep responses concise (2-3 paragraphs max)
- Always end with a helpful suggestion or question
- Mention /menu when relevant

Your knowledge areas:
- Namibian tourism, wildlife, culture
- Geography, history, and practical travel info
- Safari planning and destinations

Response style:
- Natural and conversational
- Time-appropriate greetings (Good morning/afternoon/evening)
- Engage warmly with group members
- Welcome new members enthusiastically
"""
        
        # Add knowledge base context if available
        if context and context.get('kb_results'):
            prompt += "\n\nKnowledge Base Information:\n"
            for result in context['kb_results'][:2]:
                prompt += f"- {result['topic']}: {result['content'][:200]}...\n"
            prompt += "\nUse this information to enhance your response, but respond naturally in your own words."
        
        return prompt
    
    async def generate_welcome(self, member_name, time_of_day=""):
        """Generate personalized welcome message using Grok"""
        if not self.enabled:
            return None
        
        greeting = time_of_day if time_of_day else "Hello"
        prompt = f"Generate a warm, friendly welcome message for {member_name} joining our Namibia group. Use '{greeting}' as greeting. Keep it brief (2-3 sentences), enthusiastic, and mention you're Eva, an AI assistant. Include 🇳🇦 emoji and mention /menu."
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": "You are Eva Geises, a friendly Namibia AI assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.8,
                    "max_tokens": 150
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Grok welcome error: {e}")
        
        return None
    
    async def generate_conversation_starter(self):
        """Generate engaging conversation starter using Grok"""
        if not self.enabled:
            return None
        
        prompt = "Generate a short, engaging conversation starter about Namibia for a Telegram group. It should be a question or interesting fact. Keep it to 1-2 sentences. Include relevant emoji and mention /menu."
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": "You are Eva Geises, a friendly Namibia AI assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.9,
                    "max_tokens": 100
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Grok starter error: {e}")
        
        return None