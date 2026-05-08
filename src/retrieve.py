from qdrant_client import QdrantClient

from src.config import QDRANT_PATH
from src.parse import Chunk


def retrieve(query: str, embedder, top_k: int = 5) -> list[tuple[Chunk, float]]:
    """Embed query and return (Chunk, score) tuples from Qdrant."""
    client = QdrantClient(path=str(QDRANT_PATH))
    vector = embedder.embed([query])[0]

    results = client.query_points(
        collection_name=embedder.collection,
        query=vector,
        limit=top_k,
        with_payload=True,
    ).points

    chunks = []
    for hit in results:
        p = hit.payload
        chunk = Chunk(
            id=p["id"],
            type=p["type"],
            number=p["number"],
            title=p["title"],
            text=p["text"],
        )
        chunks.append((chunk, hit.score))
    return chunks
