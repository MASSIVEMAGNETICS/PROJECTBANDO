#!/usr/bin/env python3
"""Example demonstration of VictorVault functionality."""

import json
import tempfile
import shutil
from pathlib import Path

def create_example_sessions(inbox_path: Path):
    """Create example session files for demonstration."""
    
    sessions = [
        {
            "filename": "20240107_120000_research_session.json",
            "data": {
                "tabs": [
                    {"title": "ArXiv: Machine Learning Papers", "url": "https://arxiv.org/list/cs.LG/recent"},
                    {"title": "Google Scholar", "url": "https://scholar.google.com"},
                    {"title": "Nature: AI Research", "url": "https://www.nature.com/subjects/machine-learning"}
                ]
            }
        },
        {
            "filename": "20240107_130000_coding_session.json",
            "data": {
                "tabs": [
                    {"title": "Python Documentation", "url": "https://docs.python.org/3/"},
                    {"title": "Stack Overflow - Python", "url": "https://stackoverflow.com/questions/tagged/python"},
                    {"title": "GitHub - pytorch/pytorch", "url": "https://github.com/pytorch/pytorch"},
                    {"title": "NumPy Documentation", "url": "https://numpy.org/doc/"}
                ]
            }
        },
        {
            "filename": "20240107_140000_shopping_session.json",
            "data": {
                "tabs": [
                    {"title": "Amazon", "url": "https://www.amazon.com"},
                    {"title": "Product Reviews", "url": "https://www.amazon.com/reviews"},
                ]
            }
        }
    ]
    
    for session in sessions:
        file_path = inbox_path / session['filename']
        with open(file_path, 'w') as f:
            json.dump(session['data'], f, indent=2)
        print(f"Created: {file_path}")


def main():
    """Run the demonstration."""
    print("=" * 70)
    print("VictorVault Demonstration")
    print("=" * 70)
    
    # Create demo directory
    demo_dir = Path("victorvault_demo")
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()
    
    inbox = demo_dir / "inbox"
    inbox.mkdir()
    
    print("\n1. Creating example session files in inbox...")
    print("-" * 70)
    create_example_sessions(inbox)
    
    print("\n2. Example session file content:")
    print("-" * 70)
    example_file = inbox / "20240107_120000_research_session.json"
    with open(example_file, 'r') as f:
        print(f.read())
    
    print("\n3. To process these files, run:")
    print("-" * 70)
    print("cd victorvault_demo")
    print("cat > config.json << 'EOF'")
    print(json.dumps({
        "base_path": ".",
        "inbox_dir": "inbox",
        "vault_dir": "vault",
        "quarantine_dir": "quarantine",
        "db_file": "victorvault.db",
        "checkpoint_file": "shard_checkpoint.npz"
    }, indent=2))
    print("EOF")
    print()
    print("python ../victorvault_cli.py ingest")
    
    print("\n4. Then search for sessions:")
    print("-" * 70)
    print("python ../victorvault_cli.py search 'Python'")
    print("python ../victorvault_cli.py search 'research'")
    
    print("\n5. Add mission prototypes for categorization:")
    print("-" * 70)
    print("python ../victorvault_cli.py add-mission research 'academic papers and scientific research'")
    print("python ../victorvault_cli.py add-mission development 'software development and programming'")
    
    print("\n6. Export co-occurrence graph:")
    print("-" * 70)
    print("python ../victorvault_cli.py export-graph --output graph.json")
    
    print("\n7. Add feedback for learning:")
    print("-" * 70)
    print("python ../victorvault_cli.py feedback 1 --score 0.95 --terms 'research,machine,learning'")
    
    print("\n" + "=" * 70)
    print("Demo directory created: victorvault_demo/")
    print("Follow the commands above to test the system!")
    print("=" * 70)


if __name__ == '__main__':
    main()
