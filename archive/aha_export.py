import requests
import pandas as pd
import time
from engine import get_aha_data

def live(idea):
    headers = {
        'Authorization' : 'Bearer REDACTED_TOKEN'
    }
    data = []
    project_url = 'https://optum.aha.io/api/v1/ideas/' + idea
    project_details = requests.get(url=project_url, headers=headers).json()['idea']
    impacted_apps = project_details['custom_object_links'][0]['record_ids']
    aha_details = project_details['custom_fields']

    for d in aha_details:
        if 'initial_oversight_amount_usp' in d.values():
            os_approved = d['value']
            continue
        # if 'funding_usp' in d.values():
        #     funding = d['value']
        #     continue
        if 'date_needed' in d.values():
            go_live = d['value']

    for app in impacted_apps:
        url = 'https://optum.aha.io/api/v1/custom_object_records/' + app
        details = requests.get(url, headers=headers).json()['custom_object_record']['custom_fields']

        df_row = [idea, os_approved, go_live]
        impact = None
        
        for d in details:
            if 'idea_impact_type' in d.values():
                impact = d['value']
                df_row.append(impact)
                continue

        if "Development" not in df_row and "Test Only" not in df_row:
            continue
        
        for d in details:
            if 'delivery_team' in d.values():
                df_row.append(d['value'])
                continue
            # if 'impact_cost' in d.values():
            #     df_row.append(d['value'])
            #     continue
            if 'updated_cost' in d.values():
                df_row.append(d['value'])
                continue
        data.append(df_row)

    cleaded_aha = pd.DataFrame(data, columns = ['Aha Idea', 'Oversight Approved Amount', 'Desired completion date', 'Impact Type', 'Impact Cost', 'Impacts Delivery team'])
    cleaned_aha = cleaded_aha[['Impacts Delivery team', 'Impact Type', 'Impact Cost', 'Oversight Approved Amount', 'Desired completion date']]
    cleaned_aha['Impact Type'] = 'Development'
    cleaned_aha = cleaned_aha[cleaned_aha['Impact Cost'] != '0.0']
    os_approved = cleaned_aha['Oversight Approved Amount'].iloc[0]
    return cleaned_aha, os_approved

# aha = 'PSTRATEGIC-I-847'

# automated = live(aha)[0]
# manual = get_aha_data(aha)[0]

# print("LIVE AHA PULL:\n\n", automated)
# print('\n')
# print('MANUAL AHA PULL:\n\n', manual)
