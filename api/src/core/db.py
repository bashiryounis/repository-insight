from src.core.config import config

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        from neo4j import AsyncGraphDatabase
        _driver = AsyncGraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
    return _driver

def get_session():
    return get_driver().session()

async def close_driver():
    global _driver
    if _driver:
        await _driver.close()
        _driver = None
