"""Observer module using PortableShard for semantic analysis."""

from pathlib import Path
from typing import List, Dict, Any
import json

from .portable_asi import PortableShard
from .index import VaultIndex


class VaultObserver:
    """Observer for semantic analysis of vault sessions using PortableShard."""
    
    def __init__(self, index: VaultIndex, checkpoint_path: Path):
        """Initialize vault observer.
        
        Args:
            index: Vault index instance
            checkpoint_path: Path to PortableShard checkpoint
        """
        self.index = index
        self.checkpoint_path = checkpoint_path
        self.shard = PortableShard(checkpoint_path if checkpoint_path.exists() else None)
    
    def observe_session(self, session_id: int) -> Dict[str, Any]:
        """Observe and analyze a session.
        
        Args:
            session_id: Session ID to analyze
            
        Returns:
            Analysis results
        """
        session = self.index.get_session(session_id)
        if not session:
            return {'error': 'Session not found'}
        
        # Extract text for analysis
        text_parts = []
        session_data = session.get('session_data', {})
        
        if isinstance(session_data, dict):
            tabs = session_data.get('tabs', [])
            for tab in tabs:
                if isinstance(tab, dict):
                    if 'title' in tab:
                        text_parts.append(tab['title'])
                    if 'url' in tab:
                        text_parts.append(tab['url'])
        
        text = " ".join(text_parts)
        vec = self.shard.text_to_vec(text)
        
        # Rank against mission prototypes
        mission_similarities = {}
        if self.shard.mission_prototypes:
            for mission_name, mission_vec in self.shard.mission_prototypes.items():
                rankings = self.shard.rank_sim(mission_vec, [vec])
                if rankings:
                    mission_similarities[mission_name] = rankings[0][1]
        
        return {
            'session_id': session_id,
            'vector_size': len(vec),
            'mission_similarities': mission_similarities,
            'text_length': len(text)
        }
    
    def observe_all(self) -> List[Dict[str, Any]]:
        """Observe all sessions in the vault.
        
        Returns:
            List of analysis results
        """
        sessions = self.index.get_all_sessions()
        results = []
        
        for session in sessions:
            result = self.observe_session(session['id'])
            results.append(result)
        
        return results
    
    def add_feedback(self, session_id: int, relevant_terms: List[str], score: float):
        """Add feedback for a session.
        
        Args:
            session_id: Session ID
            relevant_terms: List of relevant terms
            score: Relevance score
        """
        feedback = {
            'session_id': session_id,
            'relevant_terms': relevant_terms,
            'score': score
        }
        self.shard.add_feedback(feedback)
        self.save_checkpoint()
    
    def add_mission_prototype(self, mission_name: str, description: str):
        """Add a mission prototype.
        
        Args:
            mission_name: Mission name
            description: Mission description
        """
        self.shard.add_mission_prototype(mission_name, description)
        self.save_checkpoint()
    
    def save_checkpoint(self):
        """Save PortableShard checkpoint."""
        self.shard.save_checkpoint(self.checkpoint_path)
    
    def compute_cooccurrence(self) -> Dict[str, Dict[str, int]]:
        """Compute co-occurrence matrix of URLs across sessions.
        
        Returns:
            Dictionary mapping URL -> {URL: count}
        """
        sessions = self.index.get_all_sessions()
        cooccur = {}
        
        for session in sessions:
            session_data = session.get('session_data', {})
            if isinstance(session_data, dict):
                urls = []
                tabs = session_data.get('tabs', [])
                for tab in tabs:
                    if isinstance(tab, dict) and 'url' in tab:
                        url = tab['url']
                        # Extract domain
                        if '://' in url:
                            domain = url.split('://')[1].split('/')[0]
                            urls.append(domain)
                
                # Build co-occurrence for this session
                for i, url1 in enumerate(urls):
                    if url1 not in cooccur:
                        cooccur[url1] = {}
                    for url2 in urls[i+1:]:
                        cooccur[url1][url2] = cooccur[url1].get(url2, 0) + 1
                        if url2 not in cooccur:
                            cooccur[url2] = {}
                        cooccur[url2][url1] = cooccur[url2].get(url1, 0) + 1
        
        return cooccur
