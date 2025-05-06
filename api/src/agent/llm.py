from src.core.config import config 
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.llms.openai import OpenAI

llm_gemini = GoogleGenAI(model="gemini-2.0-flash", api_key=config.GOOGLE_API_KEY)
llm_open= OpenAI(model="gpt-4o-mini", api_key=config.OPENAI_API_KEY)