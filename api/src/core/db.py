import asyncio
from neo4j import AsyncGraphDatabase
from src.core.config import config

driver = AsyncGraphDatabase.driver(
    config.NEO4J_URI, 
    auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
)

def get_session():
    """
    Returns an asynchronous session from the global Neo4j driver.
    Usage example:
      async with get_session() as session:
          result = await session.run("MATCH (n) RETURN n LIMIT 1")
    """
    return driver.session()

async def close_driver():
    """Closes the global Neo4j driver."""
    await driver.close()

