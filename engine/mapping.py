from typing_extensions import final
from engine.utils import read_excel_to_dataframe
import pandas as pd
import numpy as np
import requests
import certifi
import os
import pprint
import urllib3
from io import StringIO
from config import Config

# Load configuration
config = Config()

# Suppress SSL warnings for corporate environments
if not config.VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------- TEMPLATE EXPORT FUNCTION ----------------------------------

def get_template(project_type, bdl, rdl, file_name=None):
    """
    Retrieves the appropriate project plan template based on the user input.
    """
    try:
        if file_name is None:
            file_name = config.TEMPLATE_FILE
        
        print(f"Loading template file: {file_name}")
        
        # Check if template file exists
        if not os.path.exists(file_name):
            print(f"Template file not found at: {os.path.abspath(file_name)}")
            # Try alternative paths
            alternative_paths = [
                f"/app/{file_name}",
                f"/app/documents/GNP_Template_v4.xlsx",
                "documents/GNP_Template_v4.xlsx"
            ]
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    file_name = alt_path
                    print(f"Found template at alternative path: {alt_path}")
                    break
            else:
                raise FileNotFoundError(f"Template file not found at any location: {file_name}, tried: {alternative_paths}")
        
        # Retrieve the appropriate template based on the selected project type
        if project_type == 'Care Cash':
            template_name = 'cc_template_projectPlan'
        elif project_type == 'Foundational-PCP Assignment':
            template_name = 'template_projectPlan'
        elif project_type == 'General':
            template_name = 'general_template_projectPlan'
        else:
            template_name = 'template_projectPlan'  # Default template
        
        print(f"Loading sheet: {template_name} from {file_name}")
        
        # First check what sheets are available
        try:
            excel_file = pd.ExcelFile(file_name)
            available_sheets = excel_file.sheet_names
            print(f"Available sheets: {available_sheets}")
            
            if template_name not in available_sheets:
                print(f"Sheet {template_name} not found. Using first available sheet: {available_sheets[0]}")
                template_name = available_sheets[0]
        except Exception as e:
            print(f"Error reading Excel file sheets: {e}")
        
        template = read_excel_to_dataframe(file_name, template_name)
        
        # Check if template was loaded successfully
        if template is None:
            raise ValueError(f"Template '{template_name}' could not be loaded - returned None")
        
        if template.empty:
            raise ValueError(f"Template '{template_name}' is empty - 0 rows loaded")
        
        print(f"Template loaded successfully: {len(template)} rows, columns: {list(template.columns)}")
        
        # Check if required columns exist
        if 'Assigned To' not in template.columns:
            print(f"Warning: Template missing 'Assigned To' column. Available columns: {list(template.columns)}")
            # Try to find similar column names
            possible_columns = [col for col in template.columns if col and ('assign' in str(col).lower() or 'owner' in str(col).lower())]
            if possible_columns:
                print(f"Using column '{possible_columns[0]}' instead of 'Assigned To'")
                template = template.rename(columns={possible_columns[0]: 'Assigned To'})
            else:
                # Add the column if it doesn't exist
                template['Assigned To'] = bdl  # Default assignment
        
        # Replace placeholders with actual values
        template['Assigned To'] = template['Assigned To'].replace({
            'BDL': bdl,
            'RDL': rdl
        })
        
        return template
        
    except Exception as e:
        print(f"Error loading template: {e}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Files in current directory: {os.listdir('.')}")
        if os.path.exists('documents'):
            print(f"Files in documents directory: {os.listdir('documents')}")
        
        # Return a basic template structure as fallback
        fallback_template = pd.DataFrame({
            'Work Breakdown': ['Project Planning', 'Requirements Analysis', 'Development Phase 1', 'Testing Phase 1', 'Deployment'],
            'Task ID': ['1', '2', '3', '4', '5'],
            'Assigned To': [bdl, rdl, bdl, rdl, bdl],
            'Release': ['Initial', 'Initial', 'Phase 1', 'Phase 1', 'Phase 1'],
            'Status': ['Not Started', 'Not Started', 'Not Started', 'Not Started', 'Not Started'],
            'Level': [1, 2, 2, 2, 1]
        })
        print(f"Returning fallback template with {len(fallback_template)} rows")
        return fallback_template

# --------------------------------- LEAD TEAM MAPPING EXPORT FUNCTION ----------------------------------

def get_lead_team_mapping(file_name = 'documents/GNP_Template_v4.xlsx', map = 'mapping_rallyLeadTeam'):
    """
    Retrieves the Lead Team Mapping information from the Excel and returns it as a dictionary.
    """
    # pulls the lead team mapping from the Excel workbook
    lead_team_mapping = read_excel_to_dataframe(file_name, map)
    
    # creates a dictionary with lead team and desired output in the project plan
    ltm_dict = dict(zip(lead_team_mapping.iloc[1:]['rally_Data '], lead_team_mapping.iloc[1:]['Output_Project plan']))
    return ltm_dict

# --------------------------------- COST PER POINT EXPORT FUNCTION ----------------------------------

def get_cpp(file_name = 'documents/GNP_Template_v4.xlsx', map = 'mapping_rallyLeadTeam'):
    cpp = read_excel_to_dataframe(file_name, map)
    cpp_calculator = dict(zip(cpp.iloc[1:]['rally_Data '], cpp.iloc[1:]['CPP']))
    return cpp_calculator

# --------------------------------- TASK MAPPING EXPORT FUNCTION ----------------------------------

def get_task_mapping(file_name = 'documents/GNP_Template_v4.xlsx', map = 'mapping_rallyLeadTeam'):
    mapping = read_excel_to_dataframe(file_name, map)
    task_name_mapping = dict(zip(mapping.iloc[1:]['Optics Name'], mapping.iloc[1:]['Output_Project plan']))
    return task_name_mapping

