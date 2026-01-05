import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

class Database:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'bot_data.db')
        self.init_database()
    
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
    
    def init_database(self):
        """Initialize all database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Query logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS query_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    query TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Chats table for tracking group chats
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_type TEXT,
                    chat_title TEXT,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON query_logs(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON query_logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_active ON chats(is_active)')
    
    def add_user(self, user_id, username, first_name=None):
        """Add or update user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_active = CURRENT_TIMESTAMP
            ''', (user_id, username, first_name))
    
    def track_chat(self, chat_id, chat_type='group', chat_title=None):
        """Track a group chat for automated postings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chats (chat_id, chat_type, chat_title, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_type = excluded.chat_type,
                    chat_title = excluded.chat_title,
                    last_active = CURRENT_TIMESTAMP,
                    is_active = 1
            ''', (chat_id, chat_type, chat_title))
    
    def get_active_chats(self):
        """Get all active group chats for automated postings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id, chat_type, chat_title
                FROM chats
                WHERE is_active = 1
                ORDER BY last_active DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def deactivate_chat(self, chat_id):
        """Deactivate a chat (e.g., when bot is removed)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE chats
                SET is_active = 0
                WHERE chat_id = ?
            ''', (chat_id,))
    
    def log_query(self, user_id, query):
        """Log a user query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO query_logs (user_id, query)
                VALUES (?, ?)
            ''', (user_id, query))
    
    def get_user_stats(self, user_id):
        """Get user statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get user info
            cursor.execute('''
                SELECT username, joined_date
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            user_info = cursor.fetchone()
            
            # Get query count
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM query_logs
                WHERE user_id = ?
            ''', (user_id,))
            query_count = cursor.fetchone()['count']
            
            return {
                'username': user_info['username'] if user_info else 'Unknown',
                'joined_date': user_info['joined_date'] if user_info else None,
                'query_count': query_count
            }
    
    def get_all_users(self):
        """Get all users"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_popular_queries(self, limit=10):
        """Get most popular queries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT query, COUNT(*) as count
                FROM query_logs
                GROUP BY query
                ORDER BY count DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_total_queries(self):
        """Get total number of queries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM query_logs')
            return cursor.fetchone()['count']
