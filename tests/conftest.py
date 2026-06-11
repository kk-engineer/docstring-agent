from pathlib import Path

from src.config import AppConfig, Config, DocstringGenConfig, LLMConfig
from src.logger import Logger

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_NO_DOCS = FIXTURES_DIR / "sample_no_docs.py"
SAMPLE_WITH_DOCS = FIXTURES_DIR / "sample_with_docs.py"
SAMPLE_COMPLEX = FIXTURES_DIR / "sample_complex.py"

# Initialize logger once at import time for all tests
try:
    Logger.get_instance()
except RuntimeError:
    cfg = Config(
        app=AppConfig(name="test", version="0.1.0", log_level="CRITICAL"),
        llm=LLMConfig(
            provider="test", model="test", base_url="http://localhost",
        ),
        docstring_gen=DocstringGenConfig(),
    )
    Logger.get_instance(cfg)
