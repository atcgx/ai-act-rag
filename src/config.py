from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
HTML_PATH = DATA_DIR / "ai_act.html"
QDRANT_PATH = ROOT / "qdrant_data"

AI_ACT_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

DEFAULT_EMBEDDER = "local-bge-m3"
DEFAULT_GENERATOR = "ollama-gemma2"
TOP_K = 5
LOW_CONFIDENCE_THRESHOLD = 0.55
