import sqlalchemy
from HOwDI.model.HydrogenData import HydrogenData

c = sqlalchemy.create_engine(
    "sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite"
)

uuid = "7f1610e4-ddde-43bb-9b22-e09b5ce6975a"

h = HydrogenData(uuid=uuid, sql_database=c, read_type="sql", trial_number=714)

v = h.output_vector()


# from here, could do an outer merge to get a DataFrame with matched rows, filling na accordingly

pass
