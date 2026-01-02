import os
import requests
import logging
import asyncio

logger = logging.getLogger(__name__)

class GrokAI:
    """Grok AI integration - Simplified version that won't crash"""
    
    def __init__(self):
        self.api_key = os.environ.get("GROK_API_KEY", "")
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info("✅ Grok AI enabled")
        else:
            logger.info("ℹ️ Grok AI disabled (no API key) - using fallback responses")
    
    async def chat(self, user_message, context=None):
        """Chat with Grok AI - Returns None on any error"""
        if not self.enabled:
            return None
        
        try:
            system_prompt = self._build_system_prompt(context)
            
            # Use asyncio to run requests in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500
                    },
                    timeout=10  # Shorter timeout
                )
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.warning(f"Grok AI unavailable: {e}")
        
        return None
    
    def _build_system_prompt(self, context=None):
        """Build system prompt for Grok"""
        prompt = """You are Eva Geises, an AI assistant specializing in Namibia.

Your personality:
- Friendly, warm, and enthusiastic about Namibia
- Use emojis naturally (🇳🇦, 🦁, 🏜️, etc.)
- Keep responses concise (2-3 paragraphs max)
- Always end with a helpful suggestion
- Mention /menu when relevant

Response style:
- Natural and conversational
- Time-appropriate greetings
- Engage warmly with group members
"""
        
        if context and context.get('kb_results'):
            prompt += "\n\nKnowledge Base:\n"
            for result in context['kb_results'][:2]:
                prompt += f"- {result['topic']}: {result['content'][:150]}...\n"
        
        return prompt
    
    async def generate_welcome(self, member_name, time_of_day=""):
        """Generate welcome - Returns None on error"""
        if not self.enabled:
            return None
        
        try:
            greeting = time_of_day if time_of_day else "Hello"
            prompt = f"Welcome {member_name} to Namibia group. Use '{greeting}'. Brief 2 sentences. Mention you're Eva. Include 🇳🇦 and /menu."
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": "You are Eva Geises, friendly Namibia AI."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.8,
                        "max_tokens": 100
                    },
                    timeout=10
                )
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.warning(f"Grok welcome unavailable: {e}")
        
        return None
    
    async def generate_conversation_starter(self):
        """Generate starter - Returns None on error"""
        if not self.enabled:
            return None
        
        try:
            prompt = "Short Namibia conversation starter. 1-2 sentences. Question or fact. Include emoji and /menu."
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": "You are Eva Geises, friendly Namibia AI."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.9,
                        "max_tokens": 80
                    },
                    timeout=10
                )
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.warning(f"Grok starter unavailable: {e}")
        
        return None