import os
import sqlite3
from contextlib import contextmanager

class KnowledgeBase:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'bot_data.db')
        self.init_knowledge_base()
        self.seed_initial_data()
    
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
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create full-text search virtual table
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts 
                USING fts5(topic, content, keywords)
            ''')
            
            # Create index for better search performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_knowledge_topic 
                ON knowledge(topic)
            ''')
    
    def seed_initial_data(self):
        """Seed the knowledge base with initial data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if data already exists
            cursor.execute('SELECT COUNT(*) as count FROM knowledge')
            if cursor.fetchone()['count'] > 0:
                return
            
            # Initial knowledge entries
            initial_data = [
                ('Python Programming', 
                 'Python is a high-level, interpreted programming language known for its simplicity and readability. It supports multiple programming paradigms including procedural, object-oriented, and functional programming.',
                 'programming, code, development, syntax'),
                
                ('Machine Learning',
                 'Machine Learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It uses statistical techniques to give computers the ability to learn from data.',
                 'AI, artificial intelligence, data science, algorithms'),
                
                ('Web Development',
                 'Web development involves creating websites and web applications. It includes front-end development (user interface), back-end development (server-side logic), and database management.',
                 'HTML, CSS, JavaScript, websites, frontend, backend'),
                
                ('Database Systems',
                 'Database systems are organized collections of data that can be easily accessed, managed, and updated. Common types include relational databases (SQL) and NoSQL databases.',
                 'SQL, data storage, queries, tables'),
                
                ('API Development',
                 'APIs (Application Programming Interfaces) allow different software applications to communicate with each other. REST and GraphQL are popular API architectures.',
                 'REST, GraphQL, endpoints, integration'),
                
                ('Cloud Computing',
                 'Cloud computing delivers computing services over the internet, including servers, storage, databases, networking, and software. Major providers include AWS, Google Cloud, and Azure.',
                 'AWS, Azure, GCP, infrastructure, hosting'),
                
                ('Version Control',
                 'Version control systems track changes to code over time. Git is the most popular version control system, often used with platforms like GitHub, GitLab, or Bitbucket.',
                 'git, github, commits, branches, repository'),
                
                ('Cybersecurity',
                 'Cybersecurity protects systems, networks, and data from digital attacks. It includes practices like encryption, authentication, firewall configuration, and security auditing.',
                 'security, encryption, authentication, protection'),
                
                ('Mobile Development',
                 'Mobile development creates applications for mobile devices. Native development uses platform-specific languages (Swift for iOS, Kotlin for Android), while cross-platform frameworks like React Native enable code sharing.',
                 'iOS, Android, apps, React Native, Flutter'),
                
                ('DevOps',
                 'DevOps combines software development and IT operations to shorten development cycles and provide continuous delivery. It emphasizes automation, monitoring, and collaboration.',
                 'CI/CD, automation, deployment, Docker, Kubernetes')
            ]
            
            for topic, content, keywords in initial_data:
                cursor.execute('''
                    INSERT INTO knowledge (topic, content, keywords)
                    VALUES (?, ?, ?)
                ''', (topic, content, keywords))
                
                # Add to FTS table
                cursor.execute('''
                    INSERT INTO knowledge_fts (rowid, topic, content, keywords)
                    VALUES (last_insert_rowid(), ?, ?, ?)
                ''', (topic, content, keywords))
    
    def search(self, query, limit=5):
        """Search the knowledge base"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Use FTS for better search results
            search_query = ' OR '.join(query.split())
            
            cursor.execute('''
                SELECT k.topic, k.content, k.keywords
                FROM knowledge_fts f
                JOIN knowledge k ON k.id = f.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            ''', (search_query, limit))
            
            results = cursor.fetchall()
            
            # If no FTS results, fall back to LIKE search
            if not results:
                search_pattern = f'%{query}%'
                cursor.execute('''
                    SELECT topic, content, keywords
                    FROM knowledge
                    WHERE topic LIKE ? OR content LIKE ? OR keywords LIKE ?
                    LIMIT ?
                ''', (search_pattern, search_pattern, search_pattern, limit))
                results = cursor.fetchall()
            
            return [dict(row) for row in results]
    
    def add_knowledge(self, topic, content, keywords=''):
        """Add new knowledge entry"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO knowledge (topic, content, keywords)
                VALUES (?, ?, ?)
            ''', (topic, content, keywords))
            
            knowledge_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT INTO knowledge_fts (rowid, topic, content, keywords)
                VALUES (?, ?, ?, ?)
            ''', (knowledge_id, topic, content, keywords))
    
    def update_knowledge(self, knowledge_id, topic=None, content=None, keywords=None):
        """Update existing knowledge entry"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if topic:
                updates.append('topic = ?')
                params.append(topic)
            if content:
                updates.append('content = ?')
                params.append(content)
            if keywords:
                updates.append('keywords = ?')
                params.append(keywords)
            
            if updates:
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(knowledge_id)
                
                query = f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                # Update FTS table
                cursor.execute('''
                    DELETE FROM knowledge_fts WHERE rowid = ?
                ''', (knowledge_id,))
                
                cursor.execute('''
                    INSERT INTO knowledge_fts (rowid, topic, content, keywords)
                    SELECT id, topic, content, keywords
                    FROM knowledge WHERE id = ?
                ''', (knowledge_id,))
    
    def delete_knowledge(self, knowledge_id):
        """Delete knowledge entry"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM knowledge WHERE id = ?', (knowledge_id,))
            cursor.execute('DELETE FROM knowledge_fts WHERE rowid = ?', (knowledge_id,))
    
    def get_all_topics(self):
        """Get all available topics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT topic FROM knowledge ORDER BY topic')
            return [row['topic'] for row in cursor.fetchall()]
    
    def get_by_topic(self, topic):
        """Get knowledge by exact topic match"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT topic, content, keywords
                FROM knowledge
                WHERE topic = ?
            ''', (topic,))
            row = cursor.fetchone()
            return dict(row) if row else None