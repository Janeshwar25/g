from utils import read_excel_to_dataframe
import pandas as pd
import numpy as np
import requests
import certifi
import os
from dotenv import load_dotenv
import pprint

load_dotenv(dotenv_path='credentials.env')

api_key = os.getenv('RALLY_API_KEY')
rally_url = os.getenv('RALLY_URL')
aha_token = os.getenv('AHA_API_KEY')
api_key_chris = 'REDACTED_API_KEY'

# --------------------------------- API CREDENTIALS ----------------------------------

# api_key = 'REDACTED_API_KEY'
# rally_url = 'https://rally1.rallydev.com/slm/webservice/v2.0'

WORKSPACE = 'UHG'
PROJECT = 'Pioneers GenAI'

HEADERS = {
    'ZSESSIONID': api_key_chris,
    'Content-Type': 'application/json'


}

# --------------------------------- RALLY EXPORT HELPER FUNCTIONS ----------------------------------

# def get_strategic_theme_ref(st_id):
#         """
#         Retrives the unique Rally API URL that can be used to retrieve capability and feature information.
#         """
#         # defines the parameters for the Rally API call
#         url = f"{rally_url}/PortfolioItem/StrategicTheme"
#         params = {
#             "query": f'(FormattedID = "{st_id}")',
#             "fetch": "_ref,FormattedID,Workspace,ObjectID",
#         }

#         # returns the Rally url that is needed to find ST details
#         response = requests.get(url, headers=HEADERS, params=params).json()

#         result = response["QueryResult"]["Results"]
#         obj_id = result[0]['ObjectID']
#         if result:
#             return result[0]["_ref"], obj_id
#         return None

# # print(get_strategic_theme_ref("ST19890"))

# def get_features_by_capability_ref(capability):
#     """
#     Retrieves all feature details given a capability.
#     """
#     # defines the parameters for the Rally API call
#     url = f"{rally_url}/PortfolioItem/Feature"
#     params = {
#         "query": f'(Parent = "{capability["_ref"]}")',
#         'pagesize': 200,
#         'fetch': 'FormattedID,Name,LeadTeam,ArtifactType,State,Release,ActualStartDate,ActualEndDate,Owner,'
#                  'PreliminaryEstimate,PreliminaryEstimateCountValue,PreliminaryEstimateValue,PlannedStartDate,'
#                  'PlannedEndDate,PercentDoneByStoryCount,PercentDoneByStoryPlanEstimate,LeafStoryPlanEstimateTotal,'
#                  'Project,PolarisRelease,CapabilityManager'
#     }

#     response = requests.get(url, headers=HEADERS, params=params)

#     # returns the specific columns of data for each feature based on a given capability
#     if response.status_code == 200:
#         data = response.json()
#         result = data['QueryResult']['Results']
#         features = []
#         for feature in result:
#             feature_details = {
#                 'Lead Team': feature.get('c_LeadTeam', None),
#                 'Release': (feature.get('Release', {}) or {}).get('_refObjectName', None),
#                 'Artifact Type': 'Feature',
#                 'Solution Capability': capability["FormattedID"],
#                 'Feature': feature.get('FormattedID', None),
#                 'ID': feature.get('FormattedID', None),
#                 'State': (feature.get('State', {}) or {}).get('_refObjectName', None),
#                 'Owner': (feature.get('Owner', {}) or {}).get('_refObjectName', None),
#                 'PED': feature.get('PlannedEndDate', None),
#                 '% Done By Story Plan Estimate': feature.get('PercentDoneByStoryPlanEstimate', None),
#                 'Preliminary Estimate Value': feature.get('PreliminaryEstimateValue', None),
#                 'Name': feature.get('Name', 'N/A'),
#             }
#             features.append(feature_details)
#         return features
#     return []

# def live_rally_data(rally_st):
#     """
#     Retrieves all capability details given an ST.
#     """
#     # defines the parameters for the Rally API call
#     ref_st, obj_id = get_strategic_theme_ref(rally_st)
#     # print("REF ST", ref_st, "OBJ ID", obj_id)
#     url = f"{rally_url}/PortfolioItem/SolutionCapability"
#     params = {
#         "query": f'(Parent = "{ref_st}")',
#         "fetch": "_ref,FormattedID,LeadTeam,ArtifactType,State,PercentDoneByStoryPlanEstimate,PreliminaryEstimateValue,Name,Owner,PlannedEndDate",
#         "pageSize": 200,
#         "projectScopeDown": "true",
#         "projectScopeUp": "true"
#     }

#     response = requests.get(url, headers=HEADERS, params=params)

