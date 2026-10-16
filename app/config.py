import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DB_URL"]
LLM_BASE_URL = os.environ.get("LLM_BASE_URL")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL")
