"""Command-line interface for VictorVault."""

import argparse
import json
import time
from pathlib import Path
from typing import Optional

from .ingestion import IngestEngine
from .index import VaultIndex
from .observer import VaultObserver


class VictorVaultCLI:
    """CLI for VictorVault operations."""
    
    def __init__(self, config_path: Path):
        """Initialize CLI with configuration.
        
        Args:
            config_path: Path to config.json
        """
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize paths
        base_path = Path(self.config.get('base_path', '.')).resolve()
        self.inbox_path = base_path / self.config.get('inbox_dir', 'inbox')
        self.vault_path = base_path / self.config.get('vault_dir', 'vault')
        self.quarantine_path = base_path / self.config.get('quarantine_dir', 'quarantine')
        self.db_path = base_path / self.config.get('db_file', 'victorvault.db')
        self.checkpoint_path = base_path / self.config.get('checkpoint_file', 'shard_checkpoint.npz')
        
        # Initialize components
        self.ingest_engine = IngestEngine(self.inbox_path, self.vault_path, self.quarantine_path)
        self.index = VaultIndex(self.db_path)
        self.observer = VaultObserver(self.index, self.checkpoint_path)
    
    def cmd_ingest(self, args):
        """Process files from inbox."""
        print(f"Ingesting files from {self.inbox_path}...")
        stats = self.ingest_engine.ingest_inbox()
        
        print(f"\nIngestion complete:")
        print(f"  Processed: {stats['processed']}")
        print(f"  Duplicates: {stats['duplicates']}")
        print(f"  Quarantined: {stats['quarantined']}")
        print(f"  Errors: {stats['errors']}")
        
        # Index newly ingested files
        if stats['processed'] > 0:
            print("\nIndexing processed files...")
            self._index_vault_files()
    
    def cmd_watch(self, args):
        """Watch inbox for new files and process them."""
        print(f"Watching {self.inbox_path} for new files...")
        print("Press Ctrl+C to stop.")
        
        interval = args.interval if hasattr(args, 'interval') else 5
        
        try:
            while True:
                session_files = list(self.inbox_path.glob("*_session.json"))
                if session_files:
                    print(f"\nFound {len(session_files)} files to process...")
                    self.cmd_ingest(args)
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nWatch stopped.")
    
    def cmd_search(self, args):
        """Search indexed sessions."""
        query = args.query
        limit = args.limit if hasattr(args, 'limit') else 10
        
        print(f"Searching for: {query}")
        results = self.index.search(query, limit)
        
        if not results:
            print("No results found.")
            return
        
        print(f"\nFound {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result['id']}] {result['title'] or 'Untitled'}")
            print(f"   URL: {result['url'] or 'N/A'}")
            print(f"   Tabs: {result['tab_count']}")
            print(f"   Ingested: {result['ingested_at']}")
            print(f"   Path: {result['file_path']}")
            print()
    
    def cmd_export_graph(self, args):
        """Export co-occurrence graph."""
        output_file = args.output if hasattr(args, 'output') else 'cooccurrence.json'
        
        print("Computing co-occurrence matrix...")
        cooccur = self.observer.compute_cooccurrence()
        
        # Convert to exportable format
        graph = {
            'nodes': list(cooccur.keys()),
            'edges': []
        }
        
        for url1, connections in cooccur.items():
            for url2, count in connections.items():
                graph['edges'].append({
                    'source': url1,
                    'target': url2,
                    'weight': count
                })
        
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(graph, f, indent=2)
        
        print(f"\nExported co-occurrence graph to {output_path}")
        print(f"  Nodes: {len(graph['nodes'])}")
        print(f"  Edges: {len(graph['edges'])}")
    
    def cmd_feedback(self, args):
        """Add feedback for a session."""
        session_id = args.session_id
        score = args.score if hasattr(args, 'score') else 1.0
        terms = args.terms.split(',') if hasattr(args, 'terms') and args.terms else []
        
        print(f"Adding feedback for session {session_id}...")
        self.observer.add_feedback(session_id, terms, score)
        print("Feedback recorded and checkpoint saved.")
    
    def cmd_add_mission(self, args):
        """Add a mission prototype."""
        mission_name = args.name
        description = args.description
        
        print(f"Adding mission prototype: {mission_name}")
        self.observer.add_mission_prototype(mission_name, description)
        print("Mission prototype added and checkpoint saved.")
    
    def _index_vault_files(self):
        """Index all files in vault that aren't already indexed."""
        vault_files = list(self.vault_path.rglob("*_session.json"))
        indexed_count = 0
        
        for file_path in vault_files:
            # Compute hash
            file_hash = self.ingest_engine.compute_sha256(file_path)
            
            # Skip if already indexed
            if self.index.hash_exists(file_hash):
                continue
            
            # Parse and index
            is_valid, data = self.ingest_engine.validate_session_json(file_path)
            if is_valid and data:
                self.index.add_session(file_path, file_hash, data)
                indexed_count += 1
        
        if indexed_count > 0:
            print(f"Indexed {indexed_count} new files.")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description='VictorVault - Local-first TabTimeMachine ingestion and observer')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Ingest command
    parser_ingest = subparsers.add_parser('ingest', help='Process files from inbox')
    
    # Watch command
    parser_watch = subparsers.add_parser('watch', help='Watch inbox for new files')
    parser_watch.add_argument('--interval', type=int, default=5, help='Check interval in seconds')
    
    # Search command
    parser_search = subparsers.add_parser('search', help='Search indexed sessions')
    parser_search.add_argument('query', help='Search query')
    parser_search.add_argument('--limit', type=int, default=10, help='Maximum results')
    
    # Export-graph command
    parser_export = subparsers.add_parser('export-graph', help='Export co-occurrence graph')
    parser_export.add_argument('--output', default='cooccurrence.json', help='Output file')
    
    # Feedback command
    parser_feedback = subparsers.add_parser('feedback', help='Add feedback for a session')
    parser_feedback.add_argument('session_id', type=int, help='Session ID')
    parser_feedback.add_argument('--score', type=float, default=1.0, help='Relevance score')
    parser_feedback.add_argument('--terms', help='Comma-separated relevant terms')
    
    # Add-mission command
    parser_mission = subparsers.add_parser('add-mission', help='Add mission prototype')
    parser_mission.add_argument('name', help='Mission name')
    parser_mission.add_argument('description', help='Mission description')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize CLI
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Run with a valid --config path or create config.json in current directory.")
        return
    
    cli = VictorVaultCLI(config_path)
    
    # Execute command
    if args.command == 'ingest':
        cli.cmd_ingest(args)
    elif args.command == 'watch':
        cli.cmd_watch(args)
    elif args.command == 'search':
        cli.cmd_search(args)
    elif args.command == 'export-graph':
        cli.cmd_export_graph(args)
    elif args.command == 'feedback':
        cli.cmd_feedback(args)
    elif args.command == 'add-mission':
        cli.cmd_add_mission(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