#     # returns a list of all capabilities and the specified columns given a ST
#     if response.status_code == 200:
#         data = response.json()
#         # pprint.pprint(data)
#         # print(len(data['QueryResult']['Results']))
#         # for i in data['QueryResult']['Results']:
#         #     print(i['Name'])
#         result = data['QueryResult']['Results']
#         rows = []
#         for c in result:
#             cap_details = {
#                 'Lead Team': c.get('c_LeadTeam', None),
#                 'Release': None,
#                 'Artifact Type': 'Solution Capability',
#                 'Solution Capability': c["FormattedID"],
#                 'Feature': None,
#                 'ID': c.get('FormattedID', None),
#                 'State': (c.get('State', {}) or {}).get('_refObjectName', None),
#                 'Owner': (c.get('Owner', {}) or {}).get('_refObjectName', None),
#                 'PED': c.get('PlannedEndDate', None),
#                 '% Done By Story Plan Estimate': c.get('PercentDoneByStoryPlanEstimate', None),
#                 'Preliminary Estimate Value': c.get('PreliminaryEstimateValue', None),
#                 'Name': c.get('Name', None),
#             }
#             rows.append(cap_details)

#             # calling the get features function to retreive the features for each capabilitiy
#             features = get_features_by_capability_ref(c)
#             if len(features) > 0:
#                  rows.extend(features)

#         # creating a dataframe with the features and capabilities
#         df = pd.DataFrame(rows)

#         # dropping tasks with a Will Not Implement Status
#         df = df[df['State'] != 'Will Not Implement']

#         # testing to see if tasks with no lead teams can be pulled in based on the task name
#         df.loc[df['Name'].str.contains(r'\[PL\]|CBB|\[Plan Library\]', na = False), 'Lead Team'] = 'Plan Library'
#         df.loc[df['Name'].str.contains(r'OFIN', na = False), 'Lead Team'] = 'Payment Banking - Smartinis/OFIN'
#         return df
#     return []

# s = 'ST20047'
# # print(live_rally_data(s))

# url = f"{rally_url}/PortfolioItem/StrategicTheme"
# params = {
#     "query": f'(FormattedID = "{s}")',
#     "fetch": "_ref,FormattedID,Workspace,ObjectID",
# }



# response = requests.get(url, headers=HEADERS, params=params).json()
# # pprint.pprint(response)

# wid = response["QueryResult"]["Results"][0]['Workspace']['ObjectID']
# oid = response["QueryResult"]["Results"][0]['ObjectID']

# url = f"{rally_url}/PortfolioItem/SolutionCapability"

# params = {
#      "workspace": f"/Workspace/{wid}",
#      "query": f'(Parent = /portfolioitem/strategictheme/{oid})',
#      "fetch": "_FormattedID,State,Name",
#      "pagesize": 200
# }

# response = requests.get(url, headers=HEADERS, params=params)
# data = response.json()
# pprint.pprint(data['QueryResult']['Results'][0])
# ref_link = data['QueryResult']['Results'][0]['_ref']
# print(ref_link.split('/')[-1])


# url = f"{rally_url}/PortfolioItem/Feature"

# print(wid)
# params = {
#      "workspace": f"/Workspace/{wid}",
#      "query": f'(Parent = /portfolioitem/solutioncapability/821309001389)',
#      "fetch": 'FormattedID,Name,LeadTeam,ArtifactType,State,Release,ActualStartDate,ActualEndDate,Owner,'
#                  'PreliminaryEstimate,PreliminaryEstimateCountValue,PreliminaryEstimateValue,PlannedStartDate,'
#                  'PlannedEndDate,PercentDoneByStoryCount,PercentDoneByStoryPlanEstimate,LeafStoryPlanEstimateTotal,'
#                  'Project,PolarisRelease,CapabilityManager',
#         "pagesize": 200
# }


# response = requests.get(url, headers=HEADERS, params=params)
# data = response.json()
# pprint.pprint(data['QueryResult']['Results'])

# print(len(data['QueryResult']['Results']))
# for i in data['QueryResult']['Results']:
#     print(i['Name'])

 #print(get_features_by_capability_ref(data['QueryResult']['Results'][0]))

