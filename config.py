import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DB_SERVER = _required_env("AZURE_DB_SERVER")
DB_PORT = int(os.getenv("AZURE_DB_PORT", "1433"))
DB_NAME = _required_env("AZURE_DB_NAME")
DB_USER = _required_env("AZURE_DB_USER")
DB_PASSWORD = _required_env("AZURE_DB_PASSWORD")
DB_CONNECTION_STRING = URL.create(
    "mssql+pymssql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_SERVER,
    port=DB_PORT,
    database=DB_NAME,
).render_as_string(hide_password=False)

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_BASE = os.getenv("AZURE_OPENAI_API_BASE")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

TARGET_QB_ID = 366033
RTU_CUSTOMER_ID = 310
LOGICBOX_QB_IDENTIFIERS = ["logicbox", "LogicBox", "Logic Box", "logic box", "LB_", "_LB"]
