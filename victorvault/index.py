"""SQLite index module for metadata storage and search."""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class VaultIndex:
    """SQLite-based index for vault metadata and search."""
    
    def __init__(self, db_path: Path):
        """Initialize vault index.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    session_data TEXT,
                    title TEXT,
                    url TEXT,
                    tab_count INTEGER,
                    search_text TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tabs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    tab_index INTEGER NOT NULL,
                    title TEXT,
                    url TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(file_hash)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_search ON sessions(search_text)
            """)
            
            conn.commit()
    
    def add_session(self, file_path: Path, file_hash: str, session_data: dict) -> int:
        """Add session to index.
        
        Args:
            file_path: Path to session file in vault
            file_hash: SHA256 hash of file
            session_data: Parsed session data
            
        Returns:
            Session ID
        """
        # Extract searchable text
        search_parts = []
        title = ""
        url = ""
        tab_count = 0
        
        if isinstance(session_data, dict):
            tabs = session_data.get('tabs', [])
            tab_count = len(tabs)
            
            for tab in tabs:
                if isinstance(tab, dict):
                    if 'title' in tab:
                        search_parts.append(tab['title'])
                        if not title:
                            title = tab['title']
                    if 'url' in tab:
                        search_parts.append(tab['url'])
                        if not url:
                            url = tab['url']
        
        search_text = " ".join(search_parts)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO sessions (file_path, file_hash, ingested_at, session_data, title, url, tab_count, search_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(file_path),
                file_hash,
                datetime.now().isoformat(),
                json.dumps(session_data),
                title,
                url,
                tab_count,
                search_text
            ))
            session_id = cursor.lastrowid
            
            # Add individual tabs
            if isinstance(session_data, dict):
                tabs = session_data.get('tabs', [])
                for idx, tab in enumerate(tabs):
                    if isinstance(tab, dict):
                        conn.execute("""
                            INSERT INTO tabs (session_id, tab_index, title, url)
                            VALUES (?, ?, ?, ?)
                        """, (
                            session_id,
                            idx,
                            tab.get('title', ''),
                            tab.get('url', '')
                        ))
            
            conn.commit()
            return session_id
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for sessions matching query.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of session dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT id, file_path, file_hash, ingested_at, title, url, tab_count
                FROM sessions
                WHERE search_text LIKE ?
                ORDER BY ingested_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))
            
            results = []
            for row in cursor:
                results.append({
                    'id': row['id'],
                    'file_path': row['file_path'],
                    'file_hash': row['file_hash'],
                    'ingested_at': row['ingested_at'],
                    'title': row['title'],
                    'url': row['url'],
                    'tab_count': row['tab_count']
                })
            
            return results
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT * FROM sessions WHERE id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'file_path': row['file_path'],
                    'file_hash': row['file_hash'],
                    'ingested_at': row['ingested_at'],
                    'session_data': json.loads(row['session_data']),
                    'title': row['title'],
                    'url': row['url'],
                    'tab_count': row['tab_count']
                }
            return None
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions.
        
        Returns:
            List of session dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT id, file_path, file_hash, ingested_at, title, url, tab_count, session_data
                FROM sessions
                ORDER BY ingested_at DESC
            """)
            
            results = []
            for row in cursor:
                results.append({
                    'id': row['id'],
                    'file_path': row['file_path'],
                    'file_hash': row['file_hash'],
                    'ingested_at': row['ingested_at'],
                    'title': row['title'],
                    'url': row['url'],
                    'tab_count': row['tab_count'],
                    'session_data': json.loads(row['session_data']) if row['session_data'] else {}
                })
            
            return results
    
    def hash_exists(self, file_hash: str) -> bool:
        """Check if hash already exists in index.
        
        Args:
            file_hash: SHA256 hash
            
        Returns:
            True if hash exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM sessions WHERE file_hash = ?
            """, (file_hash,))
            return cursor.fetchone()[0] > 0