# --------------------------------- LIVE AHA DATA RETRIEVAL FUNCTION ----------------------------------
def get_aha_data(idea):
    """
    Pulls the live updated Aha impacts given an idea. Returns the cleaned df and the os approved amount.
    """
    try:
        # pulling the Aha data via its API
        headers = config.get_aha_headers()
        data = []
        project_url = f'{config.AHA_BASE_URL}/ideas/' + idea
        project_details = requests.get(url=project_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()['idea']

        # Initialize defaults for potentially missing values
        tag_record = None
        prj = 'dne'
        theme = 'No ST'
        os_approved = 0
        go_live = None

        # Get initiative/tag info
        for i in project_details['custom_fields']:
            if 'initiative' in i.values():
                tag_record = i['value'][0]
                break

        # Get project ID
        for i in project_details['custom_fields']:
            if 'ppm_optics_prj' in i.values():
                prj = i['value']
                break

        # Get tag name if tag_record exists
        if tag_record:
            try:
                tag = requests.get(url=f'{config.AHA_BASE_URL}/initiatives/' + tag_record, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()['initiative']['name']
            except:
                tag = 'default'
        else:
            tag = 'default'
            
        # Try to get strategic theme - this is where it might be missing
        try:
            capability_url = project_details['master_feature']['resource']
            capability = requests.get(url = capability_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()

            st_list = capability['epic']['integration_fields']

            for i in st_list:
                if str(i['name']) == 'FormattedID':
                    theme = i['value']
                    break

            if theme.startswith('ST') == False or theme == '':
                theme = 'No ST'
        except Exception as e:
            print(f"Could not retrieve strategic theme: {e}")
            theme = 'No ST'  # Only theme defaults to 'No ST', other data still captured
        
        # Final validation: ensure theme is valid ST number or set to 'No ST'
        if not theme or not isinstance(theme, str) or not theme.startswith('ST') or theme == '':
            theme = 'No ST'

        # pulling a list of impacted apps as AHA API records
        impacted_apps = []
        for link in project_details['custom_object_links']:
            if link['key'] == 'idea_impacts':
                impacted_apps = link['record_ids']
                break
        
        aha_details = project_details['custom_fields']

        for d in aha_details:
            # searching the response to pull the OS Approved amount
            if 'oversight_approved_amount_usp' in d.values():
                os_approved = d['value']
                continue
            # searching the response to pull the go-live date
            if 'date_needed' in d.values():
                go_live = d['value']

        for app in impacted_apps:
            # new API call for each impacted app
            url = f'{config.AHA_BASE_URL}/custom_object_records/' + app
            details = requests.get(url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()['custom_object_record']['custom_fields']

            df_row = [idea, os_approved, go_live]
            impact = None
            
            for d in details:
                # searching the response for the impact type
                if 'idea_impact_type' in d.values():
                    impact = d['value']
                    df_row.append(impact)
                    continue
            
            # checking for tech impacts - Development or Test Only as the impact type
            if "Development" not in df_row and "Test Only" not in df_row:
                continue
            
            for d in details:
                # searching the response for the delivery team name
                if 'delivery_team' in d.values():
                    df_row.append(d['value'])
                    continue
                # searching the resposne for the updated cost for the impacted app
                if 'updated_cost' in d.values():
                    df_row.append(d['value'])
                    continue
            data.append(df_row)
        
        # transforming the data into a pandas dataframe
        cleaded_aha = pd.DataFrame(data, columns = ['Aha Idea', 'Oversight Approved Amount', 'Desired completion date', 'Impact Type', 'Impact Cost', 'Impacts Delivery team'])

        # reordering columns
        cleaned_aha = cleaded_aha[['Impacts Delivery team', 'Impact Type', 'Impact Cost', 'Oversight Approved Amount', 'Desired completion date']].copy()

        # splitting Cirrus QIB to split into Cirrus QIB - SIT Testing if the impact type in the Aha is TO
        mask = (cleaned_aha['Impacts Delivery team'] == 'Cirrus QIB') & (cleaned_aha['Impact Type'] == 'Test Only')
        cleaned_aha.loc[mask, 'Impacts Delivery team'] = 'Cirrus QIB - SIT Testing'
        
        # removing any impacts that have a impact amount of 0
        cleaned_aha = cleaned_aha[cleaned_aha['Impact Cost'] != '0.0']

        # Convert Impact Cost to numeric, handling any invalid values
        try:
            cleaned_aha['Impact Cost'] = pd.to_numeric(cleaned_aha['Impact Cost'], errors='coerce').round().astype(int)
        except Exception as e:
            print(f"Warning: Error converting Impact Cost to numeric: {e}")
            # Remove rows with non-numeric impact costs
            cleaned_aha['Impact Cost'] = pd.to_numeric(cleaned_aha['Impact Cost'], errors='coerce')
            cleaned_aha = cleaned_aha.dropna(subset=['Impact Cost'])
            cleaned_aha['Impact Cost'] = cleaned_aha['Impact Cost'].round().astype(int)

        cleaned_aha = cleaned_aha.groupby('Impacts Delivery team').agg({
            'Impact Type': 'first',
            'Impact Cost': 'sum',
            'Oversight Approved Amount': 'first',
            'Desired completion date': 'first'
        }).reset_index()
        
        # saving the total OS approved for the project as a new variable
        if not cleaned_aha.empty:
            os_approved = cleaned_aha['Oversight Approved Amount'].iloc[0]

        return cleaned_aha, os_approved, theme, tag, prj, go_live
    
    except Exception as e:
        print(f"Critical error fetching AHA data (API failure or invalid idea): {e}")
        # Return empty DataFrame to trigger error in build_plan
        # This catches complete API failures (network, auth, invalid idea ID)
        # Missing theme is handled gracefully above (theme='No ST')
        return (pd.DataFrame(), 0, 'No ST', 'default', 'default', None)
    
def get_aha_os(idea):
    """
    Pulls the live updated Aha impacts given an idea. Returns the cleaned df and the os approved amount.
    """
    try:
        aha_sum = 0
        # pulling the Aha data via its API
        headers = config.get_aha_headers()
        data = []
        project_url = f'{config.AHA_BASE_URL}/ideas/' + idea
        project_details = requests.get(url=project_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()['idea']

        try:
            name = project_details['name']
        except:
            name = ''

        # pulling a list of impacted apps as AHA API records
        impacted_apps = []
        for link in project_details['custom_object_links']:
            if link['key'] == 'idea_impacts':
                impacted_apps = link['record_ids']
                break
        for app in impacted_apps:
            # new API call for each impacted app
            url = f'{config.AHA_BASE_URL}/custom_object_records/' + app
            details = requests.get(url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT).json()['custom_object_record']['custom_fields']

            df_row = [idea]
            impact = None

            for d in details:
                # searching the response for the impact type
                if 'idea_impact_type' in d.values():
                    impact = d['value']
                    df_row.append(impact)
                    continue
            
            # checking for tech impacts - Development or Test Only as the impact type
            if "Development" not in df_row and "Test Only" not in df_row:
                continue
            
            for d in details:
                # searching the response for the delivery team name
                if 'delivery_team' in d.values():
                    df_row.append(d['value'])
                    continue
                # searching the resposne for the updated cost for the impacted app
                if 'updated_cost' in d.values():
                    df_row.append(d['value'])
                    aha_sum += float(d['value'])
                    continue
            data.append(df_row)
        
        return aha_sum, name
    
    except Exception as e:
        print(f"Critical error fetching AHA data (API failure or invalid idea): {e}")
        # Return empty DataFrame to trigger error in build_plan
        # This catches complete API failures (network, auth, invalid idea ID)
        # Missing theme is handled gracefully above (theme='No ST')
        try:
            aha_df = get_aha_data(idea)[0]
            aha_sum = aha_df['Impact Cost'].sum()
            return aha_sum, ''
        except Exception as e:
            print(f"Error in fallback AHA data fetch: {e}")
            return (pd.DataFrame(), 0, 'No ST', 'default', 'default', None)

# --------------------------------- PULL LIVE RALLY DATA FROM THE DATA CATALOG EXPLORER ----------------------------------

def get_rally_hcp(strategic_theme_nbr='ST15926'):
    # headers = config.get_icarus_headers()

    ### Getting the Icaurus access token ###
    token_url = f'{config.ICARUS_BASE_URL}/login/access-token'

    payload = {
        'username': config.ICARUS_USERNAME,
        'password': config.ICARUS_PASSWORD
    }

    response = requests.post(token_url, data=payload, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    access_token = response.json().get('access_token')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    ### Getting strategic theme id ###
    theme_url = f'{config.ICARUS_BASE_URL}/domains/delivery/collections/agile_strategic_theme/csv?columns=strategic_theme_id&columns=strategic_theme_nbr'

    theme_response = requests.get(theme_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    theme_response_text = theme_response.content.decode('utf-8')

    themes = pd.read_csv(StringIO(theme_response_text))
    
    # Debug: Check what columns we actually got
    print(f"[DEBUG] Rally API returned columns: {list(themes.columns)}")
    print(f"[DEBUG] Looking for strategic theme: {strategic_theme_nbr}")
    
    # Check if the expected columns exist
    if 'strategic_theme_nbr' not in themes.columns or 'strategic_theme_id' not in themes.columns:
        print(f"[ERROR] Expected columns missing. Available columns: {list(themes.columns)}")
        print(f"[ERROR] First few rows of response:\n{themes.head()}")
        raise KeyError(f"Rally API response missing expected columns. Got: {list(themes.columns)}")

    # Check if the strategic theme exists in the data
    matching_themes = themes[themes['strategic_theme_nbr'] == strategic_theme_nbr]
    if matching_themes.empty:
        print(f"[ERROR] Strategic theme {strategic_theme_nbr} not found in Rally data")
        print(f"[ERROR] Available themes: {themes['strategic_theme_nbr'].unique()[:10].tolist()}")
        raise ValueError(f"Strategic theme {strategic_theme_nbr} not found in Rally. It may not exist or may be archived.")
    
    theme_id = matching_themes['strategic_theme_id'].values[0]
    print(f"[DEBUG] Found theme_id: {theme_id} for {strategic_theme_nbr}")

    ### Getting capabilities under the strategic theme ###
    capability_url = f'https://insights.hcp.uhg.com/api/icarus/v1/domains/delivery/collections/agile_solution_capability/csv?columns=solution_capability_id&columns=parent_id&columns=solution_capability_nbr&columns=title&columns=owner_name&columns=solution_capability_state&columns=planned_end_date_local&columns=preliminary_estimate_value&columns=pct_done_by_story_points'

    capability_response = requests.get(capability_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    capability_response_text = capability_response.content.decode('utf-8')

    capabilities = pd.read_csv(StringIO(capability_response_text))

    filtered_capabilities = capabilities[(capabilities['parent_id'] == theme_id) & (capabilities['solution_capability_state'] != 'Will Not Implement')].drop(columns=['work_source', 'source_id', 'team_id', 'parent_id']).rename(columns={'title': 'Name', 'owner_name': 'Owner', 'planned_end_date_local': 'Planned End Date', 'preliminary_estimate_value': 'Preliminary Estimate Value', 'pct_done_by_story_points': '% Done By Story Plan Estimate', 'solution_capability_nbr': 'ID', 'solution_capability_state': 'State'})
    filtered_capabilities['Artifact Type'] = 'Solution Capability'
    filtered_capabilities['Solution Capability'] = filtered_capabilities['ID']
    filtered_capabilities['Release'] = np.nan
    filtered_capabilities['Lead Team'] = np.nan
    filtered_capabilities['Feature'] = np.nan
    filtered_capabilities['Rally Lead Team'] = filtered_capabilities['Lead Team']

    cap_ids = filtered_capabilities['solution_capability_id'].tolist()

    cap_map = dict(zip(filtered_capabilities['solution_capability_id'], filtered_capabilities['ID']))

    filtered_capabilities = filtered_capabilities.drop(columns=['solution_capability_id'])

    ### Getting features under the capabilities ###
    # Check if we have any capabilities before proceeding
    if not cap_ids:
        print(f"[WARNING] No capabilities found for strategic theme {strategic_theme_nbr}")
        # Return empty DataFrames with correct structure
        return filtered_capabilities, pd.DataFrame(columns=[
            'ID', 'Name', 'Owner', 'Release', 'State', 'Planned End Date',
            '% Done By Story Plan Estimate', 'Preliminary Estimate Value',
            'Lead Team', 'Rally Lead Team', 'Artifact Type',
            'Solution Capability', 'Feature'
        ])
    
    parent_id_search = f'parent_id={cap_ids[0]}'

    for i in cap_ids[1:]:
        parent_id_search = parent_id_search + '&parent_id=' + str(i)

    features_url = f'https://insights.hcp.uhg.com/api/icarus/v1/domains/delivery/collections/agile_feature/csv?columns=parent_id&columns=feature_nbr&columns=team_name&columns=title&columns=owner_name&columns=feature_state&columns=planned_end_date_local&columns=preliminary_estimate_value&columns=pct_done_by_story_points&columns=release_name&{parent_id_search}'

    features_response = requests.get(features_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    features_response_text = features_response.content.decode('utf-8')

    features = pd.read_csv(StringIO(features_response_text))

    # filtering features based on the capability ids and removing any features that are Will Not Implement
    filtered_features = features[(features['parent_id'].isin(cap_ids)) & (features['feature_state'] != 'Will Not Implement')].drop(columns=['work_source', 'source_id', 'team_id', 'feature_id']).rename(columns={'title': 'Name', 'owner_name': 'Owner', 'planned_end_date_local': 'Planned End Date', 'preliminary_estimate_value': 'Preliminary Estimate Value', 'pct_done_by_story_points': '% Done By Story Plan Estimate', 'feature_nbr': 'ID', 'feature_state': 'State', 'team_name': 'Lead Team', 'release_name': 'Release', 'parent_id': 'Solution Capability'})
    filtered_features['Feature'] = filtered_features['ID']
    filtered_features['Artifact Type'] = 'Feature'
    filtered_features['Solution Capability'] = filtered_features['Solution Capability'].map(cap_map)
    filtered_features['Rally Lead Team'] = filtered_features['Lead Team']

    # adding rules to map certain features to certain lead teams based on feature name keywords
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('RTC'), 'RTC/URS', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('SAMx'), 'SAMx', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('FA&R:'), 'Financial Management/ FA&R', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('OFIN:'), 'Payment Banking - Smartinis/OFIN', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('UES'), 'UeS', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('QRT'), 'QRT', filtered_features['Lead Team'])
    filtered_features['Lead Team'] = np.where(filtered_features['Name'].str.contains('BD Apps'), 'Big Data Applications', filtered_features['Lead Team'])

    filtered_features['Rally Lead Team'] = filtered_features['Lead Team']

    return filtered_capabilities, filtered_features

# --------------------------------- CLEANING UP RALLY DATA ----------------------------------

def get_rally_data_hcp(st, ltm, file_name = 'documents/GNP_Template_v4.xlsx', data = 'input_rallyData'):
    """
    Pulls the live updated Rally data given an ST. Returns the cleaned df.    
    """

    # pulling the capabilities and features from rally based on the strategic theme number
    capabilities, features = get_rally_hcp(strategic_theme_nbr=st)

    # Fill in missing feature Lead Teams from parent capability
    for _, cap in capabilities.iterrows():
        cap_id = cap['ID']
        cap_lead = cap['Lead Team']

        # creating a boolean mask where a feature has the parent matching cap_id and no lead team, and filling in the corresponding lead team
        mask = (features['Solution Capability'] == cap_id) & (features['Lead Team'].isna())
        if cap_lead and not pd.isna(cap_lead):
            features.loc[mask, 'Lead Team'] = cap_lead

    # Simplified approach: each capability listed once, followed by all its features
    final_rows = []

    for _, cap in capabilities.iterrows():
        cap_id = cap['ID']
        
        # Add the capability
        final_rows.append(cap.to_dict())
        
        # Add all features that belong to this capability (based on Solution Capability match only)
        matching_features = features[features['Solution Capability'] == cap_id]
        final_rows.extend(matching_features.to_dict('records'))

    # creating a dataframe for the rally data
    df = pd.DataFrame(final_rows)
    
    # Handle case where no Rally data was found
    if df.empty:
        # Return empty DataFrame with all required columns
        return pd.DataFrame(columns=[
            'ID', 'Name', 'Owner', 'Release', 'State', 'Planned End Date',
            '% Done By Story Plan Estimate', 'Preliminary Estimate Value',
            'Rally Cost Estimate', 'Lead Team', 'Rally Lead Team', 'Artifact Type',
            'Solution Capability', 'Feature'
        ])
    
    # mapping the rally lead teams to the lead team mapping from the Excel workbook
    df['Lead Team'] = df['Lead Team'].map(ltm)

    # replace unmapped lead teams (NaN) with 'Other' to group them under the Other category
    df['Lead Team'] = df['Lead Team'].fillna('Other')

    for i in range(len(df) - 1):
        is_capability = df.at[i, 'ID'].startswith('C')
        next_id = df.at[i + 1, 'ID']
        next_team = df.at[i + 1, 'Rally Lead Team']

        is_next_feature = next_id.startswith('F')
        has_next_team = isinstance(next_team, str) and next_team.strip() != ''

        if is_capability and is_next_feature and has_next_team:
            df.at[i, 'Rally Lead Team'] = next_team

    # calculating the rally cost estimate based on the cost per point mapping from the Excel workbook
    df['Cost Per Point'] = df['Rally Lead Team'].map(get_cpp())

    df.loc[df['ID'].astype(str).str.startswith('C'), 'Preliminary Estimate Value'] = np.nan

    # calculating the rally cost estimate
    df['Rally Cost Estimate'] = df['Cost Per Point'] * df['Preliminary Estimate Value']
    df['Rally Cost Estimate'] = df['Rally Cost Estimate'].astype('Int64')

    df = df.drop(['Cost Per Point'], axis=1)

    # ensure Rally Lead Team NaN values are converted to empty strings to prevent 'nan' string issues
    df['Rally Lead Team'] = df['Rally Lead Team'].fillna('')
    
    return df

# --------------------------------- RETRIEVING THE LIVE OPTICS DATA FROM THE DATA CATALOG EXPLORER ----------------------------------
def get_optics(prj, st):
    # headers = config.get_icarus_headers()

    ### Getting the Icaurus access token ###
    token_url = f'{config.ICARUS_BASE_URL}/login/access-token'

    payload = {
        'username': config.ICARUS_USERNAME,
        'password': config.ICARUS_PASSWORD
    }

    response = requests.post(token_url, data=payload, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    access_token = response.json().get('access_token')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    dce_url = f'{config.ICARUS_BASE_URL}/domains/finance/collections/ppmo_work_effort_resource/csv?slicetype=MONTHLY&project_id={prj}'

    dce_response = requests.get(dce_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    response_text = dce_response.content.decode('utf-8')

    df = pd.read_csv(StringIO(response_text))

    if df.empty:
        return None

    # calculating estimated cost and etc cost based on onshore / offshore
    df['estimated_cost'] = np.where(df['onshore_offshore'] == 'Onshore', df['actual_l_hours'] * 145, df['actual_l_hours'] * 46)

    df['etc_l_cost'] = np.where(df['onshore_offshore'] == 'Onshore', df['etc_l_hours'] * 145, df['etc_l_hours'] * 46)

    # aggregating the data based on task name
    df = df.groupby(['taskname']).agg(
        Actuals=('estimated_cost', 'sum'),
        ETCs=('etc_l_cost', 'sum'),
    ).reset_index()

    df['EACs'] = df['Actuals'] + df['ETCs']

    # filtering the data based on the strategic theme input
    try:
        df = df[df['taskname'].str.contains(st)]
        df['task_team_name'] = df['taskname'].str.split('_')

        task_mapping = get_task_mapping()
        app_keys = list(task_mapping.keys())

        # Map taskname to the appropriate key if any word in task_team_name matches app_keys
        def find_matching_key(word_list):
            for word in word_list:
                if word in app_keys:
                    return task_mapping[word]
            return word_list[-1]  # fallback to last word if no match
        
        df['task_name_mapped'] = df['task_team_name'].apply(find_matching_key)

        df = df.drop(columns=['task_team_name', 'taskname'], axis=1)
        df = df.groupby('task_name_mapped').sum(numeric_only=True).reset_index()
        df = df.rename(columns={'Actuals': 'Actuals Est (Hours x Rate)'})
    except:
        df = None

    return df

def get_optics_financials(prj, st):
    # headers = config.get_icarus_headers()

    ### Getting the Icaurus access token ###
    token_url = f'{config.ICARUS_BASE_URL}/login/access-token'

    payload = {
        'username': config.ICARUS_USERNAME,
        'password': config.ICARUS_PASSWORD
    }

    response = requests.post(token_url, data=payload, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    access_token = response.json().get('access_token')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    dce_url = f'{config.ICARUS_BASE_URL}/domains/finance/collections/ppmo_work_effort_resource/csv?slicetype=MONTHLY&project_id={prj}'

    dce_response = requests.get(dce_url, headers=headers, verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT)

    response_text = dce_response.content.decode('utf-8')

    df = pd.read_csv(StringIO(response_text))

    if df.empty:
        return None

    # calculating estimated cost and etc cost based on onshore / offshore
    df['estimated_cost'] = np.where(df['onshore_offshore'] == 'Onshore', df['actual_l_hours'] * 145, df['actual_l_hours'] * 46)

    df['etc_l_cost'] = np.where(df['onshore_offshore'] == 'Onshore', df['etc_l_hours'] * 145, df['etc_l_hours'] * 46)

    # aggregating the data based on task name
    df = df.groupby(['taskname']).agg(
        Actuals=('estimated_cost', 'sum'),
        ETCs=('etc_l_cost', 'sum'),
    ).reset_index()

    df['EACs'] = df['Actuals'] + df['ETCs']

    # filtering the data based on the strategic theme input
    try:
        df = df[df['taskname'].str.contains(st)]

        df = df[['taskname', 'Actuals', 'ETCs', 'EACs']].rename(columns={'taskname': 'Task Name'})
        df['Actuals'] = df['Actuals'].round(0)
        df['ETCs'] = df['ETCs'].round(0)
        df['EACs'] = df['EACs'].round(0)
        df['% Burn'] = np.where(df['EACs'] > 0, (df['Actuals'] / df['EACs']) * 100, 0).round(0)
    except:
        df = None

    return df

# --------------------------------- TEMPLATE, RALLY, AHA MERGE FUNCTIONS ----------------------------------
def merge_aha_rally(aha, rally):
    """"
    Merges the cleaned Aha and Rally data based on MAPPED Lead Team matching AHA Impacts Delivery team.
    This is used for the Application View section to group Rally items by AHA delivery teams.
    """
    # Handle the case where rally is empty or has no required columns
    if rally.empty or 'Lead Team' not in rally.columns or 'Rally Lead Team' not in rally.columns:
        merged = aha.copy()
        # Add Rally columns with NaN values
        rally_columns = ['ID', 'Name', 'Owner', 'Release', 'State', 'Planned End Date',
                        '% Done By Story Plan Estimate', 'Preliminary Estimate Value',
                        'Rally Cost Estimate', 'Lead Team', 'Rally Lead Team', 'Rally Point Estimate', 'Artifact Type',
                        'Solution Capability', 'Feature']
        for col in rally_columns:
            if col not in merged.columns:
                merged[col] = pd.NA
    else:
        # Merge using MAPPED 'Lead Team' (not unmapped 'Rally Lead Team')
        # This matches Rally's mapped team names with AHA's 'Impacts Delivery team' names
        
        # Debug: Show what we're trying to match
        print(f"\n[DEBUG MERGE] AHA Delivery Teams: {sorted(aha['Impacts Delivery team'].unique().tolist())}")
        print(f"[DEBUG MERGE] Rally Mapped Lead Teams: {sorted(rally['Lead Team'].unique().tolist())}")
        
        merged = pd.merge(left=aha, right=rally, how='left', left_on='Impacts Delivery team', right_on='Lead Team')
        
        # Debug: Show merge results
        matched_count = merged[merged['ID'].notna()].shape[0]
        print(f"[DEBUG MERGE] Matched rows (AHA + Rally): {matched_count}")
        
        # Drop duplicate columns
        if 'Lead Team' in merged.columns:
            merged = merged.drop(columns=['Lead Team'])
        if 'Impact Type' in merged.columns:
            merged = merged.drop(columns=['Impact Type'])
        
        # Rally data has 'Preliminary Estimate Value', but output needs 'Rally Point Estimate'
        if 'Rally Point Estimate' not in merged.columns:
            merged['Rally Point Estimate'] = merged.get('Preliminary Estimate Value', pd.NA)
   
        # Creating an additional df of Rally items that don't match any AHA delivery team
        unmatched_rally = rally[~rally['Lead Team'].isin(aha['Impacts Delivery team']) & rally['Lead Team'].notna()]
        
        # Debug: Show unmatched Rally items
        if not unmatched_rally.empty:
            print(f"[DEBUG MERGE] Unmatched Rally teams (going to 'Other'): {sorted(unmatched_rally['Lead Team'].unique().tolist())}")
            print(f"[DEBUG MERGE] Unmatched Rally count: {len(unmatched_rally)} items")
        
        unmatched_rally = unmatched_rally.rename(columns={
            'Lead Team': 'Impacts Delivery team'
        })

        # Making the AHA columns NA for unmatched Rally items
        unmatched_rally['Impact Cost'] = pd.NA
        unmatched_rally['Oversight Approved Amount'] = pd.NA
        unmatched_rally['Desired completion date'] = pd.NA
        
        # Create Rally Point Estimate in unmatched_rally to match merged columns
        if 'Rally Point Estimate' not in unmatched_rally.columns:
            unmatched_rally['Rally Point Estimate'] = unmatched_rally.get('Preliminary Estimate Value', pd.NA)
        
        unmatched_rally = unmatched_rally[merged.columns]
        
        # Concatenate matched and unmatched Rally items
        merged = pd.concat([merged, unmatched_rally], ignore_index=True)

    # Create Task ID column from ID for Application View compatibility
    if 'ID' in merged.columns and 'Task ID' not in merged.columns:
        merged['Task ID'] = merged['ID']
    
    # Ensure Work Breakdown column exists (will be used in Application View)
    if 'Impacts Delivery team' in merged.columns and 'Work Breakdown' not in merged.columns:
        merged['Work Breakdown'] = merged['Impacts Delivery team']
    
    merged['Keep Raw'] = 'Y'
    return merged

def merge_template(template, rally_data):
    """
    No longer merges based on delivery teams. Simply returns the template as-is.
    Rally data will be inserted directly under 'Case Install Ready' in clean_template().
    """
    # Just return the template - we'll handle Rally insertion in clean_template()
    return template

def build_application_view(merged_data, apps_for_application_view):
    """
    Builds the Application View section using original Rally grouping logic.
    
    Logic (from get_rally_data_hcp):
    1. For each capability, look at ALL its features
    2. Group features by their unique 'Impacts Delivery team' values
    3. Create one capability instance per unique team found in features
    4. Under each capability instance, add only features with that team
    5. Items with no AHA team match go to "Other"
    
    Args:
        merged_data: DataFrame with Rally data merged to AHA data (from merge_aha_rally)
        apps_for_application_view: DataFrame with AHA 'Impacts Delivery team' values
    
    Returns:
        DataFrame with Application View structure
    """
    application_view_rows = [{'Work Breakdown': '**Application View**', 'Level': 2}]

    if apps_for_application_view is None or apps_for_application_view.empty:
        application_view_rows.append({
        'Work Breakdown': 'Other',
        'Level': 3
    })
    
    if merged_data is None or merged_data.empty or apps_for_application_view is None or apps_for_application_view.empty:
        return pd.DataFrame(application_view_rows)
    
    # Get all Rally items (capabilities and features)
    rally_items = merged_data[merged_data['Task ID'].astype(str).str.match(r'^[CF]\d+')].copy()
    
    # If there are no Rally items (Task IDs are all NA), still show the AHA delivery teams
    if rally_items.empty:
        print(f"\n[DEBUG APP VIEW] No Rally items found, creating Application View with AHA teams only")
        aha_teams = apps_for_application_view['Impacts Delivery team'].dropna().unique()
        
        for app_name in aha_teams:
            # Add the delivery team as Level 3 parent (empty, ready for future Rally data)
            application_view_rows.append({
                'Work Breakdown': f'{app_name}',
                'Level': 3
            })
        
        # Always add "Other" section
        application_view_rows.append({
            'Work Breakdown': 'Other',
            'Level': 3
        })
        
        return pd.DataFrame(application_view_rows)
    
    print(f"\n[DEBUG APP VIEW] Building Application View with {len(rally_items)} Rally items")
    
    # Separate capabilities and features
    capabilities = rally_items[rally_items['Task ID'].str.startswith('C')].copy()
    features = rally_items[rally_items['Task ID'].str.startswith('F')].copy()
    
    print(f"[DEBUG APP VIEW] Capabilities: {len(capabilities)}, Features: {len(features)}")
    
    # Regroup using original logic: one capability instance per unique feature Rally Lead Team
    final_rows = []
    
    for _, cap in capabilities.iterrows():
        cap_id = cap['Task ID']
        
        # Get all features belonging to this capability
        children = features[features.get('Solution Capability', '') == cap_id].copy()
        
        # Get unique Rally Lead Teams from the features (NOT the mapped team)
        unique_rally_teams = children['Rally Lead Team'].dropna().unique()
        
        if len(unique_rally_teams) == 0:
            # No features or no team info - add capability as-is
            final_rows.append(cap.to_dict())
        else:
            # Create one capability instance per unique Rally Lead Team in features
            for rally_team in unique_rally_teams:
                cap_copy = cap.copy()
                # Set the capability's Rally Lead Team to match the features
                cap_copy['Rally Lead Team'] = rally_team
                
                # Get features with this Rally Lead Team
                matching_features = children[children['Rally Lead Team'] == rally_team]
                
                # The capability inherits the mapped 'Impacts Delivery team' from its features
                if not matching_features.empty:
                    cap_copy['Impacts Delivery team'] = matching_features.iloc[0]['Impacts Delivery team']
                
                final_rows.append(cap_copy.to_dict())
                final_rows.extend(matching_features.to_dict('records'))
    
    # Create regrouped DataFrame
    regrouped = pd.DataFrame(final_rows)
    
    if regrouped.empty:
        return pd.DataFrame(application_view_rows)
    
    print(f"[DEBUG APP VIEW] After regrouping by team: {len(regrouped)} rows")
    print(f"[DEBUG APP VIEW] Team distribution: {regrouped['Impacts Delivery team'].value_counts().to_dict()}")
    
    # Now build Application View structure from regrouped data
    # For each AHA delivery team, add team header and items
    aha_teams = apps_for_application_view['Impacts Delivery team'].dropna().unique()
    
    for app_name in aha_teams:
        # Add the delivery team as Level 3 parent
        application_view_rows.append({
            'Work Breakdown': f'{app_name}',
            'Level': 3
        })
        
        # Get regrouped items for this team
        team_items = regrouped[regrouped['Impacts Delivery team'] == app_name].copy().reset_index(drop=True)
        
        if team_items.empty:
            continue
        
        print(f"[DEBUG APP VIEW] {app_name}: {len(team_items)} items")
        
        # Process sequentially: each capability followed by its features
        i = 0
        while i < len(team_items):
            row = team_items.iloc[i]
            
            # If this is a capability, add it and its features
            if row['Task ID'].startswith('C'):
                # Look ahead for features belonging to this capability
                j = i + 1
                feature_rows = []
                all_features_done = True
                has_features = False
                
                while j < len(team_items):
                    next_row = team_items.iloc[j]
                    # If next item is a feature (F*), add it at Level 5
                    if next_row['Task ID'].startswith('F'):
                        has_features = True
                        feature_status = next_row.get('State', next_row.get('Status'))
                        if feature_status != 'Done':
                            all_features_done = False
                        
                        feat_row = {
                            'Work Breakdown': f"{next_row['Task ID']} - {next_row.get('Name', '')}" if pd.notna(next_row.get('Name')) else next_row['Task ID'],
                            'Task ID': next_row['Task ID'],
                            'Rally Lead Team': next_row.get('Rally Lead Team'),
                            'Assigned To': next_row.get('Owner'),
                            'Release': next_row.get('Release'),
                            # 'Actual End Date': next_row.get('Planned End Date', pd.NA),
                            'Planned End Date (Rally)': next_row.get('Planned End Date', pd.NA),
                            'Planned End Date': next_row.get('Planned End Date'),
                            'Status': feature_status,
                            '% Complete': next_row.get('% Done By Story Plan Estimate', next_row.get('% Complete')),
                            'Rally Point Estimate': next_row.get('Rally Point Estimate'),
                            'Rally Cost Estimate': next_row.get('Rally Cost Estimate'),
                            'Level': 5
                        }
                        feature_rows.append(feat_row)
                        j += 1
                    else:
                        # Next item is another capability, stop looking for features
                        break
                
                # Determine capability status: "Done" if all children are Done, otherwise use its own status
                cap_status = 'Done' if (has_features and all_features_done) else row.get('State', row.get('Status'))
                
                # Add capability at Level 4
                cap_row = {
                    'Work Breakdown': f"{row['Task ID']} - {row.get('Name', '')}" if pd.notna(row.get('Name')) else row['Task ID'],
                    'Task ID': row['Task ID'],
                    'Rally Lead Team': row.get('Rally Lead Team'),
                    'Assigned To': row.get('Owner'),
                    'Release': row.get('Release'),
                    # 'Actual End Date': row.get('Planned End Date', pd.NA),
                    'Planned End Date (Rally)': row.get('Planned End Date', pd.NA),
                    'Planned End Date': row.get('Planned End Date'),
                    'Status': cap_status,
                    '% Complete': row.get('% Done By Story Plan Estimate', row.get('% Complete')),
                    'Rally Point Estimate': row.get('Rally Point Estimate'),
                    'Rally Cost Estimate': row.get('Rally Cost Estimate'),
                    'Level': 4
                }
                application_view_rows.append(cap_row)
                
                # Add all feature rows
                application_view_rows.extend(feature_rows)
                
                i = j
            else:
                # Standalone feature (no parent capability in this team)
                i += 1
    
    # Handle "Other" section for unmatched items (items not in any AHA team)
    # Always add "Other" section as a catch-all, even if empty now
    unmatched_items = regrouped[~regrouped['Impacts Delivery team'].isin(aha_teams)].copy().reset_index(drop=True)
    
    print(f"[DEBUG APP VIEW] Other: {len(unmatched_items)} unmatched items")
    if not unmatched_items.empty:
        print(f"[DEBUG APP VIEW]   Task IDs: {unmatched_items['Task ID'].tolist()}")
    
    # Always add "Other" header regardless of whether there are items
    application_view_rows.append({
        'Work Breakdown': 'Other',
        'Level': 3
    })
    
    # Process unmatched items sequentially (if any exist)
    if not unmatched_items.empty:
        i = 0
        while i < len(unmatched_items):
            row = unmatched_items.iloc[i]
            
            if row['Task ID'].startswith('C'):
                # Look ahead for features
                j = i + 1
                feature_rows = []
                all_features_done = True
                has_features = False
                
                while j < len(unmatched_items):
                    next_row = unmatched_items.iloc[j]
                    if next_row['Task ID'].startswith('F'):
                        has_features = True
                        feature_status = next_row.get('State', next_row.get('Status'))
                        if feature_status != 'Done':
                            all_features_done = False
                        
                        feat_row = {
                            'Work Breakdown': f"{next_row['Task ID']} - {next_row.get('Name', '')}" if pd.notna(next_row.get('Name')) else next_row['Task ID'],
                            'Task ID': next_row['Task ID'],
                            'Rally Lead Team': next_row.get('Rally Lead Team'),
                            'Assigned To': next_row.get('Owner'),
                            'Release': next_row.get('Release'),
                            # 'Actual End Date': next_row.get('Planned End Date', pd.NA),
                            'Planned End Date (Rally)': next_row.get('Planned End Date', pd.NA),
                            'Planned End Date': next_row.get('Planned End Date'),
                            'Status': feature_status,
                            '% Complete': next_row.get('% Done By Story Plan Estimate', next_row.get('% Complete')),
                            'Rally Point Estimate': next_row.get('Rally Point Estimate'),
                            'Rally Cost Estimate': next_row.get('Rally Cost Estimate'),
                            'Level': 5
                        }
                        feature_rows.append(feat_row)
                        j += 1
                    else:
                        break
                
                # Determine capability status: "Done" if all children are Done, otherwise use its own status
                cap_status = 'Done' if (has_features and all_features_done) else row.get('State', row.get('Status'))
                
                # Add capability at Level 4
                cap_row = {
                    'Work Breakdown': f"{row['Task ID']} - {row.get('Name', '')}" if pd.notna(row.get('Name')) else row['Task ID'],
                    'Task ID': row['Task ID'],
                    'Rally Lead Team': row.get('Rally Lead Team'),
                    'Assigned To': row.get('Owner'),
                    'Release': row.get('Release'),
                    # 'Actual End Date': row.get('Planned End Date', pd.NA),
                    'Planned End Date (Rally)': row.get('Planned End Date', pd.NA),
                    'Planned End Date': row.get('Planned End Date'),
                    'Status': cap_status,
                    '% Complete': row.get('% Done By Story Plan Estimate', row.get('% Complete')),
                    'Rally Point Estimate': row.get('Rally Point Estimate'),
                    'Rally Cost Estimate': row.get('Rally Cost Estimate'),
                    'Level': 4
                }
                application_view_rows.append(cap_row)
                
                # Add all feature rows
                application_view_rows.extend(feature_rows)
                
                i = j
            else:
                i += 1
    
    # Build final DataFrame
    result_df = pd.DataFrame(application_view_rows)
    
    # Debug: Show full Application View structure
    print(f"\n[DEBUG APP VIEW] Final DataFrame shape: {result_df.shape}")
    print(f"[DEBUG APP VIEW] Level breakdown:")
    if not result_df.empty:
        for level in sorted(result_df['Level'].dropna().unique()):
            count = len(result_df[result_df['Level'] == level])
            print(f"  Level {level}: {count} rows")
        
        print(f"\n[DEBUG APP VIEW] Full Application View structure:")
        for idx, row in result_df.iterrows():
            level = int(row.get('Level', 0)) if pd.notna(row.get('Level')) else 0
            indent = "  " * (level - 2)
            task_id = row.get('Task ID', '')
            task_str = f" [{task_id}]" if task_id else ""
            print(f"{indent}L{level}: {row.get('Work Breakdown', '')}{task_str}")
    
    return result_df

def clean_template(df, name, st, os_approved, project_type, prj, go_live, apps=None, rally_data=None, merged_data=None, bdl=None, rdl=None, idea=None):
    """"
    Rules to clean the template and insert Rally data directly under 'Case Install Ready'.
    For Application View section, uses merged_data (AHA + Rally merged by team).
    """
    # Keep all rows from template (Level 1, 2, 3)
    final = df.copy()
    
    # Ensure Task ID column exists and is string type
    if 'Task ID' not in final.columns:
        final['Task ID'] = ''
    final['Task ID'] = final['Task ID'].fillna('').astype(str)
    
    # Ensure 'Planned End Date (Rally)' column exists (required for later column selection)
    if 'Planned End Date (Rally)' not in final.columns:
        final['Planned End Date (Rally)'] = pd.NA
    
    # Insert Rally data under 'Case Install Ready'
    if rally_data is not None and not rally_data.empty:
        # Find the index of 'Case Install Ready'
        # case_install_mask = final['Work Breakdown'] == 'Case Install Ready'
        functional_capability_mask = final['Work Breakdown'] == 'Functional Capabilities (do not delete)'
        # if case_install_mask.any():
        #     case_install_idx = final[case_install_mask].index[0]
        if functional_capability_mask.any():
            fc_install_idx = final[functional_capability_mask].index[0]
            # Prepare Rally rows for insertion
            rally_rows = []
            for idx, row in rally_data.iterrows():
                rally_row = {
                    'Work Breakdown': f"{row['ID']} - {row['Name']}" if pd.notna(row.get('Name')) else row['ID'],
                    'Task ID': row['ID'],
                    'Rally Lead Team': row.get('Rally Lead Team', '') if row['ID'].startswith('F') else '',  # Only for features
                    'Assigned To': row.get('Owner', pd.NA),
                    'Release': row.get('Release', pd.NA),
                    # 'Actual End Date': row.get('Planned End Date', pd.NA),
                    'Planned End Date (Rally)': row.get('Planned End Date', pd.NA),
                    'Planned End Date': row.get('Planned End Date', pd.NA),
                    'Status': row.get('State', pd.NA),
                    '% Complete': row.get('% Done By Story Plan Estimate', pd.NA),
                    'Rally Point Estimate': row.get('Preliminary Estimate Value', pd.NA),
                    'Rally Cost Estimate': row.get('Rally Cost Estimate', pd.NA),
                    'Level': 4 if row['ID'].startswith('C') else 5  # Capabilities at Level 4, Features at Level 5
                }
                rally_rows.append(rally_row)
            
            # Create DataFrame from Rally rows
            rally_df = pd.DataFrame(rally_rows)
            
            # Insert Rally data after 'Case Install Ready'
            final = pd.concat([
                final.iloc[:fc_install_idx + 1],
                rally_df,
                final.iloc[fc_install_idx + 1:]
            ], ignore_index=True)
    
    # Work Breakdown is already formatted during Rally insertion above
    # saving the project plan name with the st and the user inputted name
    st_name = st + ' - ' + name

    # dropping any unnecessary columns that exist (Name shouldn't exist anymore)
    columns_to_drop = ['Keep Raw', 'Name']
    columns_to_drop = [col for col in columns_to_drop if col in final.columns]
    if columns_to_drop:
        final = final.drop(columns=columns_to_drop)
    
    # Ensure all required Rally columns exist
    rally_columns_needed = ['Rally Lead Team', 'Rally Point Estimate', 'Rally Cost Estimate']
    for col in rally_columns_needed:
        if col not in final.columns:
            final[col] = pd.NA
    
    # setting the first row to contain the project name
    final.loc[0, 'Work Breakdown'] = st_name

    # converting the Rally Cost Estimate column to numeric
    final['Rally Cost Estimate'] = pd.to_numeric(
        final['Rally Cost Estimate'], errors='coerce'
    )

    # converting the % complete column to numeric
    final['% Complete'] = (
        pd.to_numeric(final['% Complete'], errors='coerce').fillna(0)
    )
    
    # Set % Complete to null (pd.NA) for Alpha and Master rows
    final.loc[final['Work Breakdown'].str.lower().isin(['alpha', 'master']), '% Complete'] = pd.NA

    # Select and reorder columns
    final = final[['Work Breakdown', 'Task ID', 'Rally Lead Team','Assigned To', 'Release', 'Planned End Date (Rally)', 'Planned End Date', 'Status', '% Complete', 'Rally Point Estimate', 'Rally Cost Estimate', 'Level']]

    final.loc[final['Task ID'] == '', 'Rally Lead Team'] = pd.NA

    # Handle empty apps DataFrame
    # Preserve original apps DataFrame for Application View section before converting to list
    apps_for_application_view = None
    financial_apps = None
    if not apps.empty and 'Impacts Delivery team' in apps.columns:
        apps_for_application_view = apps.copy()  # Keep a copy for later use
        financial_apps = apps[['Impacts Delivery team', 'Impact Cost']].rename(columns={'Impacts Delivery team': 'Impacted Applications', 'Impact Cost': 'Aha OS Approved Amount'})
        apps = apps['Impacts Delivery team'].dropna().unique().tolist()
    else:
        apps = []

    # ORIGINAL CODE (commented out):
    # # adding in optics data if available
    # optics = get_optics(prj, st)
    #
    # if optics is not None:
    #     final = final.merge(optics, left_on='Work Breakdown', right_on='task_name_mapped', how='left')
    # else:
    #     final['Actuals'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)
    #     final['ETCs'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)
    #     final['EACs'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)
    
    # NEW CODE: Only fetch optics if we have a valid strategic theme
    # if st and st != 'No ST' and st.startswith('ST'):
    #     optics = get_optics(prj, st)
    # else:
    #     optics = None

    # if optics is not None:
    #     final = final.merge(optics, left_on='Work Breakdown', right_on='task_name_mapped', how='left')
    # else:
    #     final['Actuals Est (Hours x Rate)'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)
    #     final['ETCs'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)
    #     final['EACs'] = np.where(final['Work Breakdown'].isin(apps), 0, np.nan)

    final = final[['Work Breakdown', 'Task ID', 'Rally Lead Team','Assigned To', 'Release', 'Planned End Date (Rally)', 'Planned End Date', 'Status', '% Complete', 'Rally Point Estimate', 'Rally Cost Estimate', 'Level']]

    # rows_to_drop = ['Quote Ready', 'Fulfillment Ready', 'Billing Ready', 'Finance Ready', 'Claims Ready', 'Consumer Services / Portal Ready', 'Reporting Ready']

    # drop rows where Work Breakdown is in rows_to_drop and Level equals the next row's Level
    #current_level = final['Level']
    #next_level = current_level.shift(-1)
    #drop_mask = final['Work Breakdown'].isin(rows_to_drop) & (current_level == next_level)
    #final = final[~drop_mask].reset_index(drop=True)

    # set parent status based on children: 'In Progress' if any child is in progress, 'Done' if all children are done
    # iterate from bottom to top (highest level to lowest) to propagate status upward
    max_level = final['Level'].max()
    for level in range(max_level, 0, -1):
        i = 0
        while i < len(final):
            if final.iloc[i]['Level'] == level:
                # find all children (rows immediately following with higher level)
                children_indices = []
                j = i + 1
                while j < len(final) and final.iloc[j]['Level'] > level:
                    if final.iloc[j]['Level'] == level + 1:
                        children_indices.append(j)
                    j += 1
                
                # if there are children, check their statuses
                if children_indices:
                    children_statuses = [final.iloc[idx]['Status'] for idx in children_indices]
                    
                    # if any child is 'In Progress', set parent to 'In Progress'
                    if any(status == 'In Progress' for status in children_statuses):
                        final.loc[i, 'Status'] = 'In Progress'
                    # if all children are 'Done', set parent to 'Done'
                    elif all(status == 'Done' for status in children_statuses):
                        final.loc[i, 'Status'] = 'Done'
                
                i = j if children_indices else i + 1
            else:
                i += 1

    # set the first row to contain the sum of Actuals Est (Hours x Rate), ETCs, and EACs columns
    # final.loc[0, 'Actuals Est (Hours x Rate)'] = final['Actuals Est (Hours x Rate)'].sum(skipna=True)
    # final.loc[0, 'ETCs'] = final['ETCs'].sum(skipna=True)
    # final.loc[0, 'EACs'] = final['EACs'].sum(skipna=True)

    # create three new rows at the end for test refresh dates (alpha and master)
    # new_rows = pd.DataFrame([
    #     {'Work Breakdown': 'Test Refresh Dates', 'Level': 3},
    #     {'Work Breakdown': 'Alpha', 'Planned End Date' : '06/22/26', 'Level': 4, 'Actual End Date' : '06/22/26'},
    #     {'Work Breakdown': 'Master', 'Planned End Date' : '01/14/26', 'Level': 4, 'Actual End Date' : '01/14/26'}
    # ])
    # final = pd.concat([final, new_rows], ignore_index=True)
    
    # Build Application View section using separate function
    # Uses merged_data (AHA + Rally merged by team) for team-based grouping
    print(f"\n[DEBUG CLEAN_TEMPLATE] Before build_application_view:")
    print(f"  merged_data is None: {merged_data is None}")
    print(f"  merged_data empty: {merged_data.empty if merged_data is not None else 'N/A'}")
    print(f"  merged_data shape: {merged_data.shape if merged_data is not None else 'N/A'}")
    print(f"  apps_for_application_view is None: {apps_for_application_view is None}")
    print(f"  apps_for_application_view empty: {apps_for_application_view.empty if apps_for_application_view is not None else 'N/A'}")
    if merged_data is not None and not merged_data.empty:
        print(f"  merged_data columns: {list(merged_data.columns)}")
        print(f"  merged_data Task ID sample: {merged_data['Task ID'].head(10).tolist() if 'Task ID' in merged_data.columns else 'No Task ID column'}")
    application_view_df = build_application_view(merged_data, apps_for_application_view)
    final = pd.concat([final, application_view_df], ignore_index=True)
    
    # Add Financials section
    financials_row = pd.DataFrame([{'Work Breakdown': 'Financials', 'Level': 2}])
    final = pd.concat([final, financials_row], ignore_index=True)

    final = final[['Work Breakdown', 'Task ID', 'Rally Lead Team','Assigned To', 'Release', 'Planned End Date (Rally)', 'Planned End Date', 'Status', '% Complete', 'Rally Point Estimate', 'Rally Cost Estimate', 'Level']]

    # Add optics financial section (always include structure, even if no data yet)
    # Only fetch data if both st and prj are valid and prj is in correct format (PRJxxxxxx)
    import re
    prj_valid = prj and re.match(r'^PRJ\d+$', prj.strip(), re.IGNORECASE)
    
    if st and st != 'No ST' and st.startswith('ST') and prj_valid:
        optics = get_optics_financials(prj, st)
    else:
        optics = None

    # Always create the Optics section structure (header and total)
    # Create header row with column names at Level 3
    header_row = pd.DataFrame([{
        'Work Breakdown': 'Task Name',
        'Task ID': 'Actuals',
        'Rally Lead Team': 'ETCs',
        'Assigned To': 'EACs',
        'Release': '% Burn',
        'Planned End Date (Rally)': pd.NA,
        'Planned End Date': pd.NA,
        'Status': pd.NA,
        '% Complete': pd.NA,
        'Rally Point Estimate': pd.NA,
        'Rally Cost Estimate': pd.NA,
        'Level': 3
    }])
    
    # Create data rows at Level 4 (only if we have optics data)
    optics_df = pd.DataFrame()
    if optics is not None and not optics.empty:
        optics_rows = []
        for _, row in optics.iterrows():
            optics_rows.append({
                'Work Breakdown': row['Task Name'],
                'Task ID': str(int(row['Actuals'])) if pd.notna(row['Actuals']) else '',
                'Rally Lead Team': str(int(row['ETCs'])) if pd.notna(row['ETCs']) else '',
                'Assigned To': str(int(row['EACs'])) if pd.notna(row['EACs']) else '',
                'Release': str(int(row['% Burn'])) if pd.notna(row['% Burn']) else '',
                # 'Actual End Date': pd.NA,
                'Planned End Date (Rally)': pd.NA,
                'Planned End Date': pd.NA,
                'Status': pd.NA,
                '% Complete': pd.NA,
                'Rally Point Estimate': pd.NA,
                'Rally Cost Estimate': pd.NA,
                'Level': 4
            })
        optics_df = pd.DataFrame(optics_rows)
    
    # Calculate totals for Optics Total row
    if optics is not None and not optics.empty:
        total_actuals = optics['Actuals'].sum(skipna=True)
        total_etcs = optics['ETCs'].sum(skipna=True)
        total_eacs = optics['EACs'].sum(skipna=True)
        total_burn = (total_actuals / total_eacs) if total_eacs != 0 else 0
    else:
        total_actuals = 0
        total_etcs = 0
        total_eacs = 0
        total_burn = 0
    
    # Create Optics Total row at Level 3 (always included)
    optics_total_row = pd.DataFrame([{
        'Work Breakdown': 'Optics Total',
        'Task ID': str(int(total_actuals)) if total_actuals > 0 else '',
        'Rally Lead Team': str(int(total_etcs)) if total_etcs > 0 else '',
        'Assigned To': str(int(total_eacs)) if total_eacs > 0 else '',
        'Release': str(round(total_burn * 100, 2)) + '%' if total_burn > 0 else '',
        'Planned End Date (Rally)': pd.NA,
        'Planned End Date': pd.NA,
        'Status': pd.NA,
        '% Complete': pd.NA,
        'Rally Point Estimate': pd.NA,
        'Rally Cost Estimate': pd.NA,
        'Level': 3
    }])
    
    # Concatenate: header, data rows (if any), then Optics Total to final
    if not optics_df.empty:
        final = pd.concat([final, header_row, optics_df, optics_total_row], ignore_index=True)
    else:
        # Even with no data, include header and total rows for structure
        final = pd.concat([final, header_row, optics_total_row], ignore_index=True)

    # Always add 'Impacted Applications' and 'Aha Total' rows at Level 3 to Financials section
    header_row = pd.DataFrame([{
        'Work Breakdown': 'Impacted Applications',
        'Task ID': pd.NA,
        'Rally Lead Team': pd.NA,
        'Assigned To': 'Aha OS Approved Amount',
        'Release': pd.NA,
        'Planned End Date (Rally)': pd.NA,
        'Planned End Date': pd.NA,
        'Status': pd.NA,
        '% Complete': pd.NA,
        'Rally Point Estimate': pd.NA,
        'Rally Cost Estimate': pd.NA,
        'Level': 3
    }])

    aha_rows = []
    if financial_apps is not None and not financial_apps.empty:
        for _, row in financial_apps.iterrows():
            aha_rows.append({
                'Work Breakdown': row['Impacted Applications'],
                'Task ID': pd.NA,
                'Rally Lead Team': pd.NA,
                'Assigned To': str(int(row['Aha OS Approved Amount'])) if pd.notna(row['Aha OS Approved Amount']) else '',
                'Release': pd.NA,
                'Planned End Date (Rally)': pd.NA,
                'Planned End Date': pd.NA,
                'Status': pd.NA,
                '% Complete': pd.NA,
                'Rally Point Estimate': pd.NA,
                'Rally Cost Estimate': pd.NA,
                'Level': 4
            })
        aha_df = pd.DataFrame(aha_rows)
        total_aha_os_approved = financial_apps['Aha OS Approved Amount'].sum(skipna=True)
    else:
        aha_df = pd.DataFrame()
        total_aha_os_approved = 0

    aha_total_row = pd.DataFrame([{
        'Work Breakdown': 'Aha Total',
        'Task ID': pd.NA,
        'Rally Lead Team': pd.NA,
        'Assigned To': str(int(total_aha_os_approved)) if total_aha_os_approved else '',
        'Release': pd.NA,
        'Planned End Date (Rally)': pd.NA,
        'Planned End Date': pd.NA,
        'Status': pd.NA,
        '% Complete': pd.NA,
        'Rally Point Estimate': pd.NA,
        'Rally Cost Estimate': pd.NA,
        'Level': 3
    }])

    # Concatenate header, data rows (if any), then Aha Total to final
    final = pd.concat([final, header_row, aha_df, aha_total_row], ignore_index=True)

    # Replace RDL and BDL placeholders with actual names from Assigned To column BEFORE milestone logic
    # This ensures milestone matching works correctly for these rows
    # if bdl:
    #     final['Work Breakdown'] = final['Work Breakdown'].replace('     BDL', bdl)
    # if rdl:
    #     final['Work Breakdown'] = final['Work Breakdown'].replace('     RDL', rdl)

    # Apply milestone dates as final step (after all DataFrame operations)
    milestones_0 = ['Execution', 'Claims Ready', 'Operations Ready', 'Functional Capabilities (do not delete)', 'PET Testing', 'GNG Checkpoint', 'GNG Final Go Live', 'Go To Production Plan']
    milestones_120 = ['Quote Ready']
    milestones_90 = ['Case Install Ready', 'Configuration Ready', 'Enrollment Ready', 'Finance Ready'] + apps
    milestones_60 = ['Consumer Services / Portal Ready']
    milestones_30 = ['Fulfillment Ready', 'ID Card Ready', 'Member Documents Ready']
    milestones_23 = ['Billing Ready']
    milestones_plus_30 = ['Reporting Ready']
    # milestones_plus_275 = ['Renewal Ready', 'Assumed Renewal', 'Shopping']
    # milestones_plus_255 = ['Case Selection']
    # milestones_plus_245 = ['Renewal Package']
    milestones_alpha = ['Alpha']
    milestones_master = ['Master']

    go_live_dt = pd.to_datetime(go_live)

    # Helper function to check if Work Breakdown matches milestone (exact match only)
    def matches_milestone(work_breakdown, milestone_list):
        if pd.isna(work_breakdown):
            return False
        wb_str = str(work_breakdown).strip()
        return wb_str in milestone_list

    # Apply milestone dates using exact string matching
    for idx, row in final.iterrows():
        wb = row['Work Breakdown']
        
        if matches_milestone(wb, milestones_0):
            final.at[idx, 'Planned End Date'] = go_live_dt
        elif matches_milestone(wb, milestones_120):
            final.at[idx, 'Planned End Date'] = go_live_dt - pd.DateOffset(months=4)
        elif matches_milestone(wb, milestones_90):
            final.at[idx, 'Planned End Date'] = go_live_dt - pd.DateOffset(months=3)
        elif matches_milestone(wb, milestones_60):
            final.at[idx, 'Planned End Date'] = go_live_dt - pd.DateOffset(months=2)
        elif matches_milestone(wb, milestones_30):
            final.at[idx, 'Planned End Date'] = go_live_dt - pd.DateOffset(months=1)
        elif matches_milestone(wb, milestones_23):
            final.at[idx, 'Planned End Date'] = go_live_dt - pd.DateOffset(days=23)
        elif matches_milestone(wb, milestones_plus_30):
            final.at[idx, 'Planned End Date'] = go_live_dt + pd.DateOffset(months=1)
        # elif matches_milestone(wb, milestones_plus_275):
        #     final.at[idx, 'Planned End Date'] = go_live_dt + pd.DateOffset(days=275)
        # elif matches_milestone(wb, milestones_plus_255):
        #     final.at[idx, 'Planned End Date'] = go_live_dt + pd.DateOffset(days=255)
        # elif matches_milestone(wb, milestones_plus_245):
        #     final.at[idx, 'Planned End Date'] = go_live_dt + pd.DateOffset(days=245)
        elif matches_milestone(wb, milestones_alpha):
            final.at[idx, 'Planned End Date'] = pd.to_datetime('2026-06-22')
        elif matches_milestone(wb, milestones_master):
            final.at[idx, 'Planned End Date'] = pd.to_datetime('2026-01-14')
        else:
            final.at[idx, 'Planned End Date'] = np.nan

    # Clear dates for all Finance section rows (Financials and all children)
    financials_idx = final[final['Work Breakdown'] == 'Financials'].index
    if len(financials_idx) > 0:
        financials_start = financials_idx[0]
        # Find the end of Financials section (next Level 2 or end of dataframe)
        financials_end = len(final)
        for idx in range(financials_start + 1, len(final)):
            if final.iloc[idx]['Level'] <= 2:
                financials_end = idx
                break
        # Clear all date columns for Financials section
        final.loc[financials_start:financials_end-1, 'Planned End Date'] = pd.NA
        final.loc[financials_start:financials_end-1, 'Planned End Date (Rally)'] = pd.NA

    final.loc[final["Work Breakdown"] == "Aha Toggled to Approved - Planning", "Task ID"] = idea

    if prj.startswith("PRJ"):
        final.loc[final["Work Breakdown"] == "       Tech PRJ Created", "Task ID"] = prj
    else:
        final.loc[final["Work Breakdown"] == "       PRJ added to AHA", "Task ID"] = "PRJ must be in the Aha"
    
    final['Start Date'] = pd.NA
    final['Notes'] = pd.NA
    final = final[['Work Breakdown', 'Task ID', 'Rally Lead Team','Assigned To', 'Release', 'Start Date', 'Planned End Date (Rally)', 'Planned End Date', 'Status', '% Complete', 'Notes', 'Rally Point Estimate', 'Rally Cost Estimate',  'Level']]
    # saving the final project plan as a csv that the user can download
    return final

# --------------------------------- PLAN BUILDER ----------------------------------

def build_plan(plan_params):
    """
    Creates the final plan with the user inputs and the above functions.
    """
    try:
        # default project plan parameters if nothing is entered
        idea = plan_params.get("plan idea", "PSTRATEGIC-I-2278")
        project_type = plan_params.get("project type", "Foundational-PCP Assignment")
        idea_name = plan_params.get("idea name", "PCP Assignment 2025 carry over")
        bdl = plan_params.get("BDL", config.DEFAULT_BDL)
        rdl = plan_params.get("RDL", config.DEFAULT_RDL)
        
        print(f"Building plan for idea: {idea}, project_type: {project_type}")
        
        # running the above functions to create the full version of the project plan based on the user inputted parameters
        template = get_template(project_type, bdl, rdl)
        if template is None or template.empty:
            raise ValueError("Failed to load project template")
        
        ltm = get_lead_team_mapping()
        aha_data, os_approved, rally_theme, tag, prj, go_live = get_aha_data(idea)
        
        # # Check if AHA data was retrieved successfully
        # if aha_data is None or aha_data.empty:
        #     raise ValueError(f"Insufficient AHA data for idea {idea}. Please ensure the idea exists and has delivery team impacts (Development or Test Only) configured in AHA before generating a project plan.")
        
        # Check for strategic theme requirement
        if rally_theme == 'No ST' or not rally_theme or not rally_theme.startswith('ST'):
            raise ValueError(f"Cannot create project plan without a valid strategic theme. The Aha idea '{idea}' does not have an associated strategic theme (ST number). Please link the idea to a strategic theme in Aha before generating a project plan.")
        
        # Fetch Rally data for the valid strategic theme
        print(f"AHA data: {len(aha_data) if aha_data is not None else 0} records, OS Approved: {os_approved}, Rally Theme: {rally_theme}")
        print(f"Fetching Rally data for strategic theme: {rally_theme}")
        
        try:
            rally_data = get_rally_data_hcp(rally_theme, ltm)
        except Exception as rally_error:
            print(f"Error fetching Rally data: {rally_error}")
            print("Falling back to empty Rally data")
            rally_data = pd.DataFrame(columns=[
                'ID', 'Name', 'Owner', 'Release', 'State', 'Planned End Date',
                '% Done By Story Plan Estimate', 'Preliminary Estimate Value',
                'Rally Cost Estimate', 'Lead Team', 'Rally Lead Team', 'Artifact Type',
                'Solution Capability', 'Feature'
            ])

        
        merged = merge_aha_rally(aha_data, rally_data)
        merged_template = merge_template(template, merged)
        final = clean_template(merged_template, idea_name, rally_theme, os_approved, project_type, prj, go_live, aha_data, rally_data, merged, bdl, rdl, idea)
        
        return final
        
    except Exception as e:
        print(f"Error building plan: {e}")
        # Return a basic error DataFrame with all required columns
        return pd.DataFrame({
            'Work Breakdown': [f'Error: {str(e)}'],
            'Task ID': [''],
            'Rally Lead Team': [''],
            'Assigned To': [''],
            'Release': [''],
            'Planned End Date (Rally)': [pd.NA],
            'Planned End Date': [pd.NA],
            'Status': ['Error'],
            '% Complete': [pd.NA],
            'Rally Point Estimate': [pd.NA],
            'Rally Cost Estimate': [pd.NA],
            'Level': [1]
        })