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
        self.csv_url = 'https://gist.githubusercontent.com/nambili-samuel/a3bf79d67b2bd0c8d5aa9a830024417d/raw/36f6f55b9997c60ff825ddc806cee8dfd76916d7/namibia_knowledge_base.csv'
        self.last_sync = 0
        self.sync_interval = 10 * 60 * 1000  # 10 minutes in milliseconds
        
        self.init_knowledge_base()
        self.seed_namibia_data()
        
        # Sync with CSV after seeding local data
        try:
            logger.info("🔄 Attempting initial CSV sync...")
            self.sync_with_csv()
        except Exception as e:
            logger.error(f"❌ Initial CSV sync failed: {e}")
    
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
                    source TEXT DEFAULT 'local',
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
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_source 
                ON knowledge(source)
            ''')
            
            logger.info("✅ Database initialized")
    
    def seed_namibia_data(self):
        """Seed Namibia knowledge base including real estate"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if local data exists
            cursor.execute("SELECT COUNT(*) as count FROM knowledge WHERE source = 'local'")
            if cursor.fetchone()['count'] > 0:
                return
            
            # Namibia knowledge data
            namibia_data = [
                # REAL ESTATE PROPERTIES
                ('Real Estate', '4 Bedroom House for Sale - Windhoek West', 
                 '🏠 Beautiful 4 bedroom house for sale in Windhoek West. Perfect for families. Contact Loide Hashonia on +264 81 263 7307 for viewing and more information.', 
                 'windhoek, west, house, 4 bedroom, sale, property, loide hashonia, contact'),
                
                ('Real Estate', 'Land Plot for Sale - Omuthiya (11470 sqm)', 
                 '🗺️ Prime 11470 sqm land plot for sale in Omuthiya town. Ideal location for service station and commercial businesses. Excellent investment opportunity. Contact Loide Hashonia at +264 81 263 7307.', 
                 'omuthiya, land, plot, 11470, service station, business, commercial, sale, loide hashonia'),
                
                ('Real Estate', '3 Bedroom House for Sale - Okahandja', 
                 '🏡 Charming 3 bedroom house for sale in Okahandja, conveniently located just behind the shopping mall. Great location with easy access to amenities. Contact Loide Hashonia at +264 81 263 7307 on WhatsApp.', 
                 'okahandja, house, 3 bedroom, shopping mall, sale, property, loide hashonia, whatsapp'),
                
                # Geography
                ('Geography', 'Where is Namibia', 'Namibia is in southwestern Africa, bordered by Angola, Zambia, Botswana, South Africa, and the Atlantic Ocean.', 'location, africa, southern africa, borders'),
                ('Geography', 'Capital of Namibia', 'The capital of Namibia is Windhoek, located in the central highlands.', 'windhoek, capital, city'),
                ('Geography', 'Size of Namibia', 'Namibia covers about 825,615 square kilometers, making it the 34th largest country.', 'size, area, square kilometers'),
                
                # Tourism
                ('Tourism', 'Best time to visit Namibia', 'The best time is May to October (dry season) for wildlife viewing and comfortable temperatures.', 'visit, travel, season, weather'),
                ('Tourism', 'Etosha National Park', 'Etosha is Namibia\'s premier wildlife destination with lions, elephants, rhinos, and over 100 mammal species.', 'etosha, safari, wildlife, park'),
                ('Tourism', 'Sossusvlei', 'Sossusvlei features the world\'s highest sand dunes (up to 380m) in the Namib Desert.', 'sossusvlei, dunes, desert, sand'),
                ('Tourism', 'Swakopmund', 'Swakopmund is a coastal town with German colonial architecture and adventure activities.', 'swakopmund, coast, beach, german'),
                ('Tourism', 'Fish River Canyon', 'The Fish River Canyon is located in the south of Namibia. It is the the second largest canyon in the world with 160 kilometres long, up to 27 km wide and 550 meters deep.', 'canyon, hiking, fish river'),
                ('Tourism', 'Namib Desert', 'The Namib Desert is the world\'s oldest desert with stunning landscapes and unique wildlife.', 'desert, namib, oldest'),
                
                # Culture
                ('Culture', 'Himba People', 'The Himba are semi-nomadic pastoralists known for their red ochre body paint and traditional lifestyle.', 'himba, tribe, people, culture'),
                ('Culture', 'Herero People', 'The Herero are known for their Victorian-style dresses and cattle-herding traditions.', 'herero, tribe, people, culture'),
                ('Culture', 'Languages in Namibia', 'English is official, but Afrikaans, German, Oshiwambo, and other indigenous languages are spoken.', 'language, english, afrikaans, oshiwambo'),
                
                # Practical
                ('Practical', 'Visa Requirements', 'Namibia requires most visitors to have a visa include a valid passport (6+ months validity, 3 blank pages), with options for visa on arrival (VoA) at major ports for a fee (N$1,600 for non-Africans). Check with Namibian embassy for specific requirements.', 'visa, entry, requirements, travel'),
                ('Practical', 'Currency', 'Namibian Dollar (N$) is a national currency which is pegged to the South African Rand which is also a legal tender in Namibia. The Namibian dollar has denominations of 200, 100, 50, 20 and 10 dollar notes, 5 and 1 dollar coins and 50, 10 and 5 cent coins.', 'money, currency, dollar, nad'),
                ('Practical', 'Weather', 'Namibia has a dry climate with 300+ sunny days per year. Days are warm, nights can be cool. Temperatures may rise above 40 degrees C in summer, sometimes even up to 50 degrees C in the desert areas, the Namib and the Kalahari. In winter temperatures still reach a pleasant 20 to 25 degrees C. At night temperatures may drop below 0 degrees C though.', 'weather, climate, temperature'),
                
                # Wildlife
                ('Wildlife', 'Fauna', 'Namibia boasts unique wildlife, including the iconic Gemsbok (Oryx), elephants, buffalos, rhinos, lions and cheetahs, plus large populations of springbok, zebras, and giraffes.', 'elephant, desert, adapted, wildlife'),
                ('Wildlife', 'Flora', 'Namibia has unique flora such as a resilient Welwitschia mirabilis, Quiver Tree (Kokerboom) and other unique species include diverse aloes (like the endemic Aloe erinacea), succulents (Lithops), thorny acacias, Moringa trees, and Mopane trees.', 'lion, desert, predator, wildlife'),
                ('Wildlife', 'Cheetahs', 'As per Cheetah Conservation Fund statistics, Namibia has the largest population of cheetahs in the world, with excellent conservation programs.', 'cheetah, wildlife, conservation'),
                
                # History
                ('History', 'Independence Day', 'Namibia gained independence from South Africa on March 21, 1990, ending decades of German colonial rule followed by South African administration and apartheid, with Sam Nujoma becoming its first President after SWAPO\'s victory in UN-supervised elections.','colonial, namibia, history, independence'),
                ('History', 'German Colonization', 'German colonization of Namibia began in 1883, when the German trader Adolf Luderitz annexed the territory. This ultimately led to the Herero and Namaqua Genocide, carried out under General Lothar von Trotha. After World War I, the territory came under the control of South Africa, where it was administered under an apartheid system.', 'german, colonial, history'),
                
                # Facts
                ('Facts', 'Namib Desert', 'The Namib Desert, one of the world\'s oldest and driest deserts, stretches more than 2,000 km from north to south along Namibia\'s Atlantic coast. It is only the place on Earth where the sea meets the desert directly.', 'desert, oldest, namib, record'),
                ('Facts', 'Population', 'Namibia\'s population is around 3.1 million people, making it one of the world\'s most sparsely populated countries, with a density of about 4 people per square kilometer.', 'population, density, people'),
                ('Facts', 'Natural Resources', 'Namibia\'s natural resources are crucial to its economy, primarily driven by significant mineral wealth like diamonds, uranium, zinc, copper, and gold, alongside growing oil and gas finds, and vast potential in renewable energy (solar, wind, green hydrogen).', 'stars, stargazing, dark sky, astronomy'),
                ('Facts', 'Economy', 'Namibia\'s economy is a lower-middle-income country driven by mining (diamonds, uranium), agriculture, and tourism, but it struggles with high inequality (second-highest Gini coefficient globally) and unemployment despite significant progress.', 'conservation, environment, protected'),
            ]
            
            for category, topic, content, keywords in namibia_data:
                cursor.execute('''
                    INSERT OR IGNORE INTO knowledge (category, topic, content, keywords, source)
                    VALUES (?, ?, ?, ?, 'local')
                ''', (category, topic, content, keywords))
                
                if cursor.rowcount > 0:
                    knowledge_id = cursor.lastrowid
                    
                    cursor.execute('''
                        INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (knowledge_id, category, topic, content, keywords))
            
            logger.info(f"✅ Seeded {len(namibia_data)} local topics including real estate")
    
    def sync_with_csv(self):
        """Sync database with CSV file from GitHub Gist"""
        try:
            current_time = time.time() * 1000
            
            # Check if we need to sync
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
            
            csv_data = []
            csv_file = io.StringIO(csv_text)
            
            try:
                reader = csv.DictReader(csv_file)
                logger.info(f"📋 CSV headers detected: {reader.fieldnames}")
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Map CSV columns to database structure
                        # CSV has: Question, Answer, Category, Keyword
                        # We need: topic, content, category, keywords
                        
                        topic = ''
                        content = ''
                        category = 'General'
                        keywords = ''
                        
                        # Try different possible column names
                        if 'Question' in row:
                            topic = row['Question'].strip()
                        elif 'question' in row:
                            topic = row['question'].strip()
                        elif 'topic' in row:
                            topic = row['topic'].strip()
                        elif 'Topic' in row:
                            topic = row['Topic'].strip()
                        
                        if 'Answer' in row:
                            content = row['Answer'].strip()
                        elif 'answer' in row:
                            content = row['answer'].strip()
                        elif 'content' in row:
                            content = row['content'].strip()
                        elif 'Content' in row:
                            content = row['Content'].strip()
                        
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
                return False
            
            if not csv_data:
                logger.warning("⚠️ No data parsed from CSV")
                return False
            
            # Insert/update data in database
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                added = 0
                updated = 0
                
                for entry in csv_data:
                    try:
                        # Check if entry exists
                        cursor.execute('''
                            SELECT id FROM knowledge 
                            WHERE topic = ? AND category = ?
                        ''', (entry['topic'], entry['category']))
                        
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing entry
                            cursor.execute('''
                                UPDATE knowledge 
                                SET content = ?, keywords = ?, 
                                    updated_at = CURRENT_TIMESTAMP,
                                    source = 'csv'
                                WHERE id = ?
                            ''', (entry['content'], entry['keywords'], existing['id']))
                            
                            # Update FTS
                            cursor.execute('''
                                DELETE FROM knowledge_fts WHERE rowid = ?
                            ''', (existing['id'],))
                            
                            cursor.execute('''
                                INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (existing['id'], entry['category'], entry['topic'], 
                                  entry['content'], entry['keywords']))
                            
                            updated += 1
                        else:
                            # Insert new entry
                            cursor.execute('''
                                INSERT INTO knowledge (category, topic, content, keywords, source)
                                VALUES (?, ?, ?, ?, 'csv')
                            ''', (entry['category'], entry['topic'], entry['content'], entry['keywords']))
                            
                            knowledge_id = cursor.lastrowid
                            
                            cursor.execute('''
                                INSERT INTO knowledge_fts (rowid, category, topic, content, keywords)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (knowledge_id, entry['category'], entry['topic'], 
                                  entry['content'], entry['keywords']))
                            
                            added += 1
                            
                    except Exception as insert_error:
                        logger.error(f"❌ Error inserting {entry['topic']}: {insert_error}")
                        continue
                
                logger.info(f"✅ CSV sync complete: {added} added, {updated} updated")
            
            self.last_sync = current_time
            return True
            
        except requests.RequestException as e:
            logger.error(f"❌ Failed to fetch CSV: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ CSV sync error: {e}")
            return False
    
    def has_data(self):
        """Check if database has any data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM knowledge')
                return cursor.fetchone()['count'] > 0
        except:
            return False
    
    def ensure_data(self):
        """Ensure we have data, sync if needed"""
        if not self.has_data():
            logger.warning("⚠️ No data in database, attempting sync...")
            self.sync_with_csv()
    
    def search(self, query, limit=5):
        """Search the knowledge base"""
        # Ensure we have data and auto-sync if needed
        self.ensure_data()
        
        try:
            # Try to sync in background (non-blocking)
            current_time = time.time() * 1000
            if (current_time - self.last_sync) >= self.sync_interval:
                self.sync_with_csv()
        except:
            pass  # Don't block search if sync fails
        
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
        """Add new knowledge entry"""
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
        self.ensure_data()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT topic FROM knowledge ORDER BY topic')
            return [row['topic'] for row in cursor.fetchall()]
    
    def get_by_category(self, category):
        """Get all topics in a category"""
        self.ensure_data()
        
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
        self.ensure_data()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM knowledge ORDER BY category')
            return [row['category'] for row in cursor.fetchall()]
