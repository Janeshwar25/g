import pandas as pd
from utils import read_excel_to_dataframe, match_df_without_empty_cells

import numpy as np

AHA_MAPPING_TAB_NAME = "mapping_ahaData"
AHA_TMINUS_MAPPING_TAB_NAME = "mapping_tMinus"
RALLY_LEAD_MAPPING_TAB="mapping_rallyLeadTeam"
RALLY_DATA_MAPPING_TAB="mapping_rallyData"
DEFAULT_SOURCE_TYPE = "Excel"

class MappingRuleEngine:
    """
    Incapsulate loading and using mapping rules 
    """

    def __init__(self, source_type=DEFAULT_SOURCE_TYPE):
        """
        Constructor method to initialize the attributes of the class.

        Parameters:
        source_type (str):  Type of the source for Aha Data
        """

        self.source_type = source_type
        self.df_new_plan=None

    def load_mapping_rules(self, file_path:str, tab_name:str, skip_first_header=1):         
        if self.source_type=="Excel":
                df = read_excel_to_dataframe(file_path, tab_name)
                if(skip_first_header):
                    # Remove the current header and set the first row as the new header
                    df.columns = df.iloc[0]
                    df = df[1:].reset_index(drop=True)             
                return df


    def apply_aha_mapping_rules(self, df_aha:pd.DataFrame, df_plan: pd.DataFrame, file_path:str, bdl:str, rdl:str, business_owner:str,project_type:str) :         
                # Assign value from project_type to 'task ID' column where 'Work Breakdown' column has value 'Project Plan Type'
                df_plan.loc[df_plan['Work Breakdown'] == 'Project Type', 'Task ID'] = project_type
                
                # LOAD AHA MAPING RULES          
                df_aha_mapping=self.load_mapping_rules(file_path,AHA_MAPPING_TAB_NAME)
                
                # MATCH WORK IEMS TO BE ACTIVATED and UPDATE "Activated"
                df_aha_selected=match_df_without_empty_cells(df_aha, df_aha_mapping)       
                #df_aha_selected.to_csv('df_aha_selected.csv', index=False)
               
                df_items= df_aha_selected[['Work Breakdown']]
                print("Count of tasks, originally:",df_plan[df_plan['Impacted'] == 'Yes'].shape[0])
                df_plan.loc[df_plan['Work Breakdown'].isin(df_items['Work Breakdown']), 'Impacted'] = 'Yes'
                print("Count of tasks, after updated with Aha:",df_plan[df_plan['Impacted'] == 'Yes'].shape[0])
               
                # UPDATE 'Aha OS Approved Amt' and 'End Date']
                merged_df = pd.merge(df_plan, df_aha_selected, on='Work Breakdown', how='left')
                df_plan['Aha OS Approved Amt'] = merged_df['Impact Cost'].combine_first(df_plan['Aha OS Approved Amt'])
                df_plan['End Date'] = merged_df['Desired completion date'].combine_first(df_plan['End Date'])


                # LOAD T Minus
                df_t = self.load_mapping_rules(file_path, AHA_TMINUS_MAPPING_TAB_NAME)
                #df_t.to_csv('df_t.csv', index=False)

                # UPDATE T Minus
                # Filter df_t based on the fixed project_type value               
                df_t_filtered = df_t[df_t['Project Type'] == project_type]
                #df_t_filtered.to_csv('df_t_filtered.csv', index=False)

                # Merge df_plan with the filtered df_t
                merged_df = df_plan.merge(df_t_filtered[['Work Breakdown', 'T Minus']], on='Work Breakdown', suffixes=('', '_df_t'))
                
                # Update 'T Minus' in df_plan with 'T Minus' from df_t where there is a match
                df_plan = df_plan.set_index('Work Breakdown')
                merged_df = merged_df.set_index('Work Breakdown')
                #merged_df.to_csv('merged_df.csv', index=False)
                df_plan.loc[merged_df.index, 'T Minus'] = merged_df['T Minus_df_t'].values
                # Reset index if needed
                df_plan = df_plan.reset_index()
                #df_plan.to_csv('df_plan.csv', index=False)
                

                # Convert 'T Minus' and 'Level' columns to numeric data types
                df_plan['T Minus'] = pd.to_numeric(df_plan['T Minus'])
                df_plan['Level'] = pd.to_numeric(df_plan['Level'])
    

                #UDATE WORK HIERARCHY FROM  TOP TO DOWN for 'Impacted' 
                # Initialize a variable to keep track of the current  level
                current_level = None
  
                # Iterate over the rows of the DataFrame
                for index, row in df_plan.iterrows():
                    if row['Impacted'] == 'Yes':
                        # Update the current  level
                        current_level = row['Level']

                    elif current_level is not None and row['Level'] > current_level:
                        # Set Impacted to 'Yes' for rows with level less than the current  level
                        df_plan.at[index, 'Impacted'] = 'Yes'
           
                    elif current_level is not None and row['Level'] == current_level:
                        # Reset the current  level when encountering a row with the same level
                        current_level = None
   
                print("Count of tasks, as sub tasks considered",df_plan[df_plan['Impacted'] == 'Yes'].shape[0])
                #df_plan.to_csv('new_plan0.csv', index=False)

                #UDATE WORK HIERARCHY FROM  BOTTOM TO TOP for 'Impacted'
                for i in range(len(df_plan) - 1, -1, -1):
                    if df_plan.loc[i, 'Impacted'] == 'Yes':
                        current_level = df_plan.loc[i, 'Level']
                        for j in range(i - 1, -1, -1):
                            if df_plan.loc[j, 'Level'] < current_level:
                                df_plan.loc[j, 'Impacted'] = 'Yes'
                                current_level = df_plan.loc[j, 'Level']

                #UDATE WORK HIERARCHY FROM  TOP TO DOWN for  'T Minus'
                for i in range(1, len(df_plan)):
                        current_level = df_plan.loc[i, 'Level']
                        current_t_minus = df_plan.loc[i, 'T Minus']                 
                        for j in range(i-1, -1, -1):
                            if df_plan.loc[j, 'Level'] < current_level:
                                parent_t_minus = df_plan.loc[j, 'T Minus']
                                #print("parent_t_minus",parent_t_minus)
                                if current_t_minus < parent_t_minus:
                                    df_plan.loc[i, 'T Minus'] = parent_t_minus
                                    current_t_minus=parent_t_minus
                                    #print("new current",current_t_minus)
                                current_level -= 1
                                if current_level == 0:
                                    break

                # REMOVE NOT IMPACTED TASKS FROM THE NEW PLAN
                #df_plan.to_csv('new_plan111.csv', index=False)
                df_plan_new = df_plan[df_plan['Impacted'].str.lower() == 'yes']


                # Initialize a variable to keep track of the current level
                current_level = None
                value = 0

                # TOTAL SUM
                to_count=0
                if(to_count):
                    # Convert the column to a collection
                    aha_os_approved_amt_collection = df_plan_new['Aha OS Approved Amt'].tolist()

                    # Initialize a variable to store the sum of numeric values
                    sum_numeric_values = 0

                    # Iterate through the collection and process each element
                    for element in aha_os_approved_amt_collection:
                        print(f"Element: {element}, Type: {type(element)}")
                        try:
                            if not isinstance(element, float):
                                numeric_value = float(element.replace(',', ''))
                                print(f"Converted to numeric: {numeric_value}")
                                sum_numeric_values += numeric_value
                        except (ValueError, TypeError):
                            print("Not converted")

                    # Print the summary of successful conversions
                    print(f"Sum of numeric values: {sum_numeric_values}")

                    #total_os_approved = numeric_values.sum()
                    #print("total_os_approved:", total_os_approved)
                else:
                     # Take the value from column 'A' from any row (e.g., the first row)
                    sum_numeric_values = df_aha_selected['Oversight Approved Amount'].iloc[0]
                    # Formatting the numeric value
                    sum_numeric_values = "{:,.2f}".format(sum_numeric_values)      
  
                # Replace 'Total OS Approved' with the calculated sum using .loc
                df_plan_new.loc[df_plan_new['Aha OS Approved Amt'] == 'Total OS Approved', 'Aha OS Approved Amt'] = sum_numeric_values

                # Replace occurrences in the "Assigned To" column
                df_plan_new['Assigned To'] = df_plan_new['Assigned To'].replace({
                    'BDL': bdl,
                    'RDL': rdl,
                    'Business owner': business_owner
                })
                
                df_plan_new.rename(columns={'End Date': 'End Date - Baseline'}, inplace=True)
                df_plan_new.insert(df_plan_new.columns.get_loc('End Date - Baseline') + 1, 'End Date', '')
                self.df_new_plan=df_plan_new



    def apply_rally_mapping_rules(self, df_rally:pd.DataFrame, file_path:str):

        # LOAD RALLY LEAD TEAM MAPING RULES          
        df_rally_lead_mapping=self.load_mapping_rules(file_path,RALLY_LEAD_MAPPING_TAB)

        # Convert the DataFrame to a dictionary
        lead_dict = df_rally_lead_mapping.set_index('Lead Team')['Work Breakdown'].to_dict()
        #print(lead_dict)

        # LOAD RALLY DATA MAPING RULES          
        df_rally_data_mapping=self. load_mapping_rules(file_path,RALLY_DATA_MAPPING_TAB,0)
        #print(df_rally_data_mapping.columns)
        # Convert the DataFrame to a dictionary
        data_dict = df_rally_data_mapping.set_index('rally_Data ')['Output_Project plan'].to_dict()
        #print(data_dict)

        # Loop through the DataFrame and replace values in the 'Lead Team' column based on the dictionary
        df_rally['Lead Team'] = df_rally['Lead Team'].apply(lambda x: lead_dict[x] if x in lead_dict else x) 
        #print(df_rally)   

        #Load template populated with AHA 
        df_new_plan=self.df_new_plan

        # Create a new DataFrame to keep the right order of rows
        df_combined = pd.DataFrame(columns=df_new_plan.columns)

        # Convert DataFrame to dictionary - we will need it to  get  capability for the feature added to the plan
        df_dict2 = df_rally.set_index('ID').to_dict(orient='index')
        #print(df_combined['Aha OS Approved Amt'].to_string())

        # Iterate through each row in df_new_plan
        for index, row in df_new_plan.iterrows():
            # Append the current row from df_new_plan to df_combined
            df_combined = pd.concat([df_combined, pd.DataFrame([row])], ignore_index=True)
            
            work_breakdown_value = row['Work Breakdown']
            parent_level = row['Level']
            parent_t_minus=row['T Minus']
            #parent_assign=row["Assigned To"]
            parent_status=row["Status"]
            
            # Find all rows in df_rally that have the same value in "Lead Team"
            matching_rows = df_rally[df_rally['Lead Team'] == work_breakdown_value]
            
            # Create new rows in df_combined just under the match row
            for _, match_row in matching_rows.iterrows():

                #Adding Capability row
                new_row = {col: '' for col in df_new_plan.columns}
                new_row['Level'] = parent_level + 1
                new_row["Task ID"]=match_row["Solution Capability"]
                dict2=df_dict2[match_row["Solution Capability"]]
                new_row['T Minus']=parent_t_minus
                new_row['Impacted']="Yes"
                new_row["Status"]=parent_status
                for n1 in data_dict.keys():
                     if not n1=="ID":
                        new_row[data_dict[n1]] = dict2[n1]
                #if  new_row["Assigned To"]=="":
                     #new_row["Assigned To"]=parent_assign
                df_combined = pd.concat([df_combined, pd.DataFrame([new_row])], ignore_index=True)

                #Adding Feature row
                new_row = {col: '' for col in df_new_plan.columns}
                #new_row['Work Breakdown'] = match_row['Name']
                new_row['Level'] = parent_level + 2
                new_row['T Minus']=parent_t_minus
                new_row['Impacted']="Yes"
                new_row["Status"]=parent_status
                for n1 in data_dict.keys():
                     new_row[data_dict[n1]] = match_row[n1]
                #if  new_row["Assigned To"]=="":
                    #new_row["Assigned To"]=parent_assign                    
                df_combined = pd.concat([df_combined, pd.DataFrame([new_row])], ignore_index=True)

        #print(df_combined['Aha OS Approved Amt'].to_string())

        # Adding white spaces based on the Level
        df_combined['Work Breakdown'] = df_combined.apply(lambda row: ' ' * row['Level'] + row['Work Breakdown'], axis=1)  

        # Removing columns from df_combined that do not exist in df_new_plan
        #columns_to_keep = self.df_new_plan.columns
        #df_combined = df_combined[columns_to_keep]

        # Removing Column21 and Column22, ignoring errors if they do not exist
        df_combined = df_combined.drop(columns=['Column21', 'Column22'], errors='ignore')
        
        #AJUST CAPABILITIES
        df_combined=self.remove_unneeded_capabilities(df_combined)
        #df_combined=self. update_capability_complete(df_combined)

        # APPLY T Minus TO DATES
        # Convert 'End Date - Baseline' to datetime
        df_combined.loc[:, 'End Date - Baseline'] = pd.to_datetime(df_combined['End Date - Baseline'])
        # Subtract 'T Minus' from 'End Date' using .loc
        df_combined.loc[:, 'End Date - Baseline'] = df_combined['End Date - Baseline'] - pd.to_timedelta(df_combined['T Minus'], unit='d')


        #UDATE WORK HIERARCHY FROM  BOTTOM TO TOP for 'Started' status

        # Reset the index of the DataFrame
        df_combined.reset_index(drop=True, inplace=True)

        for i in range(len(df_combined) - 1, -1, -1):
                if df_combined.loc[i, 'Status'] == 'Started' or df_combined.loc[i, 'Status'] == 'Done':
                    current_level = df_combined.loc[i, 'Level']
                    for j in range(i - 1, -1, -1):
                        if j in df_combined.index and df_combined.loc[j, 'Level'] < current_level:
                            df_combined.loc[j, 'Status'] = 'Started'
                            current_level = df_combined.loc[j, 'Level']



        
        # Remove the "Impacted" column
        df_combined = df_combined.drop(columns=['Impacted'])

        #UPDATE RALLY END DATES FROM BOTTOM TO TOP
        df_combined.rename(columns={'End Date': 'End Date - Rally'}, inplace=True)
        # Convert 'End Date - Rally' to datetime
        df_combined.loc[:, 'End Date - Rally'] = pd.to_datetime(df_combined['End Date - Rally'])
        #self.update_parent_end_dates(df_combined,'End Date - Rally')


        #UPDATE % Complete
        percent_column_name='% Complete'
        self. update_parent_percent_complete(df_combined, percent_column_name)
    

        
        # Replace 'Started' with 'In Progress' in the 'Status' column, ensuring 'Not Started' remains unchanged
        df_combined['Status'] = df_combined['Status'].apply(lambda x: 'In Progress' if x == 'Started' else x)


        # Assign 'Done' status to parent tasks if all child tasks have 'Done' status
        df_combined = self.assign_done_status(df_combined)

        
        # Assign 'In Progress' status to parent tasks if they have at least one child with status not in the list
        df_combined = self.assign_in_progress_status(df_combined)


        
        # Export DataFrame to CSV file
        df_combined.to_csv('new_plan.csv', index=False)
        self.df_new_plan=df_combined



    # Function to remove unneeded rows (capabilities) from df_plan_new
    def remove_unneeded_capabilities(self, df):
        # Initialize an empty list to store the indices of rows to keep
        indices_to_keep = []
        
        # Initialize a variable to keep track of the current level
        current_level = float('inf')
        
        # Iterate over the rows of the DataFrame
        for index, row in df.iterrows():
            task_id = row['Task ID']
            level = row['Level']
            
            if level < current_level:
                capabs=set()
                current_level = float('inf')
            
            # Check if the row is a capability (Task ID starts with C)
            if isinstance(task_id, str) and task_id.startswith('C'):

                    if task_id not in capabs:
                        indices_to_keep.append(index)
                        capabs.add(task_id)
                        current_level = level

            else:
                #it is not capability
                indices_to_keep.append(index)
        
        # Filter the DataFrame to keep only the rows with indices in indices_to_keep
        df_filtered = df.loc[indices_to_keep]
        
        return df_filtered
    
    def  update_capability_complete(self, df):
        capab="Not defined"
        d1={}
        d2={}
         
        #Loop through each row
        for index, row in df.iterrows():
            task_id = row['Task ID']

            if isinstance(task_id, str):
                if task_id.startswith('C'):
                     capab=task_id
                if task_id.startswith('F'):
                    try:
                            # Try to convert input_value to float
                            value = float(row['% Complete'])
                    except ValueError:
                            # If conversion fails, set value to 0
                            value = 0

                    if capab in d1:
                        d1[capab] += value
                        d2[capab] += 1
                    else:
                        d1[capab] = value
                        d2[capab] = 1

                    if value == 1:
                        df.at[index, 'Status'] = 'Done'
                    elif value > 0:
                        df.at[index, 'Status'] = 'Started'
                    else:
                        df.at[index, 'Status'] = 'Not Started'
                         

        #Loop through each row
        for index, row in df.iterrows():
            task_id = row['Task ID']

            if isinstance(task_id, str):
                if task_id.startswith('C'):
                    value=d1[task_id]/d2[task_id]
                    df.at[index, '% Complete'] = round(value, 4)
                    if d1[task_id] > 0:
                        df.at[index, 'Status'] = 'Started'
                    else:
                        df.at[index, 'Status'] = 'Not Started'

        return df
    


    
    # Function to update parent end dates based on child end dates
    def update_parent_end_dates(self,df, date_column_name):

        # remove end dates or capabilities
        # Create a boolean mask for rows where 'Task ID' is not NA and starts with 'c' or 'C'
        mask = df['Task ID'].notna() & df['Task ID'].str.startswith(('c', 'C'))
        # Set 'End Date - Rally' to NaT for rows matching the mask
        df.loc[mask, date_column_name] = pd.NaT



        # Iterate through the DataFrame from the last row to the first row
        for i in range(len(df) - 1, 0, -1):
            current_level = df.at[i, 'Level']
            current_end_date = df.at[i, date_column_name]
            print("Looking for ", df.at[i, 'Work Breakdown'], current_level, current_end_date)
            
            # Iterate through the rows above the current row to find the parent row
            for j in range(i - 1, -1, -1):
                if df.at[j, 'Level'] < current_level:
                    parent_end_date = df.at[j, date_column_name]
                    parent_task_id = df.at[j, 'Task ID']
                    
                    # Check if the parent end date is NaT or if the 'Task ID' starts with 'C' or 'c'
                    #if pd.isna(parent_end_date) or (isinstance(parent_task_id, str) and parent_task_id and parent_task_id[0].lower()== 'c'):
                    if (not (isinstance(parent_task_id, str))) or (not (parent_task_id[0].lower()== 'f')):
                        #df.at[j, date_column_name] = max(df.at[j, date_column_name], current_end_date)
                        if pd.isna(current_end_date):
                            max_date=parent_end_date
                        else:
                            max_date=max(current_end_date, parent_end_date)


                        df.at[j, date_column_name] = max_date
                        print("current_end_date:",current_end_date, " parent_end_date",parent_end_date, "max(current_end_date, parent_end_date)",max(current_end_date, parent_end_date), "max_date=", max_date)
                        print("found: ", df.at[j, 'Work Breakdown'], df.at[j, 'Level'] , parent_task_id, parent_end_date, " df.at[j, date_column_name]=",df.at[j, date_column_name])
                    break
    



    # Function to assign 'Done' status to parent tasks if all child tasks have 'Done' status
    def assign_done_status(self,df):
        # Iterate from the lowest level to the root level
        for level in sorted(df['Level'].unique(), reverse=True):
            if level == 1:
                continue
            # Get tasks at the current level
            current_level_tasks = df[df['Level'] == level]
            # Iterate over tasks at the current level
            for index, row in current_level_tasks.iterrows():
                # Get the parent task
                parent_task_index = df[(df.index < index) & (df['Level'] == level - 1)].index.max()
                if parent_task_index is not None:
                    # Check if all child tasks have 'Done' status
                    child_tasks = df[(df.index > parent_task_index) & (df.index <= index) & (df['Level'] == level)]
                    if all(child_tasks['Status'].str.lower() == 'done'):
                        df.at[parent_task_index, 'Status'] = 'Done'
        return df
    

    # Function to assign 'In Progress' status to parent tasks if they have at least one child with status not in the list
    def assign_in_progress_status(self,df):
        # Iterate from the lowest level to the root level
        for level in sorted(df['Level'].unique(), reverse=True):
            if level == 1:
                continue
            # Get tasks at the current level
            current_level_tasks = df[df['Level'] == level]
            # Iterate over tasks at the current level
            for index, row in current_level_tasks.iterrows():
                # Get the parent task
                parent_task_index = df[(df.index < index) & (df['Level'] == level - 1)].index.max()
                if parent_task_index is not None:
                    # Check if parent task status is not 'Done'
                    if df.at[parent_task_index, 'Status'].lower() != 'done':
                        # Check if any child task has status not in the list
                        child_tasks = df[(df.index > parent_task_index) & (df.index <= index) & (df['Level'] == level)]
                        if any(~child_tasks['Status'].str.lower().isin(['created', 'ready', 'no entry'])):
                            df.at[parent_task_index, 'Status'] = 'In Progress'
        return df
    
    

    # Function to update parent '% Complete' values based on the weighted average of all direct child rows
    def update_parent_percent_complete(self, df, percent_column_name):
        percent_column_name0=percent_column_name
        percent_column_name=percent_column_name0+" counted"
 
        # Duplicate the column 'percent_column_name0' to a new column 'percent_column_name'
        df.insert(df.columns.get_loc(percent_column_name0) + 1, percent_column_name, df[percent_column_name0])

        # '% Complete' to zero for rows where 'Task ID' starts with 'c' or 'C' followed by any digit, and handle NaN values
        # Iterate through the DataFrame from the last row to the first row
        for i in range(len(df) - 1, 0, -1):
                task_id = df.at[i, 'Task ID']
                       
                        # Check if the parent end date is NaT or if the 'Task ID' starts with 'C' or 'c'
                if (isinstance(task_id, str) and task_id and task_id[0].lower()== 'c'):
                    df.at[i, percent_column_name]=0
       
        highest_level=df['Level'].max()
        k=highest_level
        for i in range(highest_level, 0, -1):
           
            # Add temporary columns
            df['num'] = 0
            df['sum'] = 0.0
 
            # Iterate through the DataFrame from the last row to the first row
            for i in range(len(df) - 1, 0, -1):
                current_level = df.at[i, 'Level']
                current_completness = df.at[i, percent_column_name]
 
               
                # Iterate through the rows above the current row to find the parent row
                for j in range(i - 1, -1, -1):
                    if df.at[j, 'Level'] < current_level:
                        df.at[j, 'num']=df.at[j, 'num'] + 1
                        df.at[j, 'sum']=df.at[j, 'sum'] + current_completness
                        break
 
            mask = df['Level'] == k-1

            # Assign to column percent_column_name the value 'sum/num' where 'num' is not zero or NaN, otherwise assign zero
            df.loc[mask, percent_column_name] = np.where(df.loc[mask, 'num'] == 0, 0, df.loc[mask, 'sum'] / df.loc[mask, 'num'])
            df[percent_column_name] = df[percent_column_name].apply(lambda x: round(x, 4))

            k=k-1
           
            # Remove columns 'sum' and 'num'
            #df.drop(columns=['sum', 'num'], inplace=True)
          
        return
 




    


