import logging
from src.core.config import config

logger = logging.getLogger(__name__)

# ---------------------------------#
#   Setup index for LlamaIndex     #
# ---------------------------------#
def get_vector_store(
        index_name: str,
        label: str, 
        embedd_property: str, 
        text_property: str = "text",
        dim: int = 1536,
    ):
    from llama_index.vector_stores.neo4jvector import Neo4jVectorStore

    return Neo4jVectorStore(
        url=config.NEO4J_URI,
        username=config.NEO4J_USERNAME,
        password=config.NEO4J_PASSWORD,
        index_name=index_name,
        node_label=label,
        embedding_node_property=f"{embedd_property}",  
        text_node_property=f"{text_property}", 
        embedding_dimension=dim,
        distance_strategy="cosine",
        embedding_model=Settings.embed_model,
    )

_vector_store_cache = {}

def get_index_for_label_field(label: str, field: str = None):
    from llama_index.vector_stores.neo4jvector import Neo4jVectorStore
    key = f"{label}:{field}"
    if key in _vector_store_cache:
        return _vector_store_cache[key]

    index_name = f"{label.lower()}_{field}_index"
    embed_property = f"embedding_{field}"

    store = get_vector_store(index_name, label, embed_property, field)
    _vector_store_cache[key] = store
    return store



# ---------------------------------#
#   Setup index  Manually          #
# ---------------------------------#

async def create_vector_indexes_if_missing(
    session,
    index_config: dict,
    default_dim: int = 384,
    default_distance: str = "cosine"
):
    """
    Create vector indexes in Neo4j if missing.

    Supports simple strings (for default settings) or dicts (for custom dim/distance):
        "File": [
            "content",
            {"summary": {"dim": 768}},
            {"description": {"distance": "euclidean"}}
        ]

    :param session: Neo4j session
    :param index_config: Dict[str, List[Union[str, Dict[str, Dict]]]]
    :param default_dim: Default dimension size
    :param default_distance: Default distance metric
    """
    # Fetch existing index names
    result = await session.run("""
        SHOW VECTOR INDEXES 
        YIELD name, type
        RETURN name, type
    """)
    existing_indexes = {
        record["name"]
        async for record in result
        if record["type"] == "VECTOR"
    }

    for label, prop_entries in index_config.items():
        for entry in prop_entries:
            if isinstance(entry, str):
                prop = f"embedding_{entry}"
                dim = default_dim
                distance = default_distance
            elif isinstance(entry, dict):
                name, opts = next(iter(entry.items()))
                prop = f"embedding_{name}"
                dim = opts.get("dim", default_dim)
                distance = opts.get("distance", default_distance)
            else:
                raise ValueError(f"Invalid property entry: {entry}")

            index_name = f"{label.lower()}_{prop}_index"

            if index_name in existing_indexes:
                logger.debug(f"[Index Exists] {index_name} — Skipping")
                continue

            logger.info(f"[Creating Index] {index_name} (dim={dim}, distance={distance})")
            await session.run(f"""
                CALL db.index.vector.createNodeIndex('{index_name}', '{label}', '{prop}', {dim}, '{distance}')
            """)


async def setup_all_indexes():
    from src.core.db import get_session

    index_config = {
        config.REPO_LABEL: ["content"],
        config.FOLDER_LABEL: [
            "name",
            "content"
        ],
        config.BRANCH_LABEL: [
            "content",
        ],
        config.COMMIT_LABEL: [
            "content",

        ],
        config.FILE_LABEL: [
            "name",
            "content",
            "description",
            {"summary": {"dim": 384}},
        ],
        config.CLASS_LABEL: [
            "name",
            "content",
            "docstring",
            "description"
        ],
        config.METHOD_LABEL: [
            "name",
            "content",
            "docstring",
            "description"
        ],
        config.SCRIPT_LABEL: [
            "name",
            "description",
            "content"
        ]
    }

    async with get_session() as session:
        await create_vector_indexes_if_missing(session, index_config)
