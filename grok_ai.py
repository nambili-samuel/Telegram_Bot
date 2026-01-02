import os
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

class GrokAI:
    """Grok AI integration - Non-blocking version"""
    
    def __init__(self):
        self.api_key = os.environ.get("GROK_API_KEY", "")
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.enabled = bool(self.api_key)
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        if self.enabled:
            logger.info("✅ Grok AI enabled")
        else:
            logger.info("ℹ️ Grok AI disabled - using fallback responses")
    
    def _make_request(self, messages, max_tokens=500, temperature=0.7):
        """Make synchronous request to Grok API"""
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=8  # Short timeout to not block
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug(f"Grok request failed: {e}")
        
        return None
    
    async def chat(self, user_message, context=None):
        """Chat with Grok AI - Non-blocking"""
        if not self.enabled:
            return None
        
        try:
            system_prompt = """You are Eva Geises, a friendly Namibia AI assistant.
Be warm, use emojis (🇳🇦, 🦁, 🏜️), keep responses short (2-3 sentences), mention /menu."""
            
            if context and context.get('kb_results'):
                system_prompt += f"\n\nContext: {context['kb_results'][0]['topic']}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Run in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self._make_request(messages, max_tokens=500, temperature=0.7)
            )
            
            return result
            
        except Exception as e:
            logger.debug(f"Grok chat error: {e}")
            return None
    
    async def generate_welcome(self, member_name, time_of_day=""):
        """Generate welcome - Non-blocking"""
        if not self.enabled:
            return None
        
        try:
            greeting = time_of_day or "Hello"
            messages = [
                {"role": "system", "content": "You are Eva Geises, friendly Namibia AI. Keep it very brief."},
                {"role": "user", "content": f"Welcome {member_name}. Use '{greeting}'. 2 sentences. Mention Eva and /menu. Include 🇳🇦"}
            ]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self._make_request(messages, max_tokens=100, temperature=0.8)
            )
            
            return result
            
        except Exception as e:
            logger.debug(f"Grok welcome error: {e}")
            return None
    
    async def generate_conversation_starter(self):
        """Generate starter - Non-blocking"""
        if not self.enabled:
            return None
        
        try:
            messages = [
                {"role": "system", "content": "You are Eva Geises, friendly Namibia AI."},
                {"role": "user", "content": "Short Namibia fact or question for group chat. 1-2 sentences. Include emoji and /menu."}
            ]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self._make_request(messages, max_tokens=80, temperature=0.9)
            )
            
            return result
            
        except Exception as e:
            logger.debug(f"Grok starter error: {e}")
            return None
    
    def __del__(self):
        """Cleanup executor"""
        try:
            self.executor.shutdown(wait=False)
        except:
            pass