from src.config import GEMINI_API_KEY, VOYAGE_API_KEY


class LocalBgeEmbedder:
    name = "local-bge-m3"
    dim = 1024
    collection = "ai_act__local_bge_m3"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class GeminiEmbedder:
    name = "gemini-embedding"
    dim = 768
    collection = "ai_act__gemini_embedding"

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        from google import genai
        self._client = genai.Client(api_key=GEMINI_API_KEY)

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
        )
        return [e.values for e in result.embeddings]


class VoyageEmbedder:
    name = "voyage-lite"
    dim = 1024
    collection = "ai_act__voyage_lite"

    def __init__(self):
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY not set in environment")
        import voyageai
        self._client = voyageai.Client(api_key=VOYAGE_API_KEY)

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model="voyage-3.5-lite")
        return result.embeddings


REGISTRY = {
    "local-bge-m3": LocalBgeEmbedder,
    "gemini-embedding": GeminiEmbedder,
    "voyage-lite": VoyageEmbedder,
}


def get_embedder(name: str):
    if name not in REGISTRY:
        raise KeyError(f"Unknown embedder '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]()
