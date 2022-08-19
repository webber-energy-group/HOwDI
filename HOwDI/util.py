import json
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


def get_metadata(uuid, engine=None):
    if engine is None:
        engine = create_db_engine()

    with engine.connect() as con:
        metadata = con.execute(
            f"""SELECT metadata FROM metadata WHERE uuid = '{uuid}'"""
        )
        metadata = [r for r in metadata][0][0]

    metadata = json.loads(metadata)
    return metadata


def get_number_of_trials(uuid, engine=None):
    metadata = get_metadata(uuid=uuid, engine=engine)
    return metadata["metadata"]["number_of_trials"]
