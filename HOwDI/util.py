from pathlib import Path

import yaml
from sqlalchemy import create_engine


def read_yaml(fn):
    with open(fn) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def create_db_engine():
    p = Path(__file__) / ".."
    config = read_yaml(p / "config.yml")
    db = config.get("db")
    engine = create_engine(db)
    return engine
