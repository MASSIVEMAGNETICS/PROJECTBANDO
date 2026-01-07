"""Ingestion module for processing session files with atomic writes and deduplication."""

import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import tempfile


class IngestEngine:
    """Engine for ingesting session files into the vault."""
    
    def __init__(self, inbox_path: Path, vault_path: Path, quarantine_path: Path):
        """Initialize ingestion engine.
        
        Args:
            inbox_path: Directory to monitor for incoming files
            vault_path: Directory to store processed files
            quarantine_path: Directory for quarantined files
        """
        self.inbox_path = inbox_path
        self.vault_path = vault_path
        self.quarantine_path = quarantine_path
        self.processed_hashes = set()
        
        # Ensure directories exist
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.quarantine_path.mkdir(parents=True, exist_ok=True)
    
    def compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex string of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def validate_session_json(self, file_path: Path) -> Tuple[bool, Optional[dict]]:
        """Validate session JSON file.
        
        Args:
            file_path: Path to session JSON file
            
        Returns:
            Tuple of (is_valid, parsed_data)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return True, data
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            return False, None
    
    def get_vault_path(self, timestamp: Optional[datetime] = None) -> Path:
        """Get vault path with YYYY/MM/DD/stamp structure.
        
        Args:
            timestamp: Timestamp to use (defaults to now)
            
        Returns:
            Path object for vault storage
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        stamp = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        date_path = self.vault_path / timestamp.strftime("%Y") / timestamp.strftime("%m") / timestamp.strftime("%d") / stamp
        return date_path
    
    def atomic_copy(self, source: Path, destination: Path):
        """Atomically copy file using temp->rename pattern.
        
        Args:
            source: Source file path
            destination: Destination file path
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temp file in same directory as destination for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(dir=destination.parent, prefix='.tmp_')
        try:
            with open(temp_fd, 'wb') as temp_f:
                with open(source, 'rb') as source_f:
                    shutil.copyfileobj(source_f, temp_f)
            
            # Atomic rename
            Path(temp_path).rename(destination)
        except Exception:
            # Clean up temp file on error
            Path(temp_path).unlink(missing_ok=True)
            raise
    
    def ingest_file(self, file_path: Path) -> Tuple[bool, str]:
        """Ingest a single session file.
        
        Args:
            file_path: Path to session file
            
        Returns:
            Tuple of (success, message)
        """
        # Compute hash for deduplication
        file_hash = self.compute_sha256(file_path)
        
        if file_hash in self.processed_hashes:
            return False, f"Duplicate file (hash: {file_hash[:8]}...)"
        
        # Validate JSON
        is_valid, data = self.validate_session_json(file_path)
        
        if not is_valid:
            # Quarantine bad JSON
            quarantine_file = self.quarantine_path / file_path.name
            shutil.copy2(file_path, quarantine_file)
            return False, f"Invalid JSON, quarantined to {quarantine_file}"
        
        # Get vault destination
        vault_dir = self.get_vault_path()
        vault_file = vault_dir / file_path.name
        
        # Atomic copy to vault
        try:
            self.atomic_copy(file_path, vault_file)
            
            # Also copy associated PDF if it exists
            pdf_name = file_path.stem + "_tabs.pdf"
            pdf_path = file_path.parent / pdf_name
            if pdf_path.exists():
                vault_pdf = vault_dir / pdf_name
                self.atomic_copy(pdf_path, vault_pdf)
            
            # Mark as processed
            self.processed_hashes.add(file_hash)
            
            return True, f"Ingested to {vault_file}"
        except Exception as e:
            return False, f"Error during ingestion: {e}"
    
    def ingest_inbox(self) -> dict:
        """Process all session files in inbox.
        
        Returns:
            Dictionary with ingestion statistics
        """
        stats = {
            'processed': 0,
            'duplicates': 0,
            'quarantined': 0,
            'errors': 0
        }
        
        # Find all session JSON files
        session_files = list(self.inbox_path.glob("*_session.json"))
        
        for file_path in session_files:
            success, message = self.ingest_file(file_path)
            
            if success:
                stats['processed'] += 1
                # Remove from inbox after successful ingestion
                file_path.unlink()
                
                # Remove associated PDF if exists
                pdf_path = file_path.parent / (file_path.stem + "_tabs.pdf")
                if pdf_path.exists():
                    pdf_path.unlink()
            else:
                if "Duplicate" in message:
                    stats['duplicates'] += 1
                    file_path.unlink()  # Remove duplicates
                elif "quarantined" in message:
                    stats['quarantined'] += 1
                    file_path.unlink()  # Remove from inbox
                else:
                    stats['errors'] += 1
        
        return stats
