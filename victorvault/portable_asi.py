"""Portable ASI (Adaptive Semantic Index) module with text_to_vec and rank_sim."""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path


class PortableShard:
    """Portable shard for semantic text analysis with mission prototypes and feedback."""
    
    def __init__(self, checkpoint_path: Optional[Path] = None):
        """Initialize PortableShard with optional checkpoint.
        
        Args:
            checkpoint_path: Path to npz checkpoint file
        """
        self.mission_prototypes: Dict[str, np.ndarray] = {}
        self.feedback_history: List[Dict[str, Any]] = []
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        
        if checkpoint_path and checkpoint_path.exists():
            self.load_checkpoint(checkpoint_path)
    
    def text_to_vec(self, text: str) -> np.ndarray:
        """Convert text to vector representation using TF-IDF-like approach.
        
        Args:
            text: Input text
            
        Returns:
            numpy array vector representation
        """
        # Simple tokenization
        tokens = text.lower().split()
        
        # Update vocabulary
        for token in tokens:
            if token not in self.vocab:
                self.vocab[token] = len(self.vocab)
        
        # Create vector
        vec = np.zeros(len(self.vocab))
        token_counts = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        
        # TF-IDF weighting
        for token, count in token_counts.items():
            idx = self.vocab[token]
            tf = count / len(tokens) if tokens else 0
            idf = self.idf.get(token, 1.0)
            vec[idx] = tf * idf
        
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        
        return vec
    
    def rank_sim(self, query_vec: np.ndarray, document_vecs: List[np.ndarray]) -> List[Tuple[int, float]]:
        """Rank documents by similarity to query vector.
        
        Args:
            query_vec: Query vector
            document_vecs: List of document vectors
            
        Returns:
            List of (index, similarity_score) tuples, sorted by score descending
        """
        scores = []
        for idx, doc_vec in enumerate(document_vecs):
            # Ensure vectors are same length by padding with zeros
            max_len = max(len(query_vec), len(doc_vec))
            q = np.zeros(max_len)
            d = np.zeros(max_len)
            q[:len(query_vec)] = query_vec
            d[:len(doc_vec)] = doc_vec
            
            # Cosine similarity
            q_norm = np.linalg.norm(q)
            d_norm = np.linalg.norm(d)
            if q_norm > 0 and d_norm > 0:
                sim = np.dot(q, d) / (q_norm * d_norm)
            else:
                sim = 0.0
            scores.append((idx, float(sim)))
        
        return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def add_mission_prototype(self, mission_name: str, text: str):
        """Add a mission prototype vector.
        
        Args:
            mission_name: Name of the mission
            text: Mission description text
        """
        self.mission_prototypes[mission_name] = self.text_to_vec(text)
    
    def add_feedback(self, feedback: Dict[str, Any]):
        """Record user feedback for learning.
        
        Args:
            feedback: Feedback dictionary with relevance signals
        """
        self.feedback_history.append(feedback)
        
        # Update IDF based on feedback
        if 'relevant_terms' in feedback:
            for term in feedback['relevant_terms']:
                if term in self.vocab:
                    self.idf[term] = self.idf.get(term, 1.0) * 1.1
    
    def save_checkpoint(self, checkpoint_path: Path):
        """Save checkpoint to npz file.
        
        Args:
            checkpoint_path: Path to save checkpoint
        """
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data
        data = {
            'vocab': json.dumps(self.vocab),
            'idf': json.dumps(self.idf),
            'feedback_history': json.dumps(self.feedback_history),
        }
        
        # Add mission prototypes
        for name, vec in self.mission_prototypes.items():
            data[f'mission_{name}'] = vec
        
        np.savez(checkpoint_path, **data)
    
    def load_checkpoint(self, checkpoint_path: Path):
        """Load checkpoint from npz file.
        
        Args:
            checkpoint_path: Path to checkpoint file
        """
        data = np.load(checkpoint_path, allow_pickle=True)
        
        self.vocab = json.loads(str(data['vocab']))
        self.idf = json.loads(str(data['idf']))
        self.feedback_history = json.loads(str(data['feedback_history']))
        
        # Load mission prototypes
        for key in data.keys():
            if key.startswith('mission_'):
                mission_name = key[8:]  # Remove 'mission_' prefix
                self.mission_prototypes[mission_name] = data[key]
