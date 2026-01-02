import os
import sqlite3
import re
import requests
import csv
import time
import io
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'bot_data.db')
        self.csv_url = 'https://gist.githubusercontent.com/nambili-samuel/a3bf79d67b2bd0c8d5aa9a830024417d/raw/5a67657fb15925257fe14b42566969e8d17d9f2b/namibia_knowledge_base.csv'
        self.last_sync = 0
        self.sync_interval = 10 * 60 * 1000  # 10 minutes in milliseconds
        
        self.init_knowledge_base()
        
        # Force initial sync
        try:
            logger.info("🔄 Attempting initial CSV sync...")
            self.sync_with_csv()
        except Exception as e:
            logger.error(f"❌ Initial sync failed: {e}")
            self.seed_fallback_data()
    
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
            
            # Create main knowledge table
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
                USING fts5(topic, content, category, keywords)
            ''')
            
            # Create indices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_category 
                ON knowledge(category)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_source 
                ON knowledge(source)
            ''')
            
            logger.info("✅ Database initialized")
    
    def sync_with_csv(self):
        """Sync database with CSV file"""
        try:
            current_time = time.time() * 1000
            
            # Check if we need to sync (unless first time)
            if self.has_data() and (current_time - self.last_sync < self.sync_interval):
                logger.debug("📚 Using cached knowledge base")
                return True
            
            logger.info(f"📥 Fetching knowledge base from: {self.csv_url}")
            
            # Fetch CSV from URL with timeout
            response = requests.get(self.csv_url, timeout=30)
            response.raise_for_status()
            
            # Parse CSV content
            csv_text = response.text
            logger.debug(f"📄 CSV size: {len(csv_text)} characters")
            logger.debug(f"📄 First 500 chars: {csv_text[:500]}")
            
            csv_data = []
            csv_file = io.StringIO(csv_text)
            
            # Try to read CSV with different delimiters
            try:
                reader = csv.DictReader(csv_file)
                logger.info(f"📋 CSV headers detected: {reader.fieldnames}")
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Map CSV columns to our database structure
                        # CSV has: Question, Answer, Category, Keyword
                        # We need: topic, content, category, keywords
                        
                        # Extract from CSV with flexible column names
                        topic = ''
                        content = ''
                        category = 'General'
                        keywords = ''
                        
                        # Try different possible column names
                        if 'Question' in row:
                            topic = row['Question'].strip()
                        elif 'question' in row:
                            topic = row['question'].strip()
                        
                        if 'Answer' in row:
                            content = row['Answer'].strip()
                        elif 'answer' in row:
                            content = row['answer'].strip()
                        
                        if 'Category' in row:
                            category = row['Category'].strip()
                        elif 'category' in row:
                            category = row['category'].strip()
                        
                        if 'Keyword' in row:
                            keywords = row['Keyword'].strip()
                        elif 'keyword' in row:
                            keywords = row['keyword'].strip()
                        elif 'Keywords' in row:
                            keywords = row['Keywords'].strip()
                        elif 'keywords' in row:
                            keywords = row['keywords'].strip()
                        
                        # Clean and validate
                        if not topic:
                            topic = f"Topic_{row_num}"
                        if not content:
                            content = "No content available"
                        if not category:
                            category = "General"
                        
                        # Remove quotes and clean up
                        topic = topic.replace('"', '').replace("'", "").strip()
                        content = content.replace('"', '').replace("'", "").strip()
                        category = category.replace('"', '').replace("'", "").strip()
                        keywords = keywords.replace('"', '').replace("'", "").strip()
                        
                        csv_data.append({
                            'topic': topic,
                            'content': content,
                            'category': category,
                            'keywords': keywords
                        })
                        
                        if row_num <= 3:  # Log first few rows
                            logger.debug(f"📝 Row {row_num}: {topic[:50]}... -> {category}")
                            
                    except Exception as row_error:
                        logger.warning(f"⚠️ Error parsing row {row_num}: {row_error}")
                        continue
                        
            except csv.Error as csv_error:
                logger.error(f"❌ CSV parsing error: {csv_error}")
                # Fallback: simple line parsing
                lines = csv_text.strip().split('\n')
                if len(lines) > 1:
                    headers = lines[0].split(',')
                    logger.info(f"📋 Fallback parsing with headers: {headers}")
                    for line_num, line in enumerate(lines[1:], 1):
                        if line.strip():
                            values = line.split(',')
                            if len(values) >= 2:
                                csv_data.append({
                                    'topic': values[0].strip() if len(values) > 0 else f"Topic_{line_num}",
                                    'content': values[1].strip() if len(values) > 1 else "No content",
                                    'category': values[2].strip() if len(values) > 2 else "General",
                                    'keywords': values[3].strip() if len(values) > 3 else ""
                                })
            
            if not csv_data:
                logger.warning("⚠️ No data extracted from CSV")
                if not self.has_data():
                    self.seed_fallback_data()
                return False
            
            logger.info(f"📊 Successfully extracted {len(csv_data)} items from CSV")
            
            # Update database
            success = self.update_database(csv_data)
            if success:
                self.last_sync = current_time
                logger.info(f"✅ Successfully synced {len(csv_data)} topics from CSV")
                # Also seed Namibia data to ensure we have tourism info
                self.seed_namibia_tourism_data()
            else:
                logger.error("❌ Failed to update database")
                if not self.has_data():
                    self.seed_fallback_data()
                
            return success
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch CSV: {e}")
            if not self.has_data():
                self.seed_fallback_data()
            return False
        except Exception as e:
            logger.error(f"❌ Error syncing CSV: {e}")
            if not self.has_data():
                self.seed_fallback_data()
            return False
    
    def update_database(self, csv_data):
        """Update database with CSV data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get existing manual entries to preserve
                cursor.execute("SELECT topic, category FROM knowledge WHERE source = 'manual'")
                manual_entries = {(row['topic'], row['category']) for row in cursor.fetchall()}
                
                # Remove old CSV data (but preserve manual entries)
                cursor.execute("DELETE FROM knowledge WHERE source = 'csv'")
                cursor.execute("""
                    DELETE FROM knowledge_fts 
                    WHERE rowid IN (
                        SELECT k.id 
                        FROM knowledge k 
                        WHERE k.source = 'csv'
                    )
                """)
                
                # Insert new CSV data
                inserted_count = 0
                for item in csv_data:
                    # Skip if this would overwrite a manual entry
                    if (item['topic'], item['category']) in manual_entries:
                        continue
                    
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO knowledge (category, topic, content, keywords, source)
                            VALUES (?, ?, ?, ?, 'csv')
                        ''', (item['category'], item['topic'], item['content'], item['keywords']))
                        
                        if cursor.rowcount > 0:
                            knowledge_id = cursor.lastrowid
                            
                            cursor.execute('''
                                INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (knowledge_id, item['category'], item['topic'], item['content'], item['keywords']))
                            
                            inserted_count += 1
                            
                    except sqlite3.Error as e:
                        logger.warning(f"⚠️ Error inserting {item['topic'][:30]}: {e}")
                        continue
                
                # Rebuild FTS table if needed
                if inserted_count > 0:
                    cursor.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
                
                logger.info(f"📝 Inserted {inserted_count} new CSV entries into database")
                return True
                
        except Exception as e:
            logger.error(f"❌ Database update error: {e}")
            return False
    
    def has_data(self):
        """Check if database has any knowledge data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM knowledge")
                count = cursor.fetchone()['count']
                logger.debug(f"📊 Database has {count} knowledge entries")
                return count > 0
        except Exception as e:
            logger.error(f"❌ Error checking data: {e}")
            return False
    
    def seed_namibia_tourism_data(self):
        """Seed Namibia tourism data to ensure bot has relevant info"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if we already have Namibia tourism data
                cursor.execute("SELECT COUNT(*) as count FROM knowledge WHERE category IN ('Tourism', 'Geography', 'Wildlife', 'Culture')")
                count = cursor.fetchone()['count']
                
                if count > 5:  # If we already have tourism data
                    logger.info("📚 Namibia tourism data already exists")
                    return
                
                logger.info("🌍 Adding Namibia tourism data")
                
                # Essential Namibia tourism knowledge
                namibia_data = [
                    ('Tourism', 'Where is Namibia', 'Namibia is in southwestern Africa, bordered by Angola, Zambia, Botswana, South Africa, and the Atlantic Ocean.', 'location, africa, southern africa, borders'),
                    ('Tourism', 'Capital of Namibia', 'The capital of Namibia is Windhoek, located in the central highlands.', 'windhoek, capital, city'),
                    ('Tourism', 'Best time to visit Namibia', 'The best time is May to October (dry season) for wildlife viewing and comfortable temperatures.', 'visit, travel, season, weather'),
                    ('Tourism', 'Etosha National Park', 'Etosha is Namibia\'s premier wildlife destination with lions, elephants, rhinos, and over 100 mammal species.', 'etosha, safari, wildlife, park'),
                    ('Tourism', 'Sossusvlei', 'Sossusvlei features the world\'s highest sand dunes (up to 380m) in the Namib Desert.', 'sossusvlei, dunes, desert, sand'),
                    ('Tourism', 'Swakopmund', 'Swakopmund is a coastal town with German colonial architecture and adventure activities.', 'swakopmund, coast, beach, german'),
                    ('Culture', 'Himba People', 'The Himba are semi-nomadic pastoralists known for their red ochre body paint and traditional lifestyle.', 'himba, tribe, people, culture'),
                    ('Culture', 'Herero People', 'The Herero are known for their Victorian-style dresses and cattle-herding traditions.', 'herero, tribe, people, culture'),
                    ('Wildlife', 'Desert Adapted Elephants', 'These elephants have longer legs and larger feet to walk on sand, and can survive without water for days.', 'elephant, desert, adapted, wildlife'),
                    ('Wildlife', 'Namib Desert Lions', 'Desert-adapted lions survive in harsh conditions and are larger than their savanna counterparts.', 'lion, desert, predator, wildlife'),
                    ('Wildlife', 'Cheetahs', 'Namibia has the largest population of cheetahs in the world, with excellent conservation programs.', 'cheetah, wildlife, conservation'),
                    ('Geography', 'Namib Desert', 'The Namib Desert is the world\'s oldest desert with stunning landscapes and unique wildlife.', 'desert, namib, oldest'),
                    ('Geography', 'Fish River Canyon', 'Fish River Canyon is the second largest canyon in the world, perfect for hiking adventures.', 'canyon, hiking, fish river'),
                    ('Practical', 'Visa Requirements', 'Most tourists get 90-day visa on arrival. Check with Namibian embassy for specific requirements.', 'visa, entry, requirements, travel'),
                    ('Practical', 'Currency', 'Namibia uses the Namibian Dollar (NAD), which is pegged to the South African Rand.', 'money, currency, dollar, nad'),
                    ('Facts', 'Oldest Desert', 'The Namib Desert is 55-80 million years old, making it the world\'s oldest desert.', 'desert, oldest, namib, record'),
                    ('Facts', 'Population Density', 'Namibia has about 3 people per square kilometer, making it one of the least densely populated countries.', 'population, density, people'),
                ]
                
                for category, topic, content, keywords in namibia_data:
                    cursor.execute('''
                        INSERT OR IGNORE INTO knowledge (category, topic, content, keywords, source)
                        VALUES (?, ?, ?, ?, 'tourism')
                    ''', (category, topic, content, keywords))
                    
                    if cursor.rowcount > 0:
                        knowledge_id = cursor.lastrowid
                        cursor.execute('''
                            INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (knowledge_id, category, topic, content, keywords))
                
                logger.info(f"✅ Added {len(namibia_data)} Namibia tourism topics")
                
        except Exception as e:
            logger.error(f"❌ Error seeding Namibia data: {e}")
    
    def seed_fallback_data(self):
        """Seed fallback Namibia data if CSV fails"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if data exists
                cursor.execute('SELECT COUNT(*) as count FROM knowledge')
                if cursor.fetchone()['count'] > 0:
                    logger.info("📚 Database already has data, skipping fallback")
                    return
                
                logger.info("📚 Loading fallback knowledge base")
                
                # Basic fallback data
                fallback_data = [
                    ('General', 'Welcome to Namibia', 'Namibia is a beautiful country in southwestern Africa known for its stunning landscapes, diverse wildlife, and rich cultural heritage.', 'namibia, africa, country'),
                    ('Tourism', 'Etosha National Park', 'Etosha is Namibia\'s premier wildlife destination with lions, elephants, rhinos, and over 100 mammal species.', 'etosha, safari, wildlife, park'),
                    ('Tourism', 'Sossusvlei', 'Sossusvlei features the world\'s highest sand dunes in the Namib Desert.', 'sossusvlei, dunes, desert'),
                    ('Culture', 'Himba People', 'The Himba are semi-nomadic pastoralists known for their red ochre body paint.', 'himba, tribe, culture'),
                ]
                
                for category, topic, content, keywords in fallback_data:
                    cursor.execute('''
                        INSERT OR IGNORE INTO knowledge (category, topic, content, keywords, source)
                        VALUES (?, ?, ?, ?, 'fallback')
                    ''', (category, topic, content, keywords))
                    
                    if cursor.rowcount > 0:
                        knowledge_id = cursor.lastrowid
                        cursor.execute('''
                            INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (knowledge_id, category, topic, content, keywords))
                
                logger.info(f"✅ Loaded {len(fallback_data)} fallback topics")
                
        except Exception as e:
            logger.error(f"❌ Error loading fallback data: {e}")
    
    def ensure_data(self):
        """Ensure we have data, sync if needed"""
        if not self.has_data():
            logger.warning("⚠️ No data in database, attempting sync...")
            if not self.sync_with_csv():
                self.seed_fallback_data()
        else:
            # Always ensure we have Namibia tourism data
            self.seed_namibia_tourism_data()
    
    def search(self, query, limit=5):
        """Search the knowledge base"""
        # Ensure we have data
        self.ensure_data()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean query
                query = query.strip()
                if not query:
                    return []
                
                # Prepare search terms
                search_terms = [term for term in query.lower().split() if len(term) > 2]
                
                if not search_terms:
                    return []
                
                # Build FTS query
                fts_query = ' OR '.join([f'"{term}"' for term in search_terms])
                
                # Search with FTS
                cursor.execute('''
                    SELECT k.category, k.topic, k.content, k.keywords
                    FROM knowledge_fts f
                    JOIN knowledge k ON k.id = f.rowid
                    WHERE knowledge_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                ''', (fts_query, limit))
                
                results = cursor.fetchall()
                
                # Fallback search if no FTS results
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
                
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []
    
    def add_knowledge(self, topic, content, category='General', keywords=''):
        """Add new knowledge entry (for admin commands)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO knowledge (category, topic, content, keywords, source)
                    VALUES (?, ?, ?, ?, 'manual')
                ''', (category, topic, content, keywords))
                
                knowledge_id = cursor.lastrowid
                
                # Update FTS
                cursor.execute('''
                    INSERT OR REPLACE INTO knowledge_fts (rowid, category, topic, content, keywords)
                    VALUES (?, ?, ?, ?, ?)
                ''', (knowledge_id, category, topic, content, keywords))
                
                logger.info(f"📝 Added manual entry: {topic}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error adding knowledge: {e}")
            return False
    
    def get_all_topics(self):
        """Get all available topics"""
        self.ensure_data()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT topic FROM knowledge ORDER BY topic')
                return [row['topic'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting topics: {e}")
            return []
    
    def get_by_category(self, category):
        """Get all topics in a category"""
        self.ensure_data()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT topic, content, keywords
                    FROM knowledge
                    WHERE category = ?
                    ORDER BY topic
                ''', (category,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting category {category}: {e}")
            return []
    
    def get_categories(self):
        """Get all categories"""
        self.ensure_data()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM knowledge ORDER BY category')
                return [row['category'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting categories: {e}")
            return []
