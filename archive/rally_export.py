import json
import pandas as pd
from utils import read_excel_to_dataframe, filter_rows_by_value
import os
import requests

api_key = 'REDACTED_API_KEY'
rally_url = 'https://rally1.rallydev.com/slm/webservice/v2.0'

WORKSPACE = 'UHG'
PROJECT = 'Pioneers GenAI'

HEADERS = {
    'ZSESSIONID': api_key,
    'Content-Type': 'application/json'
}

def get_strategic_theme_ref(st_id):
        url = f"{rally_url}/PortfolioItem/StrategicTheme"
        params = {
            "query": f'(FormattedID = "{st_id}")',
            "fetch": "_ref,FormattedID,Workspace",
        }

        response = requests.get(url, headers=HEADERS, params=params).json()
        result = response["QueryResult"]["Results"]
        if result:
            return result[0]["_ref"]
        return None

def get_features_by_capability_ref(capability):
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
                'Lead Team': feature.get('c_LeadTeam', None), #.get('_refObjectName', None),
                'Artifact Type': 'Feature',
                'Solution Capability': capability["FormattedID"],
                'Feature': feature.get('FormattedID', None),
                'ID': feature.get('FormattedID', None),
                'State': (feature.get('State', {}) or {}).get('_refObjectName', None),
                'Owner': feature.get('Owner', None).get('_refObjectName', None),
                '% Done By Story Plan Estimate': feature.get('PercentDoneByStoryPlanEstimate', None),
                'Preliminary Estimate Value': feature.get('PreliminaryEstimateValue', None),
                'Name': feature.get('Name', 'N/A'),
            }
            features.append(feature_details)
        return features
    return []

def get_rally_data(rally_st):
    ref_st = get_strategic_theme_ref(rally_st)
    url = f"{rally_url}/PortfolioItem/SolutionCapability"
    params = {
        "query": f'(Parent = "{ref_st}")',
        "fetch": "_ref,FormattedID,LeadTeam,ArtifactType,State,PercentDoneByStoryPlanEstimate,PreliminaryEstimateValue,Name,Owner",
        "pageSize": 200,
    }

    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code == 200:
        data = response.json()
        result = data['QueryResult']['Results']
        rows = []
        for c in result:
            print(c)
            cap_details = {
                'Lead Team': c.get('c_LeadTeam', None), #.get('_refObjectName', None),
                'Artifact Type': 'Solution Capability',
                'Solution Capability': c["FormattedID"],
                'Feature': None,
                'ID': c.get('FormattedID', None),
                'State': (c.get('State', {}) or {}).get('_refObjectName', None),
                'Owner': c.get('Owner', {}).get('_refObjectName', None),
                '% Done By Story Plan Estimate': c.get('PercentDoneByStoryPlanEstimate', None),
                'Preliminary Estimate Value': c.get('PreliminaryEstimateValue', None),
                'Name': c.get('Name', None),
            }
            rows.append(cap_details)
            features = get_features_by_capability_ref(c)
            if len(features) > 0:
                 rows.extend(features)
        df = pd.DataFrame(rows)
        print(df)
        return df
    return []

st = 'ST15926'

get_rally_data(st)