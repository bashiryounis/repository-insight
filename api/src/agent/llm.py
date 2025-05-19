from src.core.config import config 

def get_llm_gemini(pro:bool = False):
    from llama_index.llms.google_genai import GoogleGenAI
    if pro : 
        GoogleGenAI(model="gemini-1.5-pro", api_key=config.GOOGLE_API_KEY)
    return GoogleGenAI(model="gemini-2.0-flash", api_key=config.GOOGLE_API_KEY)
def get_llm_openai():
    from llama_index.llms.openai import OpenAI
    return OpenAI(model="gpt-4o-mini", api_key=config.OPENAI_API_KEY)