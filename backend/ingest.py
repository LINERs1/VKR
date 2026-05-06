"""
CLI script to index course documents into ChromaDB.

Usage:
    python ingest.py                          # indexes ./data/course_docs
    python ingest.py --path ./my/docs/folder  # custom path
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.rag_service import ingest_documents


def main():
    parser = argparse.ArgumentParser(description="Ingest course documents into ChromaDB")
    parser.add_argument(
        "--path",
        default="./data/course_docs",
        help="Directory with course documents (PDF, DOCX, TXT, MD)",
    )
    args = parser.parse_args()

    print(f"📚 Indexing documents from: {args.path}")
    result = ingest_documents(args.path)

    if result["status"] == "success":
        print(f"✅ Done! Indexed {result['chunks']} chunks from {result['documents']} pages.")
    else:
        print(f"⚠️  {result.get('message', 'Unknown warning')}")


if __name__ == "__main__":
    main()
