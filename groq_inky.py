
from groq_db_functs import *


def get_all_inky_project_types():

    project_types = sql("""SELECT * FROM inky_project_types;""")

    return project_types

def get_all_inky_projects():

    projects = sql("""SELECT * FROM inky_projects;""")

    return projects