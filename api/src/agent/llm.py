from src.core.config import config 
from llama_index.llms.google_genai import GoogleGenAI

llm_gemini = GoogleGenAI(model="gemini-2.0-flash", api_key=config.GOOGLE_API_KEY)