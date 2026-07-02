import json
import pandas as pd
from utils import read_excel_to_dataframe, filter_rows_by_value
import os
import requests

THEME_REF_COLUMN_NAME = "Strategic Theme"
RALLY_TAB_NAME = "input_rallyData"
DEFAULT_SOURCE_TYPE = "Excel"


api_key = 'REDACTED_API_KEY'
rally_url = 'https://rally1.rallydev.com/slm/webservice/v2.0'

WORKSPACE = 'UHG'
PROJECT = 'Pioneers GenAI'

HEADERS = {
    'ZSESSIONID': api_key,
    'Content-Type': 'application/json'
}


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
        self.df = None

    def load_rally_data(self, file_path: str, tab_name=RALLY_TAB_NAME):
        """
        Takes data from the source and load  into data frame

        Parameters:
        file_path (str): ath to source.
        tab_name (str): Optional parameter specifying the tab name.

        Returns:
        None
        """
        if self.source_type == "Excel":
            self.df = read_excel_to_dataframe(file_path, tab_name)
            print(self.df)

    def filter_rally_data_for_theme(self, theme_ref: str):
        self.df = filter_rows_by_value(self.df, THEME_REF_COLUMN_NAME, theme_ref)
        print(self.df)

    def get_strategic_theme_ref(self, st_id):
        url = f"{rally_url}/PortfolioItem/StrategicTheme"
        params = {
            "query": f'(FormattedID = "{st_id}")',
            "fetch": "_ref,FormattedID,Workspace",
        }

        response = requests.get(url, headers=HEADERS, params=params).json()
        result = response["QueryResult"]["Results"]
        if result:
            return {"_ref": result[0]["_ref"], "FormattedID": result[0]["FormattedID"]}
        return None

    def get_solution_capabilities_by_strategic_theme_ref(self, ref_st):
        url = f"{rally_url}/PortfolioItem/SolutionCapability"
        params = {
            "query": f'(Parent = "{ref_st["_ref"]}")',
            "fetch": "_ref,FormattedID",
            "pageSize": 200,
        }

        response = requests.get(url, headers=HEADERS, params=params).json()
        result = response["QueryResult"]["Results"]
        return [{"_ref": capability["_ref"], "FormattedID": capability["FormattedID"]} for capability in
                result] if result else []

    def get_features_by_capability_ref(self, capability, strategic_theme_id):
        url = f"{rally_url}/PortfolioItem/Feature"
        params = {
            "query": f'(Parent = "{capability["_ref"]}")',
            'pagesize': 200,
            'fetch': 'FormattedID,Name,LeadTeam,ArtifactType,State,Release,ActualStartDate,ActualEndDate,Owner,'
                     'PreliminaryEstimate,PreliminaryEstimateCountValue,PreliminaryEstimateValue,PlannedStartDate,'
                     'PlannedEndDate,PercentDoneByStoryCount,PercentDoneByStoryPlanEstimate,LeafStoryPlanEstimateTotal,'
                     'Project,PolarisRelease,CapabilityManager'
        }

        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code == 200:
            data = response.json()
            result = data['QueryResult']['Results']
            features = []
            for feature in result:
                feature_details = {
                    'Concatenate': f"{feature.get('FormattedID', 'N/A')} - {feature.get('Name', 'N/A')}",
                    #'Lead Team': feature.get('LeadTeam', {}).get('_refObjectName', 'N/A'),
                    #'Artifact Type': feature.get('ArtifactType', 'N/A'),
                    #'Strategic Theme': strategic_theme_id,
                    #'Solution Capability': capability["FormattedID"],
                    #'Feature': feature.get('FormattedID', 'N/A'),
                    #'ID': feature.get('FormattedID', 'N/A'),
                    #'Name': feature.get('Name', 'N/A'),
                    #'State': feature.get('State', 'N/A'),
                    #'Polaris-Release': feature.get('PolarisRelease', 'N/A'),
                    #'Release': feature.get('Release', 'N/A'),
                    #'Actual Start Date': feature.get('ActualStartDate', 'N/A'),
                    #'Actual End Date': feature.get('ActualEndDate', 'N/A'),
                    #'Capability Manager': feature.get('CapabilityManager', {}).get('_refObjectName', 'N/A'),
                    #'Owner': feature.get('Owner', {}).get('_refObjectName', 'N/A'),
                    #'Preliminary Estimate': feature.get('PreliminaryEstimate', 'N/A'),
                    #'Preliminary Estimate Count Value': feature.get('PreliminaryEstimateCountValue', 'N/A'),
                    #'Preliminary Estimate Value': feature.get('PreliminaryEstimateValue', 'N/A'),
                    #'Planned Start Date': feature.get('PlannedStartDate', 'N/A'),
                    #'Planned End Date': feature.get('PlannedEndDate', 'N/A'),
                    #'% Done By Story Count': feature.get('PercentDoneByStoryCount', 'N/A'),
                    #'% Done By Story Plan Estimate': feature.get('PercentDoneByStoryPlanEstimate', 'N/A'),
                    #'Leaf Story Plan Estimate Total': feature.get('LeafStoryPlanEstimateTotal', 'N/A'),
                }
                features.append(feature_details)
            return features
        return []

    def get_features_by_strategic_theme(self, st_id):
        strategic_theme = self.get_strategic_theme_ref(st_id)
        if not strategic_theme:
            print(f"Strategic Theme {st_id} not found.")
            return

        solution_capabilities = self.get_solution_capabilities_by_strategic_theme_ref(strategic_theme)
        all_features = []

        for capability in solution_capabilities:
            features = self.get_features_by_capability_ref(capability, strategic_theme["FormattedID"])
            all_features.extend(features)

        self.df = pd.DataFrame(all_features)
        print(self.df)
        #self.df.to_csv('features.csv', index=False)
        print(f"Features exported successfully.")

    def get_projects_from_workspace(self, workspace_ref):
        url = f"{rally_url}/project"
        params = {
            "workspace": workspace_ref,
            "fetch": "Name,ObjectID,_ref",
            "pagesize": 200,
            "start": 1
        }

        all_projects = []

        while True:
            response = requests.get(url, headers=HEADERS, params=params).json()
            result = response["QueryResult"]["Results"]
            all_projects.extend(result)

            if response["QueryResult"]["TotalResultCount"] > params["start"] + len(result) - 1:
                params["start"] += len(result)
            else:
                break

        return all_projects

    def create_strategic_theme(self, workspace_ref, project_ref, name, description=""):
        url = f"{rally_url}/PortfolioItem/StrategicTheme/create"
        payload = {
            "PortfolioItem/StrategicTheme:": {
                "Name": name,
                "Description": description,
                "Workspace": workspace_ref,
                "Project": project_ref
            }
        }

        response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
        result = response.json()

        if response.status_code == 200 and "CreateResult" in result:
            created = result["CreateResult"]["Object"]
            print(f"Strategic Theme {name} created successfully.")
            return created
        else:
            print("Failed to create Strategic Theme: ")
            print(json.dumps(result, indent=2))
            return None

r = RallyDataWrapper()
st_id = 'ST20101'
ws_id = "https://rally1.rallydev.com/slm/webservice/v2.0/workspace/14457696030"
#r.get_features_by_strategic_theme(st_id)
ref = r.get_strategic_theme_ref(st_id)
cap = r.get_solution_capabilities_by_strategic_theme_ref(ref)
print(cap)
# projects = r.get_projects_from_workspace(ws_id)

### for strategic theme creation
# workspace_ref = 'https://rally1.rallydev.com/slm/webservice/v2.0/workspace/14457696030'
# project_ref = 'https://rally1.rallydev.com/slm/webservice/v2.0/project/627255414323'
# strategic_name = '[Auto-Generate] [Strategic Theme Test Creation]'
# r.create_strategic_theme(workspace_ref, project_ref, strategic_name)