def get_live_rally_data(st):

    # retriving the unique OID and WID for the ST
    s_url = f"{rally_url}/PortfolioItem/StrategicTheme"
    params = {
        "query": f'(FormattedID = "{st}")',
        "fetch": "_ref,FormattedID,Workspace,ObjectID",
    }

    # returns the Rally url that is needed to find ST details
    response = requests.get(s_url, headers=HEADERS, params=params).json()

    s_results = response["QueryResult"]["Results"]
    oid = s_results[0]['ObjectID']
    wid = s_results[0]['Workspace']['ObjectID']

    # retrieving the capabilities for the ST
    c_url = f"{rally_url}/PortfolioItem/SolutionCapability"
    params = {
        "workspace": f"/Workspace/{wid}",
        "query": f'(Parent = /portfolioitem/strategictheme/{oid})',
        "fetch": "_ref,FormattedID,LeadTeam,ArtifactType,State,PercentDoneByStoryPlanEstimate,PreliminaryEstimateValue,Name,Owner,PlannedEndDate",
        "pagesize": 200
    }

    response = requests.get(c_url, headers=HEADERS, params=params)
    data = response.json()
    c_results = data['QueryResult']['Results']
    print(len(c_results))

    rows = []
    for c in c_results:
        cap_details = {
            'Lead Team': c.get('c_LeadTeam', None),
            'Release': None,
            'Artifact Type': 'Solution Capability',
            'Solution Capability': c["FormattedID"],
            'Feature': None,
            'ID': c.get('FormattedID', None),
            'State': (c.get('State', {}) or {}).get('_refObjectName', None),
            'Owner': (c.get('Owner', {}) or {}).get('_refObjectName', None),
            'PED': c.get('PlannedEndDate', None),
            '% Done By Story Plan Estimate': c.get('PercentDoneByStoryPlanEstimate', None),
            'Preliminary Estimate Value': c.get('PreliminaryEstimateValue', None),
            'Name': c.get('Name', None)
        }
        rows.append(cap_details)

        # retrieving the featuers for each capability
        ref = c['_ref'].split('/')[-1]
        print("REF", ref)

        f_url = f"{rally_url}/PortfolioItem/Feature"
        params = {
            "workspace": f"/Workspace/{wid}",
            "query": f'(Parent = /portfolioitem/solutioncapability/{ref})',
            "fetch": 'FormattedID,Name,LeadTeam,ArtifactType,State,Release,ActualStartDate,ActualEndDate,Owner,'
                        'PreliminaryEstimate,PreliminaryEstimateCountValue,PreliminaryEstimateValue,PlannedStartDate,'
                        'PlannedEndDate,PercentDoneByStoryCount,PercentDoneByStoryPlanEstimate,LeafStoryPlanEstimateTotal,'
                        'Project,PolarisRelease,CapabilityManager',
            "pagesize": 200
        }
        
        response = requests.get(f_url, headers=HEADERS, params=params)
        data = response.json()
        f_results = data['QueryResult']['Results']

        for feature in f_results:
            feature_details = {
                'Lead Team': feature.get('c_LeadTeam', None),
                'Release': (feature.get('Release', {}) or {}).get('_refObjectName', None),
                'Artifact Type': 'Feature',
                'Solution Capability': c["FormattedID"],
                'Feature': feature.get('FormattedID', None),
                'ID': feature.get('FormattedID', None),
                'State': (feature.get('State', {}) or {}).get('_refObjectName', None),
                'Owner': (feature.get('Owner', {}) or {}).get('_refObjectName', None),
                'PED': feature.get('PlannedEndDate', None),
                '% Done By Story Plan Estimate': feature.get('PercentDoneByStoryPlanEstimate', None),
                'Preliminary Estimate Value': feature.get('PreliminaryEstimateValue', None),
                'Name': feature.get('Name', 'N/A'),
            }
            rows.append(feature_details)
    df = pd.DataFrame(rows)
    return df

# x = get_live_rally_data('ST20047')
# filtered_df = x[x['State'].str.contains('Will', na=False)]
# print(filtered_df)



# def get_strategic_theme_ref(st_id):
#         """
#         Retrives the unique Rally API URL that can be used to retrieve capability and feature information.
#         """
#         # defines the parameters for the Rally API call
#         url = f"{rally_url}/PortfolioItem/StrategicTheme"
#         params = {
#             "query": f'(FormattedID = "{st_id}")',
#             "fetch": "_ref,FormattedID,Workspace,ObjectID",
#         }

#         # returns the Rally url that is needed to find ST details
#         response = requests.get(url, headers=HEADERS, params=params).json()

#         result = response["QueryResult"]["Results"]
#         oid = result[0]['ObjectID']
#         wid = result[0]['Workspace']['ObjectID']
#         if result:
#             return oid, wid #[0]["_ref"], obj_id,
#         return None

# def get_features_by_capability_ref(capability, wid):
#     """
#     Retrieves all feature details given a capability.
#     """
#     # defines the parameters for the Rally API call

#     ref = capability['_ref'].split('/')[-1]
#     print(ref)
#     print(wid)

