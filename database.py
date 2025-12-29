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
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_query_logs_user 
                ON query_logs(user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp 
                ON query_logs(timestamp)
            ''')
    
    def add_user(self, user_id, username):
        """Add or update user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, last_active)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    last_active = CURRENT_TIMESTAMP
            ''', (user_id, username))
    
    def log_query(self, user_id, query):
        """Log a user query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO query_logs (user_id, query)
                VALUES (?, ?)
            ''', (user_id, query))
            
            # Update user's last active time
            cursor.execute('''
                UPDATE users SET last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
    
    def get_user_stats(self, user_id):
        """Get statistics for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get user info
            cursor.execute('''
                SELECT 
                    first_seen,
                    last_active
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            
            user_row = cursor.fetchone()
            
            if not user_row:
                return {
                    'query_count': 0,
                    'joined_date': 'Unknown',
                    'last_query': None
                }
            
            # Get query count
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM query_logs
                WHERE user_id = ?
            ''', (user_id,))
            
            count_row = cursor.fetchone()
            
            # Get last query time
            cursor.execute('''
                SELECT MAX(timestamp) as last_query
                FROM query_logs
                WHERE user_id = ?
            ''', (user_id,))
            
            last_query_row = cursor.fetchone()
            
            return {
                'query_count': count_row['count'] if count_row else 0,
                'joined_date': user_row['first_seen'],
                'last_query': last_query_row['last_query'] if last_query_row else None
            }
    
    def get_all_users(self):
        """Get all users (admin function)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY last_active DESC')
            return cursor.fetchall()
    
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
            return cursor.fetchall()