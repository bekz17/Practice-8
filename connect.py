import psycopg2

from config import DB_CONFIG


def _connection_kwargs():
    cfg = dict(DB_CONFIG)
    if "database" in cfg and "dbname" not in cfg:
        cfg["dbname"] = cfg.pop("database")
    return cfg


def connect_db():
    """
    Open a PostgreSQL connection using DB_CONFIG.

    Returns a live connection on success; raises on failure so callers can handle errors.
    """
    try:
        conn = psycopg2.connect(**_connection_kwargs())
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        print("Database connection error:", e)
        raise
    except Exception as e:
        print("Unexpected error while connecting:", e)
        raise
