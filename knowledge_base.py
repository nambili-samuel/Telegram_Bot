import os
import sqlite3
import re
import requests
import csv
import time
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'bot_data.db')
        self.csv_url = 'https://gist.githubusercontent.com/nambili-samuel/2ede6f24a58e20f2618e5adc957fdccf/raw/021a0bf53ecdd3654d3149dd84e5f58e904475dd/knowledgebase.csv'
        self.last_sync = 0
        self.sync_interval = 10 * 60 * 1000  # 10 minutes in milliseconds
        
        self.init_knowledge_base()
        self.sync_with_csv()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_knowledge_base(self):
        """Initialize knowledge base table"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT,
                    source TEXT DEFAULT 'csv',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(topic, category)
                )
            ''')
            
            # Create full-text search virtual table
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts 
                USING fts5(category, topic, content, keywords)
            ''')
            
            # Create index
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_category 
                ON knowledge(category)
            ''')
            
            # Create index for sync
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_source 
                ON knowledge(source)
            ''')
    
    def sync_with_csv(self):
        """Sync database with CSV file"""
        try:
            current_time = time.time() * 1000
            if current_time - self.last_sync < self.sync_interval and self.has_data():
                logger.info("📚 Using cached knowledge base")
                return
            
            logger.info(f"📥 Fetching knowledge base from: {self.csv_url}")
            
            # Fetch CSV from URL
            response = requests.get(self.csv_url, timeout=15)
            response.raise_for_status()
            
            # Parse CSV content
            content = response.text.splitlines()
            csv_reader = csv.DictReader(content)
            
            csv_data = []
            for row in csv_reader:
                topic = row.get('topic', '').strip()
                content_text = row.get('content', '').strip()
                category = row.get('category', 'General').strip()
                keywords = row.get('keywords', '').strip()
                
                if topic and content_text:
                    csv_data.append({
                        'topic': topic,
                        'content': content_text,
                        'category': category,
                        'keywords': keywords
                    })
            
            if not csv_data:
                logger.warning("⚠️ CSV file is empty, using existing data")
                return
            
            self.update_database(csv_data)
            self.last_sync = current_time
            logger.info(f"✅ Synced {len(csv_data)} topics from CSV")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch CSV: {e}")
            if not self.has_data():
                self.seed_fallback_data()
        except Exception as e:
            logger.error(f"❌ Error syncing CSV: {e}")
            if not self.has_data():
                self.seed_fallback_data()
    
    def update_database(self, csv_data):
        """Update database with CSV data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Remove old CSV data
            cursor.execute("DELETE FROM knowledge WHERE source = 'csv'")
            cursor.execute("DELETE FROM knowledge_fts WHERE rowid IN (SELECT id FROM knowledge WHERE source = 'csv')")
            
            # Insert new CSV data
            for item in csv_data:
                cursor.execute('''
                    INSERT OR REPLACE INTO knowledge (category, topic, content, keywords, source)
                    VALUES (?, ?, ?, ?, 'csv')
                ''', (item['category'], item['topic'], item['content'], item['keywords']))
                
                knowledge_id = cursor.lastrowid
                
                cursor.execute('''
                    INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                    VALUES (?, ?, ?, ?, ?)
                ''', (knowledge_id, item['category'], item['topic'], item['content'], item['keywords']))
    
    def has_data(self):
        """Check if database has any knowledge data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM knowledge")
            return cursor.fetchone()['count'] > 0
    
    def seed_fallback_data(self):
        """Seed fallback Namibia data if CSV fails"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if data exists
            cursor.execute('SELECT COUNT(*) as count FROM knowledge')
            if cursor.fetchone()['count'] > 0:
                return
            
            # Namibia fallback data
            namibia_data = [
                # Geography
                ('Geography', 'Where is Namibia', 'Namibia is in southwestern Africa, bordered by Angola, Zambia, Botswana, South Africa, and the Atlantic Ocean.', 'location, africa, southern africa, borders'),
                ('Geography', 'Capital of Namibia', 'The capital of Namibia is Windhoek, located in the central highlands.', 'windhoek, capital, city'),
                ('Geography', 'Size of Namibia', 'Namibia covers about 825,615 square kilometers, making it the 34th largest country.', 'size, area, square kilometers'),
                
                # Tourism
                ('Tourism', 'Best time to visit Namibia', 'The best time is May to October (dry season) for wildlife viewing and comfortable temperatures.', 'visit, travel, season, weather'),
                ('Tourism', 'Etosha National Park', 'Etosha is Namibia\'s premier wildlife destination with lions, elephants, rhinos, and over 100 mammal species.', 'etosha, safari, wildlife, park'),
                ('Tourism', 'Sossusvlei', 'Sossusvlei features the world\'s highest sand dunes (up to 380m) in the Namib Desert.', 'sossusvlei, dunes, desert, sand'),
                
                # Culture
                ('Culture', 'Himba People', 'The Himba are semi-nomadic pastoralists known for their red ochre body paint and traditional lifestyle.', 'himba, tribe, people, culture'),
                ('Culture', 'Languages in Namibia', 'English is official, but Afrikaans, German, Oshiwambo, and other indigenous languages are spoken.', 'language, english, afrikaans, oshiwambo'),
                
                # Practical
                ('Practical', 'Currency', 'Namibia uses the Namibian Dollar (NAD), which is pegged to the South African Rand.', 'money, currency, dollar, nad'),
                
                # Wildlife
                ('Wildlife', 'Desert Adapted Elephants', 'These elephants have longer legs and larger feet to walk on sand, and can survive without water for days.', 'elephant, desert, adapted, wildlife'),
                
                # Facts
                ('Facts', 'Oldest Desert', 'The Namib Desert is 55-80 million years old, making it the world\'s oldest desert.', 'desert, oldest, namib, record'),
            ]
            
            for category, topic, content, keywords in namibia_data:
                cursor.execute('''
                    INSERT INTO knowledge (category, topic, content, keywords, source)
                    VALUES (?, ?, ?, ?, 'fallback')
                ''', (category, topic, content, keywords))
                
                knowledge_id = cursor.lastrowid
                
                cursor.execute('''
                    INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                    VALUES (?, ?, ?, ?, ?)
                ''', (knowledge_id, category, topic, content, keywords))
            
            logger.info("📚 Loaded fallback knowledge base")
    
    def search(self, query, limit=5):
        """Search the knowledge base"""
        # Sync with CSV before searching if needed
        self.sync_with_csv()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clean and prepare search query
            search_terms = query.lower().strip().split()
            search_query = ' OR '.join(search_terms)
            
            # Try FTS search first
            cursor.execute('''
                SELECT k.category, k.topic, k.content, k.keywords
                FROM knowledge_fts f
                JOIN knowledge k ON k.id = f.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            ''', (search_query, limit))
            
            results = cursor.fetchall()
            
            # Fallback to LIKE search
            if not results:
                search_pattern = f'%{query}%'
                cursor.execute('''
                    SELECT category, topic, content, keywords
                    FROM knowledge
                    WHERE topic LIKE ? OR content LIKE ? OR keywords LIKE ?
                    ORDER BY 
                        CASE 
                            WHEN topic LIKE ? THEN 1
                            WHEN content LIKE ? THEN 2
                            ELSE 3
                        END
                    LIMIT ?
                ''', (search_pattern, search_pattern, search_pattern, 
                      search_pattern, search_pattern, limit))
                results = cursor.fetchall()
            
            return [dict(row) for row in results]
    
    def add_knowledge(self, topic, content, category='General', keywords=''):
        """Add new knowledge entry (for admin commands)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO knowledge (category, topic, content, keywords, source)
                VALUES (?, ?, ?, ?, 'manual')
            ''', (category, topic, content, keywords))
            
            knowledge_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT OR REPLACE INTO knowledge_fts (rowid, category, topic, content, keywords)
                VALUES (?, ?, ?, ?, ?)
            ''', (knowledge_id, category, topic, content, keywords))
    
    def get_all_topics(self):
        """Get all available topics"""
        self.sync_with_csv()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT topic FROM knowledge ORDER BY topic')
            return [row['topic'] for row in cursor.fetchall()]
    
    def get_by_category(self, category):
        """Get all topics in a category"""
        self.sync_with_csv()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT topic, content, keywords
                FROM knowledge
                WHERE category = ?
                ORDER BY topic
            ''', (category,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_categories(self):
        """Get all categories"""
        self.sync_with_csv()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM knowledge ORDER BY category')
            return [row['category'] for row in cursor.fetchall()]
