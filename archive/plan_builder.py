import pandas as pd
from utils import read_excel_to_dataframe, filter_rows_by_value
from archive.aha_data_wrapper import AhaDataWrapper
from archive.rally_data_wrapper import RallyDataWrapper
from archive.mapping_rules_engine import MappingRuleEngine

DEFAULT_SOURCE_TYPE = "Excel"
PLAN_TEMPLATE_TAB_NAME = "template_projectPlan"

class Plan:
    """
    Incapsulate Plan and opertations on this data
    """

    def __init__(self, source_type=DEFAULT_SOURCE_TYPE):
        """
        Constructor method to initialize the attributes of the class.

        Parameters:
        source_type (str):  Type of the source for Aha Data
        """

        self.source_type = source_type
        self.df=None
        self.new_plan=None

            #to set up  default values for plan parameters, just for testing
        self.idea=None
        self.rally_theme=None
        self.project_type=None
        self.idea_name=None
        self.BDL = None
        self.RDL = None
        self.business_owner = None


        #to set up resources (just for now)
        self.file_path='GNP_Template_v4.xlsx'
        self.aha_file_path=self.file_path

    def load_plan_template(self, tab_name=PLAN_TEMPLATE_TAB_NAME):
        """
        Takes plan template  from the source and load into data frame

        Parameters:
        file_path (str): path to source.
        tab_name (str): Optional parameter specifying the tab name.

        Returns:
        None
        """
        if self.source_type=="Excel":
            self.df = read_excel_to_dataframe(self.file_path, tab_name)
            print(self.df)

    def build_plan(self):
        
        #update the new file name based on the user provided plan  parameters
        #Step #3 Update the File Name: Update the File Name on the project plan in cell A2. File Name will be "ST20101 - PCP Assignment Carry Over"
        self.set_up_file_name()

        #load aha data
        aha = AhaDataWrapper()
        aha.load_aha_data(self.file_path)  

        #load rally  data
        rally = RallyDataWrapper()
        rally.load_rally_data(self.file_path) 

        #filer aha by idea     
        aha.filter_aha_data_for_idea(self.idea)

        #filter rally by theme
        rally.filter_rally_data_for_theme(self.rally_theme)

        #apply rules
        eng = MappingRuleEngine()
        eng.apply_aha_mapping_rules(aha.df,self.df,self.file_path, self.BDL, self.RDL, self.business_owner,self.project_type)
        eng.apply_rally_mapping_rules(rally.df,self.file_path)
        self.new_plan=eng.df_new_plan

    


    def set_up_file_name(self):
        # Get the value of the first column in the first row
        first_value = self.df.iloc[0, 0]
        
        if not first_value=="File Name":
            print("WARNING: unexpected value where should be File Name placeholder. The found value:", first_value)

        # Replace the value with another value
        new_value = self.rally_theme + " - " + self.idea_name
        self.df.iloc[0, 0] = new_value
        




#https://uhgazure-my.sharepoint.com/:x:/r/personal/christopher_d_capewell_uhc_com/Documents/GNP%20Template%20-%20POC.xlsx?d=w59acbef77ed046a68e2ed206a56e7145&csf=1&web=1&e=d9Z5jY
