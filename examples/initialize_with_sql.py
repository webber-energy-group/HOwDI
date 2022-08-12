from HOwDI.model.HydrogenData import HydrogenData

import sqlalchemy

c = sqlalchemy.create_engine(
    "sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite"
)

uuid = "0e9be8a1-7619-4487-9041-8cffe1040f57"

h = HydrogenData(uuid=uuid, sql_database=c, read_type="sql", trial_number=1)
