import pandas as pd
import json
import os
from engine.mongodb_helper import MongoDBHelper

def read_excel_to_dataframe(file_path, sheet_name):
    """
    Reads an Excel file and returns a DataFrame for the specified sheet.

    Parameters:
    file_path (str): Path to the Excel file.
    sheet_name (str): Name of the sheet to read.

    Returns:
    pd.DataFrame: DataFrame containing the data from the specified sheet.
    """
    try:
   
        # Read the Excel file without header
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        
        # Drop empty rows at the top
        df = df.dropna(how='all').reset_index(drop=True)
        
        # Set the first non-empty row as the header
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

        # Drop empty columns
        #df = df.dropna(axis=1, how='all')

        # Drop columns with empty headers and all empty values
        df = df.loc[:, ~(df.columns.isna() & df.isna().all())]

        return df


    except Exception as e:
        # print(f"An error occurred: {e}")
        return None

def filter_rows_by_value(df, column_name, value):
    """
    Filters rows in the DataFrame to keep only those where the specified column has the given value.

    Parameters:
    df (pd.DataFrame): The input DataFrame.
    column_name (str): The name of the column to filter by.
    value: The value to filter rows by.

    Returns:
    pd.DataFrame: The filtered DataFrame.
    """
    filtered_df = df[df[column_name] == value]
    return filtered_df

def match_df_without_empty_cells(df1, df2):
    # Extract columns from df2 that are also in df1
    common_columns = df2.columns.intersection(df1.columns)
    #print("df1: ",df1.columns)
    #print("df2: ",df2.columns)
    #print("!!!!!!!!!!!!!!!!!!!!!!!!!!!",common_columns)

    # Find matching rows in df1
    matching_rows = df1[df1[common_columns].isin(df2[common_columns].to_dict(orient='list')).all(axis=1)]

    # Merge matching rows with the extra column from df2
    result = matching_rows.merge(df2, on=list(common_columns))
    return result


# Function to find matching rows considering empty cells
def match_df_with_empty_cells(df1, df2):
    matching_rows = pd.DataFrame()
    for idx, row in df2.iterrows():
        # Drop columns with empty cells for this row
        row_non_empty = row.dropna()
        common_columns = row_non_empty.index.intersection(df1.columns)
        # Find matching rows in df1
        match = df1[df1[common_columns].isin(row_non_empty.to_dict()).all(axis=1)]
        # Add the extra column from df2
        match = match.assign(**{df2.columns[-1]: row[df2.columns[-1]]})
        matching_rows = pd.concat([matching_rows, match], ignore_index=True)
    return matching_rows


def save_plan_metadata_mongo(rally_theme, prj, tag, idea, name, go_live, bdl, rdl):
    '''
    Saving the plan metadata to MongoDB.
    This ensures data persists even when containers are destroyed.
    When rally_theme is 'none', uses the AHA idea as the key instead.
    '''
    # Determine the key to use - if no theme, use the idea number
    if rally_theme == 'none' or not rally_theme:
        metadata_key = idea  # Use AHA idea as key (e.g., PSTRATEGIC-I-2278)
        print(f"No strategic theme found. Using AHA idea as key: {metadata_key}")
    else:
        metadata_key = rally_theme
        print(f"Using strategic theme as key: {metadata_key}")
    
    theme_values = {
        'idea': idea,
        'name': name,
        'tag': tag,
        'prj': prj,
        'go live': go_live,
        'bdl': bdl,
        'rdl': rdl,
        'rally_theme': rally_theme,  # Store the theme value even if 'none'
        'active': True  # New projects are active by default
    }
    
    # Save to MongoDB
    mongo_helper = MongoDBHelper()
    mongo_helper.save_plan_metadata(metadata_key, theme_values)
    mongo_helper.close()
    
    return metadata_key  # Return the key used for storage

def save_plan_metadata_v2(file , rally_theme, prj, tag, idea, name, go_live, bdl, rdl):
    '''
    Saving the plan meta data in a json file. This includes 'sheet id' which is references when updating a plan.
    '''
    if rally_theme == 'none' or not rally_theme:
        raise ValueError("Rally Theme not included.")
    
    theme_values = {
        'idea': idea,
        'name': name,
        'tag': tag,
        'prj': prj,
        'go live': go_live,
        'bdl': bdl,
        'rdl': rdl
    }

    if os.path.exists(file):
        with open(file, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data[rally_theme] = theme_values

    with open(file, 'w') as f:
        json.dump(data, f, indent=2)