#     url = f"{rally_url}/PortfolioItem/Feature"
#     params = {
#         "workspace": f"/Workspace/{wid}",
#         "query": f'(Parent = /portfolioitem/solutioncapability/821309001389)',
#         "fetch": 'FormattedID,Name,LeadTeam,ArtifactType,State,Release,ActualStartDate,ActualEndDate,Owner,'
#                  'PreliminaryEstimate,PreliminaryEstimateCountValue,PreliminaryEstimateValue,PlannedStartDate,'
#                  'PlannedEndDate,PercentDoneByStoryCount,PercentDoneByStoryPlanEstimate,LeafStoryPlanEstimateTotal,'
#                  'Project,PolarisRelease,CapabilityManager',
#         "pagesize": 200
#     }

#     response = requests.get(url, headers=HEADERS, params=params)

#     # returns the specific columns of data for each feature based on a given capability
#     if response.status_code == 200:
#         data = response.json()
#         result = data['QueryResult']['Results']
#         print('THIS IS THE FEATURES FOR REF: ', ref)
#         pprint.pprint(result)
#         print('---------------------------------')
#         features = []
#         for feature in result:
#             feature_details = {
#                 'Lead Team': feature.get('c_LeadTeam', None),
#                 'Release': (feature.get('Release', {}) or {}).get('_refObjectName', None),
#                 'Artifact Type': 'Feature',
#                 'Solution Capability': capability["FormattedID"],
#                 'Feature': feature.get('FormattedID', None),
#                 'ID': feature.get('FormattedID', None),
#                 'State': (feature.get('State', {}) or {}).get('_refObjectName', None),
#                 'Owner': (feature.get('Owner', {}) or {}).get('_refObjectName', None),
#                 'PED': feature.get('PlannedEndDate', None),
#                 '% Done By Story Plan Estimate': feature.get('PercentDoneByStoryPlanEstimate', None),
#                 'Preliminary Estimate Value': feature.get('PreliminaryEstimateValue', None),
#                 'Name': feature.get('Name', 'N/A')
#             }
#             features.append(feature_details)
#         return features
#     return []

# def live_rally_data(rally_st):
#     """
#     Retrieves all capability details given an ST.
#     """
#     # defines the parameters for the Rally API call
#     oid, wid = get_strategic_theme_ref(rally_st)

#     # print("Object ID:", oid)
#     # print("Workspace ID:", wid)

#     url = f"{rally_url}/PortfolioItem/SolutionCapability"
#     params = {
#         "workspace": f"/Workspace/{wid}",
#         "query": f'(Parent = /portfolioitem/strategictheme/{oid})',
#         "fetch": "_ref,FormattedID,LeadTeam,ArtifactType,State,PercentDoneByStoryPlanEstimate,PreliminaryEstimateValue,Name,Owner,PlannedEndDate",
#         "pagesize": 200
#     }

#     response = requests.get(url, headers=HEADERS, params=params)

#     # returns a list of all capabilities and the specified columns given a ST
#     if response.status_code == 200:
#         data = response.json()
#         # pprint.pprint(data)
#         # print(len(data['QueryResult']['Results']))
#         # for i in data['QueryResult']['Results']:
#         #     print(i['Name'])
#         result = data['QueryResult']['Results']
#         # print(len(result))
#         rows = []
#         for c in result:
#             cap_details = {
#                 'Lead Team': c.get('c_LeadTeam', None),
#                 'Release': None,
#                 'Artifact Type': 'Solution Capability',
#                 'Solution Capability': c["FormattedID"],
#                 'Feature': None,
#                 'ID': c.get('FormattedID', None),
#                 'State': (c.get('State', {}) or {}).get('_refObjectName', None),
#                 'Owner': (c.get('Owner', {}) or {}).get('_refObjectName', None),
#                 'PED': c.get('PlannedEndDate', None),
#                 '% Done By Story Plan Estimate': c.get('PercentDoneByStoryPlanEstimate', None),
#                 'Preliminary Estimate Value': c.get('PreliminaryEstimateValue', None),
#                 'Name': c.get('Name', None)
#             }
#             rows.append(cap_details)

#             # calling the get features function to retreive the features for each capabilitiy
#             features = get_features_by_capability_ref(c, wid)
#             if len(features) > 0:
#                  rows.extend(features)

#         # creating a dataframe with the features and capabilities
#         df = pd.DataFrame(rows)

#         # dropping tasks with a Will Not Implement Status
#         df = df[df['State'] != 'Will Not Implement']

#         # testing to see if tasks with no lead teams can be pulled in based on the task name
#         # df.loc[df['Name'].str.contains(r'\[PL\]|CBB|\[Plan Library\]', na = False), 'Lead Team'] = 'Plan Library'
#         # df.loc[df['Name'].str.contains(r'OFIN', na = False), 'Lead Team'] = 'Payment Banking - Smartinis/OFIN'
#         return df
#     return []

# x = live_rally_data('ST20047')
# filtered_df = x[x['Name'].str.contains('SAMx', na=False)]
# print(filtered_df)