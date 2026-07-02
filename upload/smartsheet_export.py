import os
import certifi
# os.environ['SSL_CERT_FILE'] = certifi.where()
# os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
import upload
import csv
import time
import io
from collections import defaultdict
import pandas as pd
import requests
import pprint
from engine.utils import read_excel_to_dataframe
from config import Config

# Load configuration
config = Config()

WORKSPACE_ID = config.SMARTSHEET_WORKSPACE_ID
TOKEN = config.SMARTSHEET_API_KEY

SMARTSHEET_HEADERS = config.get_smartsheet_headers()
BASE_URL = config.SMARTSHEET_BASE_URL

def smartsheet_upload(file=None, dataframe=None, sheet_name='new plan', tag=None, apps=None):
    # selecting the correct folder
    if tag == 'USP - Commercial Medical Product':
        fid = 3536663918995332
    elif tag == 'USP - Consumer Engagement':
        fid = 5047118017652612
    elif tag == 'USP - Risk Level Enhancements':
        fid = 3446229087610756
    elif tag == 'USP - Specialty':
        fid = 7601283528976260
    elif tag == 'USP - Stepwise':
        fid = 2572551722428292
    else:
        fid = 8409716968712068
    
    # Use DataFrame directly if provided, otherwise read from file
    if dataframe is not None:
        # Use the DataFrame directly - no need to convert to CSV and back
        df = dataframe.copy()
        headers = list(df.columns)
        print(f"[DEBUG] Received DataFrame with columns: {headers}")
        print(f"[DEBUG] DataFrame shape: {df.shape}")
    elif file is not None:
        # opening the saved csv project plan
        with open(file, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            rows = list(reader)
        # converting the saved project plan to a dataframe
        df = pd.DataFrame(rows, columns=headers)
        print(f"[DEBUG] Read from file with columns: {headers}")
    else:
        raise ValueError("Either 'file' or 'dataframe' parameter must be provided")

    # Ensure required columns exist before converting (for plans without Rally data or missing columns)
    if 'Rally Point Estimate' not in df.columns:
        print(f"[DEBUG] WARNING: 'Rally Point Estimate' column missing! Creating it.")
        df['Rally Point Estimate'] = pd.NA
    if 'Rally Cost Estimate' not in df.columns:
        print(f"[DEBUG] WARNING: 'Rally Cost Estimate' column missing! Creating it.")
        df['Rally Cost Estimate'] = pd.NA
    if 'Rally Lead Team' not in df.columns:
        print(f"[DEBUG] WARNING: 'Rally Lead Team' column missing! Creating it.")
        df['Rally Lead Team'] = pd.NA
    if '% Complete' not in df.columns:
        print(f"[DEBUG] WARNING: '% Complete' column missing! Creating it.")
        df['% Complete'] = pd.NA
    if 'Level' not in df.columns:
        print(f"[DEBUG] WARNING: 'Level' column missing! Creating it.")
        df['Level'] = pd.NA
    if 'Aha OS Approved Amt' not in df.columns:
        print(f"[DEBUG] WARNING: 'Aha OS Approved Amt' column missing! Creating it.")
        df['Aha OS Approved Amt'] = pd.NA

    # converting the Rally Point Estimate column to numeric
    df['Rally Point Estimate'] = pd.to_numeric(
        df['Rally Point Estimate'], errors='coerce'
    ).astype('Int64')

    # converting the Level column to numeric
    df['Level'] = pd.to_numeric(
        df['Level'], errors='coerce'
    ).astype('Int64')

    # converting the % complete column to numeric
    df['% Complete'] = pd.to_numeric(
        df['% Complete'], errors='coerce'
    )

    # converting the % burn column to numeric
    # df['% Burn'] = pd.to_numeric(
    #     df['% Burn'], errors='coerce'
    # )
    
    # converting the rally cost estimate column to numeric
    df['Rally Cost Estimate'] = pd.to_numeric(
        df['Rally Cost Estimate'], errors='coerce'
    )

    # converting the aha os approved column to numeric
    # df['Aha OS Approved Amt'] = pd.to_numeric(
    #     df['Aha OS Approved Amt'], errors='coerce'
    # )

    # try:
    #     # converting the actuals column to numeric
    #     df['Actuals Est (Hours x Rate)'] = pd.to_numeric(
    #         df['Actuals Est (Hours x Rate)'], errors='coerce'
    #     )

    #     # converting the etcs column to numeric
    #     df['ETCs'] = pd.to_numeric(
    #         df['ETCs'], errors='coerce'
    #     )

    #     # converting the etcs column to numeric
    #     df['EACs'] = pd.to_numeric(
    #         df['EACs'], errors='coerce'
    #     )

    #     # converting the rally / optics variance column to numeric
    #     df['Rally-Optics Variance'] = pd.to_numeric(
    #         df['Rally-Optics Variance'], errors='coerce'
    #     )
    # except KeyError:
    #     pass

    columns = []

    # for each column in our project plan, creating the appropriate definition for the smartsheet API call to create a new sheet
    for i, col_name in enumerate(headers):
        # standard data type in smartsheet
        col_type = 'TEXT_NUMBER'
        
        # changing the column type to date if the word date is in the column name
        if 'date' in col_name.lower():
            col_type = 'DATE'

        # changing the column type to piclist if the word status is in the column name
        elif 'status' in col_name.lower():
            col_type = 'PICKLIST'

        # creating the column definiton dict for each column
        col_def = {
            'title' : col_name,
            'type' : col_type,
            'primary' : (i == 0)
        }

        # adding an additional key for options for the picklist
        if col_type == 'PICKLIST':
            col_def['options'] = ['Not Started', 'Created', 'In Progress', 'Ready', 'Done', 'At Risk', 'Blocked']

        # adding formatting for % complete
        if '%' in col_name.lower():
            col_def['format'] = ',,,,,,,,,,,,,,3'
        
        if 'aha os approved amt' in col_name.lower() or 'rally cost estimate' in col_name.lower() or 'actuals est (hours x rate)' in col_name.lower() or 'etcs' in col_name.lower() or 'eacs' in col_name.lower() or 'rally-optics variance' in col_name.lower():
            col_def['format'] = ',,,,,,,,,,,,,1,2'

        columns.append(col_def)

    # creating the new sheet
    initial_payload = {
        'name': sheet_name,
        'columns': columns
    }

    response = requests.post(
        f"{BASE_URL}/folders/{fid}/sheets",
        headers=SMARTSHEET_HEADERS,
        json=initial_payload,
        verify=False
    )

    initial_sheet = response.json()

    col_map = {c['title']: c['id'] for c in initial_sheet['result']['columns']}
    ctype = {c['title']: c['type'] for c in initial_sheet['result']['columns']}
    sheet_id = initial_sheet['result']['id']

    # changing the date columns to be compliant to the expected date format in smartsheet
    # Convert to datetime, then to string format, replacing NaT with None
    #df['Actual End Date'] = pd.to_datetime(df['Actual End Date'], errors='coerce')
    #df['Actual End Date'] = df['Actual End Date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)

    df['Planned End Date (Rally)'] = pd.to_datetime(df['Planned End Date (Rally)'], errors='coerce')
    df['Planned End Date (Rally)'] = df['Planned End Date (Rally)'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
    
    df['Planned End Date'] = pd.to_datetime(df['Planned End Date'], errors='coerce')
    df['Planned End Date'] = df['Planned End Date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)

    level_stack = {}

    # saving the sheet name with a - instead of :
    s = sheet_name.replace(': ', ' - ')

    apps = apps['Impacts Delivery team'].dropna().unique().tolist()

    # bold_targets = [s, 'Critical Path Delivery', 'Initiation & Solution', 'Case Install Ready', 'Development', 'Quote Ready', 'Fulfillment Ready', 
    #                 'Billing Ready', 'Functional Capabilities', 'Finance Ready', 'Claims Ready', 'Consumer Services / Portal Ready', 'Reporting Ready',
    #                 'Case Effective - Go-Live', 'Cirrus QIB - SIT Testing', 'Other', 'PET Testing', 'Operational Readiness',
    #                 'Test Refresh Dates', 'Application View', 'Financials', 'Impacted Applications', 'Task Name', 'Optics Total', 'Aha Total', 'Optics'] + apps
    
    # Track which section we're in for conditional formatting
    in_application_view = False
    
    # looping through each row to appopriately push it to smartsheet with the proper indendations / hierarchy
    for _, r in df.iterrows():
        # getting the row level
        lvl = int(r.get('Level', 1))

        # getting the parent row level
        parent = level_stack.get(lvl - 1)

        # creating a new row object in smartsheet
        new_row = {
            'toBottom': True,
            'cells': []
        }

        # setting the parent attribute to the row as the parent if one exists
        if parent:
            new_row['parentId'] = parent

        
        # gettign the value from each column in the dataframe and inputting it in smartsheet cell
        # Get Work Breakdown value and strip markdown bold syntax (** **)
        wb = str(r.get('Work Breakdown', '')).strip()
        wb_clean = wb.replace('**', '').strip()  # Remove markdown bold for comparison
        
        # Track section transitions
        if wb_clean == 'Application View':
            in_application_view = True
        elif wb_clean == 'Financials':
            in_application_view = False
        
        fin_rows = ['Optics Total', 'Aha Total', 'Task Name', 'Impacted Applications'] + apps
        is_financial_row = wb_clean.startswith('ST') or wb_clean in fin_rows
        
        for h in headers:
            val = r[h]
            
            # Special handling for % Complete on Alpha/Master rows - explicitly set to blank
            if h == '% Complete' and wb_clean.lower() in ['alpha', 'master', 'test refresh dates']:
                cell_data = {'columnId': col_map[h], 'value': ''}
                new_row['cells'].append(cell_data)
                continue
            
            # setting the value to blank if the value is null in the dataframe
            if pd.isna(val) or val == "":
                continue
            
            # Strip markdown bold syntax from Work Breakdown column values
            if h == 'Work Breakdown' and isinstance(val, str):
                val = val.replace('**', '').strip()
            
            cell_data = {'columnId': col_map[h], 'value': val}
            
            # Apply Smartsheet number formatting to financial cells
            if is_financial_row:
                if h in ['Task ID', 'Rally Lead Team', 'Assigned To']:
                    # Currency format: $ with commas, no decimals
                    # Format code: ,,,,,,,,,,,,,1,2 means currency with $ and commas, 0 decimal places
                    try:
                        num_val = float(str(val).replace('$', '').replace(',', ''))
                        cell_data['value'] = num_val
                        cell_data['format'] = ',,,,,,,,,,,,,1,2'
                    except (ValueError, TypeError):
                        pass
                        
                elif h == 'Release':
                    # Percentage format: % with no decimals
                    # Format code: ,,,,,,,,,,,,,,3 means percentage
                    try:
                        if isinstance(val, str) and '%' in val:
                            num_val = float(val.replace('%', '')) / 100
                        else:
                            num_val = float(val) / 100
                        cell_data['value'] = num_val
                        cell_data['format'] = ',,,,,,,,,,,,,,3'
                    except (ValueError, TypeError):
                        pass
            
            new_row['cells'].append(cell_data)
        
        # conditionally formatting rows based on status value
        status = str(r.get('Status', '')).strip()
        st_underscore = s.split(' - ')[0].strip() + '_'
        st_start = s.split(' - ')[0].strip() + ' -'

        # print(f"WORK BREAKDOWN: '{wb}' | CLEAN: '{wb_clean}' | ST START: '{st_start}' | ST: '{s}'")

        if wb_clean: # in bold_targets:
            if wb_clean.startswith(st_start):
                new_row['format'] = ',,1,,,,,,,25' # dark brown
            elif wb_clean in ['Aha Toggled to Approved - Planning', 'PMAT Dashboard created', 'Core team assigned - RDL, BDL', 'Capabilities Created', 'Configuration team engaged, planned', 'Renewals Impacts confirmed', 'Capacity Modeling completed', 'High Level Market Events planned', 'UCMG ID funding released', 'PRJs set up (Tech & Business)', 'Aha Toggled to Approved Status', 'Solution Completed', 'Test Refresh Dates']:
                new_row['format'] = ',,1,,,,,,,18' # medium blue
            elif wb_clean == 'Planning':
                new_row['format'] = ',,1,,,,,,,26' # medium gray
            elif wb_clean == 'Execution':
                new_row['format'] = ',,1,,,,,,,22' # dark green
            elif wb_clean in ['Functional Capabilities (do not delete)', 'Case Install Ready', 'Quote Ready', 'Fulfillment Ready', 'Billing Ready', 'Finance Ready', 'Claims Ready', 'Consumer Services / Portal Ready', 'Reporting Ready', 'Renewal Ready', 'GNG Checkpoint', 'GNG Final Go Live', 'PET Testing', 'Operations Ready', 'Enrollment Ready', 'Go To Production Plan']:
                new_row['format'] = ',,1,,,,,,,14' # medium green
            elif wb_clean == 'Financials':
                new_row['format'] = ',,1,,,,,,,20' # dark yellow
            elif wb_clean.startswith('C1') or wb_clean.startswith('C2'):
                if in_application_view:
                    new_row['format'] = ',,1,,,,,,,8' # light blue
                else:
                    new_row['format'] = ',,1,,,,,,,7' # light green
            elif wb_clean.startswith('F1') or wb_clean.startswith('F2') or wb_clean.startswith('F3'):
                new_row['format'] = ',,,,,,,,,18' # grey
            elif wb_clean in apps or wb_clean == 'Other':
                if lvl == 3:
                    new_row['format'] = ',,1,,,,,,,15' # blue
                else:
                    new_row['format'] = ',,,,,,,,,5' # LIGHT GREEN
            elif wb_clean in ['Task Name', 'Impacted Applications']:
                new_row['format'] = ',,1,,,,,,,12' # medium yellow
            elif wb_clean in ['Optics Total', 'Aha Total']:
                new_row['format'] = ',,1,,,,,,,5' # medium yellow
            elif wb_clean in ['Application View']:
                new_row['format'] = ',,1,,,,,,,23' # darkest blue
            elif wb_clean.startswith(st_underscore):
                new_row['format'] = ',,,,,,,,,5' # light yellow
            else:
                new_row['format'] = ',,,,,,,,,18' # grey

        # 18: grey
        # 8: light blue
        # 15: medium blue
        # 23: dark blue
        # 5: light yellow
        # 12: medium yellow
        # 20: dark yellow
        # 6: light green
        # 14: medium green
        # 22: dark green

        row_payload = [new_row]

        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            res = requests.post(
                f"{BASE_URL}/sheets/{sheet_id}/rows",
                headers=SMARTSHEET_HEADERS,
                json=row_payload,
                verify=False
            )

            result = res.json()
            
            # Check if the result has the expected structure
            if 'result' in result and isinstance(result['result'], list) and len(result['result']) > 0:
                level_stack[lvl] = result['result'][0]['id']
                success = True
                break
            else:
                if attempt < max_retries - 1:
                    time.sleep(0.2)  # Wait a bit longer before retry
        
        if not success:
            print(f"Failed to create row after {max_retries} attempts: {result}")
            # Continue anyway to not break the entire upload
        
        time.sleep(0.05)

    roll_up_targets = ['Quote Ready', 'Billing Ready', 'Consumer Services / Portal Ready', 'Reporting Ready', 'Development', 'Case Install Ready', 'Functional Capabilities (do not delete)', 'Planning', 'Claims Ready', 'Finance Ready', 'Renewal Ready', 'GNG Checkpoint', 'GNG Final Go Live', 'PET Testing', 'Operations Ready', 'Enrollment Ready', 'Go To Production Plan', 'Other', 'Core team assigned - RDL, BDL', 'Renewals Impacts confirmed', 'PRJs set up (Tech & Business)', 'Solution Completed', s] + apps
    special_roll_up_targets = ['Execution']
    primary_col = 'Work Breakdown'
    secondary_col = '% Complete'
    third_col = 'Planned End Date (Rally)'

    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{sheet_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    secondary_sheet = sheet_response.json()

    sheet_columns = secondary_sheet['columns']
    sheet_rows = secondary_sheet.get('rows', [])

    def get_col_id(col_title):
        match = next((col['id'] for col in sheet_columns if col['title'] == col_title), None)
        if not match:
            raise ValueError(f"Column '{col_title}' not found in sheet.")
        return match

    pid = get_col_id(primary_col)
    sid = get_col_id(secondary_col)
    tid = get_col_id(third_col)
    rally_point_col_id = get_col_id('Rally Point Estimate')
    rally_cost_col_id = get_col_id('Rally Cost Estimate')
    # actuals_col_id = get_col_id('Actuals Est (Hours x Rate)')
    # eacs_col_id = get_col_id('EACs')
    # burn_col_id = get_col_id('% Burn')
    # variance_col_id = get_col_id('Rally-Optics Variance')


    # for each row and cell, checking to see if we have a match with our target and primary columns
    rows_to_update = []

    # rows to skip roll ups
    rows_to_skip = [
        "Aha Toggled to Approved - Planning",
        "PMAT Dashboard created",
        "Core team assigned - RDL, BDL",
        "RDL",
        "BDL",
        "Capabilities Created",
        "Configuration team engaged, planned",
        "Renewals Impacts confirmed",
        "Renewal questionnaire completed",
        "Capacity Modeling completed",
        "High Level Market Events planned",
        "UCMG ID funding released",
        "PRJs set up (Tech & Business)",
        "Tech PRJ Created",
        "PRJ added to AHA",
        "Optics tasks created",
        "Aha Toggled to Approved Status",
        "Solution Completed",
        "Configuration solution completed",
        "Product solutions complete (Cirrus, PL, CBB, etc)",
        "E2E solution completed (if applicable)",
        "Test Refresh Dates",
        "Alpha",
        "Master",
        "Planning",
        "Application View"
    ]


    # Flag to track if we've reached 'Financials' section
    financials_reached = False

    for row in sheet_rows:
        task_id = str(row['cells'][0]['value']) if row.get('cells') else ''
        work_breakdown_val = next((cell.get('value') for cell in row.get('cells', []) if cell.get('columnId') == pid), None)

        # Check if we've reached the 'Financials' row
        if work_breakdown_val == 'Financials':
            financials_reached = True
        
        # Skip applying formulas to any rows after 'Financials'
        if financials_reached:
            continue

        row_cells = []

        if task_id.startswith('C1') or task_id.startswith('C2') or work_breakdown_val in roll_up_targets:
            # updating the formula in the target cells
            row_cells.append({
                'columnId': sid,
                'formula': '=IF(COUNT(CHILDREN()) > 0, AVG(CHILDREN()), 0)'
            }) 

        # add SUM formula for rally point and cost columns for all rows except F1 and F2
        if not (task_id.startswith('F1') or task_id.startswith('F2') or work_breakdown_val in rows_to_skip):
            row_cells.append({
                'columnId': rally_point_col_id,
                'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
            })
            row_cells.append({
                'columnId': rally_cost_col_id,
                'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
            })
            # Add date rollup formula: MAX of child dates (latest date)
            row_cells.append({
                'columnId': tid,
                'formula': '=MAX(CHILDREN())'
            })
            if work_breakdown_val in special_roll_up_targets:
                row_cells.append({
                    'columnId': sid,
                    'formula': '=IF(COUNTIF(CHILDREN(), "<>0") > 0, AVG(COLLECT(CHILDREN(), CHILDREN(), "<>0")), 0)'
                })
            # # Add % Burn formula: Actuals / EACs (only if both are filled and EACs is non-zero)
            # row_cells.append({
            #     'columnId': burn_col_id,
            #     'formula': f'=IF(AND(NOT(ISBLANK([Actuals Est (Hours x Rate)]@row)), NOT(ISBLANK([EACs]@row)), [EACs]@row <> 0), [Actuals Est (Hours x Rate)]@row / [EACs]@row, "")'
            # })
            # # Add Rally-Optics Variance formula: EACs - Rally Cost Estimate (only if both are not blank, zeros are ok)
            # row_cells.append({
            #     'columnId': variance_col_id,
            #     'formula': '=IF(AND(NOT(ISBLANK([EACs]@row)), NOT(ISBLANK([Rally Cost Estimate]@row))), [EACs]@row - [Rally Cost Estimate]@row, "")'
            # })
        
        # if task_id.startswith('C1') or task_id.startswith('C2') or work_breakdown_val in apps:
        #     row_cells.append({
        #         'columnId': rally_point_col_id,
        #         'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
        #     })
        #     row_cells.append({
        #         'columnId': rally_cost_col_id,
        #         'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
        #     })

        if row_cells:
            rows_to_update.append(
                {
                    'id': row['id'],
                    'cells': row_cells
                }
            )
    
    if rows_to_update:
        # pushing the changes to smartsheet
        payload = rows_to_update

        res = requests.put(
            f"{BASE_URL}/sheets/{sheet_id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )

    # Collapse rows with Work Breakdown starting with C1, C2, or equal to 'Task Name' or 'Impacted Applications'
    # Also collapse 'Application View' and all Level 3 impacted apps under it (plus 'Other')
    print("\nCollapsing parent rows...")
    rows_to_collapse = []
    
    for row in sheet_rows:
        work_breakdown_val = next((cell.get('value') for cell in row.get('cells', []) if cell.get('columnId') == pid), None)
        level_val = next((cell.get('value') for cell in row.get('cells', []) if cell.get('columnId') == get_col_id('Level')), None)
        
        if work_breakdown_val:
            wb = str(work_breakdown_val).strip()
            wb_clean = wb.replace('**', '').strip()  # Remove markdown bold for comparison
            
            # Original collapse rules
            if wb.startswith('C1') or wb.startswith('C2') or wb in ['Task Name', 'Impacted Applications', 'Case Install Ready', 'Fulfillment Ready', 'Go To Production Plan', 'Renewal Ready']:
                rows_to_collapse.append({
                    'id': row['id'],
                    'expanded': False  # False means collapsed
                })
            # New rules for Application View section
            # elif wb_clean == 'Application View':
            #     rows_to_collapse.append({
            #         'id': row['id'],
            #         'expanded': False
            #     })
            # Collapse all Level 3 rows under Application View (impacted apps and 'Other')
            elif level_val == 3 and wb_clean in (apps + ['Other']):
                rows_to_collapse.append({
                    'id': row['id'],
                    'expanded': False
                })
    
    if rows_to_collapse:
        print(f"Collapsing {len(rows_to_collapse)} rows...")
        collapse_payload = rows_to_collapse
        
        res = requests.put(
            f"{BASE_URL}/sheets/{sheet_id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=collapse_payload,
            verify=False
        )
        
        if res.status_code == 200:
            print(f"✓ Successfully collapsed {len(rows_to_collapse)} parent rows")
        else:
            print(f"✗ Failed to collapse rows: {res.status_code} - {res.text}")

    # Enable text wrapping for Work Breakdown column
    print("\nEnabling text wrapping for Work Breakdown column...")
    wrap_payload = {
        'format': ',,,,,,,,,,,,,,,1,'
    }
    
    res = requests.put(
        f"{BASE_URL}/sheets/{sheet_id}/columns/{pid}",
        headers=SMARTSHEET_HEADERS,
        json=wrap_payload,
        verify=False
    )
    
    if res.status_code == 200:
        print(f"✓ Successfully enabled text wrapping for Work Breakdown column")
    else:
        print(f"✗ Failed to enable text wrapping: {res.status_code} - {res.text}")

    return sheet_id