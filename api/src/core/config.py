from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

load_dotenv(verbose=True)

class Config(BaseSettings):
    REPO_DIRS: str = "/app/data"
    REPO_DIRS: str = Field(default="/app/data", env="REPO_DIRS")
    NEO4J_URI:str = Field(default="bolt://neo4j:7687", env="NEO4J_USERNAME")
    NEO4J_USERNAME: str = Field(default="neo4j", env="NEO4J_USERNAME")
    NEO4J_PASSWORD: str = Field(default="password", env="NEO4J_PASSWORD")
    REPO_LABEL:str = Field(default="Repository", env="REPO_LABEL")
    BRANCH_LABEL:str = Field(default="Branch", env="Branch_LABEL")
    COMMIT_LABEL:str = Field(default="Commit", env="Commit_LABEL")
    FOLDER_LABEL:str = Field(default="Folder", env="FOLDER_LABEL")
    FILE_LABEL:str = Field(default="File", env="FILE_LABEL")
    CLASS_LABEL:str = Field(default="Class", env="CLASS_LABEL")
    METHOD_LABEL:str = Field(default="Method", env="METHOD_LABEL")
    SCRIPT_LABEL:str = Field(default="Script", env="SCRIPT_LABEL")
    GOOGLE_API_KEY:str = Field(env="GOOGLE_API_KEY")
    OPENAI_API_KEY:str = Field(env="OPENAI_API_KEY")
    EMBED_MODL:str = Field(default="models/embedding-001", env="EMBED_MODL")

    APP_ENV: str = Field(default="dev", env="APP_ENV")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

config = Config()
