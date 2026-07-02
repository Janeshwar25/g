import pandas as pd
from utils import read_excel_to_dataframe, filter_rows_by_value

THEME_REF_COLUMN_NAME = "Strategic Theme"
RALLY_TAB_NAME = "input_rallyData"
DEFAULT_SOURCE_TYPE = "Excel"

class RallyDataWrapper:
    """
    Incapsulate Rally Data and opertations on this data
    """

    def __init__(self, source_type=DEFAULT_SOURCE_TYPE):
        """
        Constructor method to initialize the attributes of the class.

        Parameters:
        source_type (str):  Type of the source for Rally Data
        """

        self.source_type = source_type
        self.df=None



    def load_rally_data(self, file_path:str,tab_name=RALLY_TAB_NAME):
        """
        Takes data from the source and load  into data frame

        Parameters:
        file_path (str): path to source.
        tab_name (str): Optional parameter specifying the tab name.

        Returns:
        None
        """
        if self.source_type=="Excel":
            self.df = read_excel_to_dataframe(file_path, tab_name)
            print(self.df)


    def filter_rally_data_for_theme(self, theme_ref:str):
        self.df=filter_rows_by_value(self.df,THEME_REF_COLUMN_NAME,theme_ref)
        print(self.df)