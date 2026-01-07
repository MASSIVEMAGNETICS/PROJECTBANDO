#!/usr/bin/env python3
"""Smoke test for VictorVault functionality."""

import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from victorvault.ingestion import IngestEngine
from victorvault.index import VaultIndex
from victorvault.observer import VaultObserver
from victorvault.portable_asi import PortableShard


def test_portable_asi():
    """Test PortableShard functionality."""
    print("Testing PortableShard...")
    
    shard = PortableShard()
    
    # Test text_to_vec
    vec1 = shard.text_to_vec("machine learning python programming")
    vec2 = shard.text_to_vec("python data science")
    vec3 = shard.text_to_vec("javascript web development")
    
    assert len(vec1) > 0, "Vector should not be empty"
    assert len(vec2) > 0, "Vector should not be empty"
    
    # Test rank_sim
    rankings = shard.rank_sim(vec1, [vec1, vec2, vec3])
    assert rankings[0][1] == 1.0, "Self-similarity should be 1.0"
    assert rankings[1][1] > rankings[2][1], "Python docs should be more similar than JS"
    
    # Test mission prototype
    shard.add_mission_prototype("coding", "software development programming")
    assert "coding" in shard.mission_prototypes
    
    # Test feedback
    shard.add_feedback({"relevant_terms": ["python", "machine"], "score": 0.9})
    assert len(shard.feedback_history) == 1
    
    print("✓ PortableShard tests passed")


