import sqlalchemy
from HOwDI.model.HydrogenData import HydrogenData

c = sqlalchemy.create_engine(
    "sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite"
)

uuid = "ae83c384-8da6-41e6-99a7-13732a7f520d"

h = HydrogenData(uuid=uuid, sql_database=c, read_type="sql", trial_number=1)

v = h.output_vector()


# from here, could do an outer merge to get a DataFrame with matched rows, filling na accordingly

pass
