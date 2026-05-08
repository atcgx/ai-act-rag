from src.config import OLLAMA_HOST, GEMINI_API_KEY, ANTHROPIC_API_KEY


class OllamaGenerator:
    name = "ollama-gemma2"
    data_sharing_ok = True

    def __init__(self, model: str = "gemma2:9b"):
        import ollama
        self._client = ollama.Client(host=OLLAMA_HOST)
        self._model = model

    def generate(self, system: str, user: str) -> str:
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.message.content


class OllamaGemma4Generator(OllamaGenerator):
    name = "ollama-gemma4"

    def __init__(self):
        super().__init__(model="gemma4:e4b")


class GeminiGenerator:
    name = "gemini-2.0-flash-lite"
    data_sharing_ok = False

    def __init__(self, model: str = "models/gemini-2.0-flash-lite"):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        from google import genai
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._model = model

    def generate(self, system: str, user: str) -> str:
        from google.genai import types
        response = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return response.text


class AnthropicGenerator:
    name = "claude-sonnet"
    data_sharing_ok = True

    def __init__(self, model: str = "claude-sonnet-4-5"):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        import anthropic
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._model = model

    def generate(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text


REGISTRY = {
    "ollama-gemma2": OllamaGenerator,
    "ollama-gemma4": OllamaGemma4Generator,
    "gemini-2.0-flash-lite": GeminiGenerator,
    "claude-sonnet": AnthropicGenerator,
}


def get_generator(name: str):
    if name not in REGISTRY:
        raise KeyError(f"Unknown generator '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]()