def test_ingestion():
    """Test ingestion functionality."""
    print("\nTesting Ingestion...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        inbox = tmppath / "inbox"
        vault = tmppath / "vault"
        quarantine = tmppath / "quarantine"
        
        inbox.mkdir()
        
        # Create test session file
        session_data = {
            "tabs": [
                {"title": "GitHub", "url": "https://github.com"},
                {"title": "Python Docs", "url": "https://docs.python.org"}
            ]
        }
        
        session_file = inbox / "test_session.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        
        # Create bad JSON file
        bad_file = inbox / "bad_session.json"
        with open(bad_file, 'w') as f:
            f.write("{invalid json")
        
        # Test ingestion
        engine = IngestEngine(inbox, vault, quarantine)
        
        # Test single file ingestion
        success, message = engine.ingest_file(session_file)
        assert success, f"Ingestion should succeed: {message}"
        
        # Verify vault structure
        vault_files = list(vault.rglob("*_session.json"))
        assert len(vault_files) == 1, "Should have one file in vault"
        
        # Test duplicate detection
        session_file2 = inbox / "duplicate_session.json"
        shutil.copy(vault_files[0], session_file2)
        success, message = engine.ingest_file(session_file2)
        assert not success, "Duplicate should be rejected"
        assert "Duplicate" in message
        
        # Test bad JSON quarantine
        success, message = engine.ingest_file(bad_file)
        assert not success, "Bad JSON should fail"
        assert "quarantined" in message.lower()
        
        quarantine_files = list(quarantine.glob("*.json"))
        assert len(quarantine_files) == 1, "Bad file should be in quarantine"
        
        print("✓ Ingestion tests passed")


def test_index():
    """Test SQLite index functionality."""
    print("\nTesting SQLite Index...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        index = VaultIndex(db_path)
        
        # Test adding session
        session_data = {
            "tabs": [
                {"title": "Python Tutorial", "url": "https://python.org/tutorial"},
                {"title": "NumPy Docs", "url": "https://numpy.org/doc"}
            ]
        }
        
        session_id = index.add_session(
            Path("/vault/2024/01/01/test_session.json"),
            "abc123hash",
            session_data
        )
        
        assert session_id > 0, "Should return valid session ID"
        
        # Test hash checking
        assert index.hash_exists("abc123hash"), "Hash should exist"
        assert not index.hash_exists("nonexistent"), "Nonexistent hash should return False"
        
        # Test search
        results = index.search("Python")
        assert len(results) > 0, "Should find Python-related session"
        assert results[0]['id'] == session_id
        
        results = index.search("JavaScript")
        assert len(results) == 0, "Should not find JavaScript"
        
        # Test get_session
        session = index.get_session(session_id)
        assert session is not None
        assert session['tab_count'] == 2
        assert session['title'] == "Python Tutorial"
        
        print("✓ Index tests passed")


def test_observer():
    """Test observer functionality."""
    print("\nTesting Observer...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        db_path = tmppath / "test.db"
        checkpoint_path = tmppath / "checkpoint.npz"
        
        index = VaultIndex(db_path)
        observer = VaultObserver(index, checkpoint_path)
        
        # Add mission prototype
        observer.add_mission_prototype("research", "academic papers scientific research")
        
        # Add test session
        session_data = {
            "tabs": [
                {"title": "Research Paper on ML", "url": "https://arxiv.org/paper123"},
                {"title": "Scientific Journal", "url": "https://nature.com/article"}
            ]
        }
        
        session_id = index.add_session(
            Path("/vault/2024/01/01/research_session.json"),
            "research_hash",
            session_data
        )
        
        # Observe session
        result = observer.observe_session(session_id)
        assert 'session_id' in result
        assert 'mission_similarities' in result
        assert 'research' in result['mission_similarities']
        
        # Add feedback
        observer.add_feedback(session_id, ["research", "machine", "learning"], 0.95)
        
        # Test checkpoint save/load
        assert checkpoint_path.exists(), "Checkpoint should be saved"
        
        # Load checkpoint
        observer2 = VaultObserver(index, checkpoint_path)
        assert "research" in observer2.shard.mission_prototypes
        assert len(observer2.shard.feedback_history) > 0
        
        # Test co-occurrence
        session_data2 = {
            "tabs": [
                {"title": "GitHub", "url": "https://github.com/user/repo"},
                {"title": "ArXiv", "url": "https://arxiv.org/paper456"}
            ]
        }
        index.add_session(
            Path("/vault/2024/01/01/mixed_session.json"),
            "mixed_hash",
            session_data2
        )
        
        cooccur = observer.compute_cooccurrence()
        assert len(cooccur) > 0, "Should have co-occurrence data"
        
        print("✓ Observer tests passed")


def test_integration():
    """Test full integration workflow."""
    print("\nTesting Full Integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        inbox = tmppath / "inbox"
        vault = tmppath / "vault"
        quarantine = tmppath / "quarantine"
        db_path = tmppath / "victorvault.db"
        checkpoint_path = tmppath / "checkpoint.npz"
        
        inbox.mkdir()
        
        # Create multiple test sessions
        sessions = [
            {
                "name": "coding_session.json",
                "data": {
                    "tabs": [
                        {"title": "Python Docs", "url": "https://docs.python.org"},
                        {"title": "Stack Overflow", "url": "https://stackoverflow.com/questions/python"}
                    ]
                }
            },
            {
                "name": "research_session.json",
                "data": {
                    "tabs": [
                        {"title": "ArXiv Paper", "url": "https://arxiv.org/abs/2024.12345"},
                        {"title": "Google Scholar", "url": "https://scholar.google.com"}
                    ]
                }
            }
        ]
        
        for session in sessions:
            file_path = inbox / session['name']
            with open(file_path, 'w') as f:
                json.dump(session['data'], f)
        
        # Initialize components
        engine = IngestEngine(inbox, vault, quarantine)
        index = VaultIndex(db_path)
        observer = VaultObserver(index, checkpoint_path)
        
        # Ingest all files
        stats = engine.ingest_inbox()
        assert stats['processed'] == 2, f"Should process 2 files, got {stats['processed']}"
        
        # Index vault files
        vault_files = list(vault.rglob("*_session.json"))
        for vault_file in vault_files:
            file_hash = engine.compute_sha256(vault_file)
            is_valid, data = engine.validate_session_json(vault_file)
            if is_valid and data:
                index.add_session(vault_file, file_hash, data)
        
        # Search
        results = index.search("Python")
        assert len(results) > 0, "Should find Python session"
        
        results = index.search("ArXiv")
        assert len(results) > 0, "Should find research session"
        
        # Add mission and observe
        observer.add_mission_prototype("development", "coding programming software")
        observer.add_mission_prototype("academic", "research papers science")
        
        all_sessions = index.get_all_sessions()
        assert len(all_sessions) == 2, "Should have 2 sessions indexed"
        
        for session in all_sessions:
            analysis = observer.observe_session(session['id'])
            assert 'mission_similarities' in analysis
        
        # Export co-occurrence
        cooccur = observer.compute_cooccurrence()
        assert len(cooccur) > 0, "Should have co-occurrence data"
        
        print("✓ Integration tests passed")


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("VictorVault Smoke Tests")
    print("=" * 60)
    
    try:
        test_portable_asi()
        test_ingestion()
        test_index()
        test_observer()
        test_integration()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
