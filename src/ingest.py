"""Parse the AI Act HTML, embed chunks, and store in Qdrant."""
import argparse
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.config import (
    AI_ACT_URL, HTML_PATH, QDRANT_PATH,
    DEFAULT_EMBEDDER,
)
from src.parse import fetch_html, parse_all
from src.embedders import get_embedder


def ingest(embedder_name: str | None = None) -> None:
    embedder_name = embedder_name or DEFAULT_EMBEDDER

    print(f"Using embedder: {embedder_name}")
    print("Ensuring HTML is downloaded...")
    fetch_html(AI_ACT_URL, HTML_PATH)

    print("Parsing HTML into chunks...")
    chunks = parse_all(HTML_PATH)
    print(f"  {len(chunks)} chunks parsed")

    print("Loading embedder (may download model on first run)...")
    embedder = get_embedder(embedder_name)

    client = QdrantClient(path=str(QDRANT_PATH))

    # (Re-)create collection to ensure correct vector size
    existing = {c.name for c in client.get_collections().collections}
    if embedder.collection in existing:
        client.delete_collection(embedder.collection)

    client.create_collection(
        collection_name=embedder.collection,
        vectors_config=VectorParams(size=embedder.dim, distance=Distance.COSINE),
    )

    print("Embedding chunks...")
    texts = [c.text for c in chunks]
    vectors = []
    batch_size = 1
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors.extend(embedder.embed(batch))
        print(f"  {min(i + batch_size, len(texts))}/{len(texts)}")

    points = [
        PointStruct(
            id=i,
            vector=vectors[i],
            payload={
                "id": chunks[i].id,
                "type": chunks[i].type,
                "number": chunks[i].number,
                "title": chunks[i].title,
                "text": chunks[i].text,
            },
        )
        for i in range(len(chunks))
    ]

    client.upsert(collection_name=embedder.collection, points=points)
    print(f"Indexed {len(chunks)} chunks into '{embedder.collection}' using {embedder_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default=None, help="Embedder name (default from config)")
    args = parser.parse_args()
    ingest(args.embedder)
