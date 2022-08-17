from HOwDI.model.HydrogenData import HydrogenData

import sqlalchemy

c = sqlalchemy.create_engine(
    "sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite"
)

uuid = "65ff619c-ff90-4c42-8da9-9cb48fca11b7"

h = HydrogenData(uuid=uuid, sql_database=c, read_type="sql", trial_number=1)

pass
