import pandas as pd
from utils import read_excel_to_dataframe, filter_rows_by_value

IDEA_REF_COLUMN_NAME = "Idea reference"
AHA_TAB_NAME = "input_ahaData"
DEFAULT_SOURCE_TYPE = "Excel"

class AhaDataWrapper:
    """
    Incapsulate Aha Data and opertations on this data
    """

    def __init__(self, source_type=DEFAULT_SOURCE_TYPE):
        """
        Constructor method to initialize the attributes of the class.

        Parameters:
        source_type (str):  Type of the source for Aha Data
        """

        self.source_type = source_type
        self.df=None



    def load_aha_data(self, file_path:str,tab_name=AHA_TAB_NAME):
        """
        Takes data from the source and load  into data frame

        Parameters:
        file_path (str): ath to source.
        tab_name (str): Optional parameter specifying the tab name.

        Returns:
        None
        """
        if self.source_type=="Excel":
            self.df = read_excel_to_dataframe(file_path, tab_name)
            print(self.df)


    def filter_aha_data_for_idea(self, idea_ref:str):
        self.df=filter_rows_by_value(self.df,IDEA_REF_COLUMN_NAME,idea_ref)
        print(self.df)


