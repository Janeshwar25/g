import streamlit as st
import requests
import pandas as pd
import json
import os
import io
import logging
import re
from engine.utils import save_plan_metadata_v2, save_plan_metadata_mongo
from upload.smartsheet_export import smartsheet_upload
from engine.mapping import get_aha_data
from config import Config
from engine.mongodb_helper import MongoDBHelper
from engine.test_dashboard import generate_pet_test_script


# Load configuration
config = Config()
metadata_file = config.METADATA_FILE

# API endpoint
API_URL = f"{config.API_BASE_URL}/chat"
API_URL_FINANCIALS= f"{config.API_BASE_URL}/financials"

# Helper function to convert markdown to HTML
def markdown_to_html(text):
    """Convert basic markdown formatting to HTML, including email draft buttons and tables"""
    # Check for email draft pattern [OPEN_OUTLOOK:url]
    outlook_match = re.search(r'\[OPEN_OUTLOOK:(mailto:[^\]]+)\]', text)
    if outlook_match:
        mailto_url = outlook_match.group(1)
        # Remove the [OPEN_OUTLOOK:url] tag from text
        text = re.sub(r'\[OPEN_OUTLOOK:[^\]]+\]', '', text)
        # Add a styled button at the end with single line space
        button_html = f'''<a href="{mailto_url}" style="display: inline-block; background-color: #001f3f; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 10px;">Open in Outlook</a>'''
        text = text + button_html
    
    # Check for download report pattern [DOWNLOAD_REPORT:filepath]
    # Remove the tag from display (button will be rendered separately)
    text = re.sub(r'\[DOWNLOAD_REPORT:[^\]]+\]', '', text)
    
    # Convert markdown tables to HTML tables
    # Look for table pattern (lines with | separators)
    lines = text.split('\n')
    in_table = False
    table_html = []
    non_table_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this line looks like a table row (has | characters)
        if '|' in line and line.count('|') >= 2:
            if not in_table:
                # Starting a new table
                in_table = True
                table_html = ['<table style="border-collapse: collapse; margin: 10px 0; width: 100%;">']
                
                # Process header row
                headers = [cell.strip() for cell in line.split('|')[1:-1]]
                table_html.append('<thead><tr>')
                for header in headers:
                    table_html.append(f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f0f2f6; text-align: left;">{header}</th>')
                table_html.append('</tr></thead><tbody>')
                
                # Skip separator line if present (next line with dashes)
                if i + 1 < len(lines) and re.match(r'^\|[\s\-:]+\|', lines[i + 1].strip()):
                    i += 1
            else:
                # Add data row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                table_html.append('<tr>')
                for cell in cells:
                    table_html.append(f'<td style="border: 1px solid #ddd; padding: 8px;">{cell}</td>')
                table_html.append('</tr>')
        else:
            # Not a table row
            if in_table:
                # End the table
                table_html.append('</tbody></table>')
                non_table_lines.append(''.join(table_html))
                table_html = []
                in_table = False
            
            non_table_lines.append(line)
        
        i += 1
    
    # Close any open table
    if in_table:
        table_html.append('</tbody></table>')
        non_table_lines.append(''.join(table_html))
    
    # Rejoin the text
    text = '\n'.join(non_table_lines)
    
    # Bold: **text** or __text__ -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_ -> <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Line breaks
    text = text.replace('\n', '<br>')
    return text

# Initialize session state for update option and generated plans
if 'update_option' not in st.session_state:
    st.session_state.update_option = []
if 'generated_plans' not in st.session_state:
    st.session_state.generated_plans = []

# Initialize session state for user login
# if 'user' not in st.session_state:
#     st.session_state.user = None

# Sidebar login form
# with st.sidebar:
#     st.header("Login to View Your Alerts!")
#     first_name = st.text_input("First Name")
#     last_name = st.text_input("Last Name")
#     if st.button("Login"):
#         full_name = f"{first_name.strip()} {last_name.strip()}"
#         st.session_state.user = full_name
#         st.success(f"Welcome, {full_name}!")

# Global CSS for all buttons (navy blue) and wider layout
st.markdown(f"""
    <style>
    .main .block-container {{
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }}
    div[data-testid="stButton"] button {{
        background-color: #001f3f !important; /* Navy blue */
        color: white !important;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
        border-radius: 8px;
        cursor: pointer;
    }}
    div[data-testid="stDownloadButton"] button {{
        background-color: #001f3f !important; /* Navy blue */
        color: white !important;
        border-radius: 8px;
    }}
    /* Make dataframe take full width without internal scrolling */
    div[data-testid="stDataFrame"] {{
        width: 100%;
    }}
    div[data-testid="stDataFrame"] > div {{
        width: 100%;
        max-width: 100%;
    }}
    </style>
""", unsafe_allow_html=True)

# Tabs
# tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Build Plan", "Update Plan", "Project Dashboard", "AI Alerts", "Financials", "Project Intel AI"])
# tab1, tab2, tab3, tab6 = st.tabs(["Build Plan", "Update Plan", "Dashboard", "Project Intel AI"])
# tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Build Plan", "Update Plan", "Test Plan", "Alerts", "Dashboard", "Project Intel AI", "Frequently Asked Questions"])
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Build Plan",
    "Update Plan",
    "Test Plan",
    "Frequently Asked Questions",
    "AI Help Bot",
])


# Build Plan Tab
with tab1:
    st.title("Project Plan Builder")

    st.subheader("Enter Plan Parameters")
    plan_idea = st.text_input("Aha Idea *", placeholder="PSTRATEGIC-I-847")
    project_type = st.selectbox("Project Type", options=["General"])
    idea_name = st.text_input("Idea Name *", placeholder="Provide Doula Support for E&I Commercial Pregnant Members", help="Must be 40 characters or less")
    
    # Validate idea name length
    if idea_name and len(idea_name.strip()) > 40:
        st.error(f"Idea Name is too long ({len(idea_name.strip())} characters). Please limit to 40 characters or less.")
    
    bdl = st.text_input("BDL", placeholder="Beth Smith")
    rdl = st.text_input("RDL", placeholder="Rahil Sharma")

    if st.button("Build Plan"):
        # Validate required fields
        if not plan_idea or not plan_idea.strip():
            st.error("Aha Idea is required. Please enter an Aha Idea.")
        elif not idea_name or not idea_name.strip():
            st.error("Idea Name is required. Please enter an Idea Name.")
        elif len(idea_name.strip()) > 40:
            st.error("Cannot build plan: Idea Name must be 40 characters or less.")
        else:
            plan_params = {
                "plan idea": plan_idea.strip() if plan_idea else None,
                "project type": project_type.strip() if project_type else None,
                "idea name": idea_name.strip() if idea_name else None,
                "BDL": bdl.strip() if bdl else None,
                "RDL": rdl.strip() if rdl else None,
            }

            try:
                apps, approved, rally_theme, tag, prj, go_live = get_aha_data(plan_idea)

                plan_name = f"{rally_theme}: {idea_name}"

                # NEW: MongoDB approach - returns the key used (theme or idea)
                metadata_key = save_plan_metadata_mongo(rally_theme, prj, tag, plan_params['plan idea'], plan_params['idea name'], go_live, plan_params['BDL'], plan_params['RDL'])
                
                # OLD: JSON file approach (active)
                # save_plan_metadata_v2('documents/plan_metadata.json', rally_theme, prj, tag, plan_params['plan idea'], plan_params['idea name'], go_live, plan_params['BDL'], plan_params['RDL'])

                st.success(f"Your plan {plan_name} is being generated. It will be available in Smartsheet shortly.")

                response = requests.post(API_URL, json={"user_input": "User Request", "plan_params": plan_params}, timeout=config.REQUEST_TIMEOUT)

                if response.status_code == 200:
                    # Get CSV string from response and convert to DataFrame
                    response_data = response.json()
                    csv_string = response_data["csv"]
                    plan_df = pd.read_csv(io.StringIO(csv_string))

                    st.session_state.generated_plans.append(plan_name)

                    # Pass DataFrame directly to smartsheet_upload
                    sheet_id = smartsheet_upload(dataframe=plan_df, sheet_name=plan_name, tag=tag, apps=apps)

                    # OLD: JSON file approach (active)
                    # with open('documents/plan_metadata.json', 'r') as f:
                    #     data = json.load(f)
                    # data[rally_theme]['sheet id'] = sheet_id
                    # with open('documents/plan_metadata.json', 'w') as f:
                    #     json.dump(data, f, indent=4)
                    
                    # NEW: MongoDB approach - use the metadata_key returned earlier
                    mongo_helper = MongoDBHelper()
                    mongo_helper.update_plan_metadata(metadata_key, {'sheet id': sheet_id})
                    mongo_helper.close()
                elif response.status_code == 400:
                    st.error("Bad Request: Please check the input parameters.")
                elif response.status_code == 500:
                    st.error("Server Error: Please try again later.")
                else:
                    st.error("Failed to generate plan")

            except Exception as e:
                st.error(f"Please ensure the Aha idea is enter correctly. Error: {e}")

# Update Plan Tab
with tab2:
    st.header("Update Project Plan")

    selected_plan = st.text_input("Please enter the strategic theme or Aha idea of the plan that you would like to update:")

    st.subheader("Select Data Sources to Update")

    update_aha = st.checkbox("Aha", value=True, key="update_aha")
    update_optics = st.checkbox("Optics", value=True, key="update_optics")

    rally_release = st.checkbox("Rally - Release", value=True, key="rally_release")
    rally_end_date = st.checkbox("Rally - Actual End Date", value=True, key="rally_end_date")
    rally_status = st.checkbox("Rally - Status", value=True, key="rally_status")
    rally_complete = st.checkbox("Rally - % Complete", value=True, key="rally_complete")
    rally_point = st.checkbox("Rally - Point Estimate", value=True, key="rally_point")
    rally_cost = st.checkbox("Rally - Cost Estimate", value=True, key="rally_cost")

    if st.button("Update Plan", key="update_plan"):
        st.write(f"Plan is updating in Smartsheet.")

        # Gather update options
        update_options = {
            "aha": update_aha,
            "optics": update_optics,
            "rally_fields": {
                "release": rally_release,
                "end_date": rally_end_date,
                "status": rally_status,
                "complete": rally_complete,
                "point": rally_point,
                "cost": rally_cost
            }
        }
        
        try:
            response = requests.post(
                API_URL, 
                json={
                    "user_input": "Update Request", 
                    'st': selected_plan,
                    'update_options': update_options
                }, 
                timeout=config.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                st.success("Plan updated successfully!")
            elif response.status_code == 400:
                st.error("Bad Request: Please check the input parameters.")
            elif response.status_code == 500:
                st.error("Please ensure this Strategic Theme is entered correctly.")
            else:
                st.error("Failed to update plan")

        except Exception as e:
            st.error(f"Please ensure the Strategic Theme is entered correctly.")

with tab3:
    st.title("Generate Test Cases")

    pet_st = st.text_input("Please enter the Strategic Theme:", key="pet_st")
    pet_capability = st.text_input("Please enter the Capability ID:", key="pet_capability")
    template_path = 'documents/Template_NB PET_Test Scripts.xlsx'

    if st.button("Generate Test Plan", key="generate_test_plan"):
        if not pet_st or not pet_st.strip():
            st.error("Strategic Theme is required.")
        elif not pet_capability or not pet_capability.strip():
            st.error("Capability ID is required.")
        elif not os.path.exists(template_path):
            st.error(f"Template not found: {template_path}")
        else:
            try:
                generated_file = generate_pet_test_script(
                    st_id=pet_st.strip(),
                    template_path=template_path,
                    capability_id=pet_capability.strip(),
                )
                st.session_state.pet_generated_file = generated_file
                st.success("Test plan generated successfully.")
            except Exception as e:
                st.error(f"Unable to generate test plan. Error: {e}")

    if st.session_state.get('pet_generated_file') and os.path.exists(st.session_state.pet_generated_file):
        with open(st.session_state.pet_generated_file, 'rb') as file_obj:
            st.download_button(
                label="Download Filtered Test Plan",
                data=file_obj.read(),
                file_name=os.path.basename(st.session_state.pet_generated_file),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_filtered_test_plan"
            )

# with tab4:

#     st.title("Alerts Dashboard")
#     st.write("This dashboard displays all projects with their status and alerts. Click to expand each project's details.")

#     # Connect to MongoDB and fetch all plans and needs_attention alerts
#     mongo_helper = MongoDBHelper()
#     all_plans = mongo_helper.get_all_plans()
#     db = mongo_helper.db
#     needs_attention_collection = db['needs_attention']
#     all_project_data = list(needs_attention_collection.find({}))

#     if not all_project_data:
#         st.info("No projects found.")
#     else:
#         # Add filters at the top
#         col1, col2, col3 = st.columns(3)
        
#         # Collect all unique values for filters
#         all_initiatives = set()
#         all_bdls = set()
#         all_rdls = set()
#         for project in all_project_data:
#             theme = project.get('project_theme', 'Unknown')
#             meta = all_plans.get(theme, {})
#             all_initiatives.add(meta.get('tag', 'N/A'))
#             all_bdls.add(meta.get('bdl', 'N/A'))
#             all_rdls.add(meta.get('rdl', 'N/A'))
        
#         with col1:
#             initiative_filter = st.multiselect(
#                 "Filter by Initiative Area",
#                 options=sorted(all_initiatives),
#                 default=[]
#             )
        
#         with col2:
#             bdl_filter = st.multiselect(
#                 "Filter by BDL",
#                 options=sorted(all_bdls),
#                 default=[]
#             )
        
#         with col3:
#             rdl_filter = st.multiselect(
#                 "Filter by RDL",
#                 options=sorted(all_rdls),
#                 default=[]
#             )
        
#         # Apply filters and display
#         filtered_projects = []
#         for project in all_project_data:
#             theme = project.get('project_theme', 'Unknown')
#             meta = all_plans.get(theme, {})
            
#             # Check filters
#             if initiative_filter and meta.get('tag', 'N/A') not in initiative_filter:
#                 continue
#             if bdl_filter and meta.get('bdl', 'N/A') not in bdl_filter:
#                 continue
#             if rdl_filter and meta.get('rdl', 'N/A') not in rdl_filter:
#                 continue
            
#             filtered_projects.append(project)
        
#         # Display count
#         st.markdown(f"**Showing {len(filtered_projects)} of {len(all_project_data)} projects**")
#         st.markdown("---")
        
#         # Pagination setup
#         items_per_page = 10
#         total_pages = (len(filtered_projects) + items_per_page - 1) // items_per_page  # Ceiling division
        
#         # Initialize page number in session state
#         if 'alert_page' not in st.session_state:
#             st.session_state.alert_page = 1
        
#         # Calculate start and end indices for current page
#         start_idx = (st.session_state.alert_page - 1) * items_per_page
#         end_idx = min(start_idx + items_per_page, len(filtered_projects))
#         current_page_projects = filtered_projects[start_idx:end_idx]
        
#         # Display expandable panels for current page
#         for project in current_page_projects:
#             theme = project.get('project_theme', 'Unknown')
#             status_info = project.get('status', {})
#             attention_items = project.get('needs_attention', [])
            
#             # Get metadata from all_plans
#             meta = all_plans.get(theme, {})
#             project_name = meta.get('name', '')
#             aha_idea = meta.get('aha_idea', 'N/A')
#             bdl = meta.get('bdl', 'N/A')
#             rdl = meta.get('rdl', 'N/A')
#             initiative_area = meta.get('tag', 'N/A')
            
#             # Format percentages
#             planning_pct = status_info.get('planning_percent')
#             execution_pct = status_info.get('execution_percent')
#             planning_str = f"{planning_pct:.0f}%" if planning_pct is not None else "N/A"
#             execution_str = f"{execution_pct:.0f}%" if execution_pct is not None else "N/A"
            
#             # Count alerts
#             alert_count = len(attention_items) if attention_items else 0
            
#             # Create title with strategic theme and project name
#             title = f"**{theme}: {project_name}**" if project_name else f"**{theme}**"
            
#             # Create expander with title showing strategic theme, project name, and alert count
#             with st.expander(f"{title} ({alert_count} alert{'s' if alert_count != 1 else ''})", expanded=False):
#                 # For MMI projects show only RDL and Initiative Area
#                 is_mmi = (meta.get('bc') or '').strip().upper() == 'MMI'
#                 if is_mmi:
#                     col1, col2 = st.columns(2)
#                     with col1:
#                         st.markdown(f"**RDL:** {rdl}")
#                     with col2:
#                         st.markdown(f"**Initiative Area:** MMI")
#                 else:
#                     # Display metadata in columns for non-MMI
#                     col1, col2 = st.columns(2)
#                     with col1:
#                         st.markdown(f"**Planning:** {planning_str}")
#                         st.markdown(f"**Execution:** {execution_str}")
#                     with col2:
#                         st.markdown(f"**RDL:** {rdl}")
#                         st.markdown(f"**BDL:** {bdl}")
#                     st.markdown(f"**Initiative Area:** {initiative_area}")
                
#                 # Display alerts
#                 if attention_items:
#                     st.markdown("---")
#                     st.markdown("**Needs Attention:**")
#                     for item in attention_items:
#                         st.markdown(f"- {item}")
#                 else:
#                     st.markdown("---")
#                     st.markdown("*No alerts*")
        
#         # Pagination controls at the bottom
#         if total_pages > 1:
#             st.markdown("---")
#             col1, col2, col3 = st.columns([1, 3, 1])
            
#             with col1:
#                 if st.session_state.alert_page > 1:
#                     if st.button("← Back", key="alert_back"):
#                         st.session_state.alert_page -= 1
#                         st.rerun()
            
#             with col2:
#                 st.markdown(f"<div style='text-align: center;'>Page {st.session_state.alert_page} of {total_pages}</div>", unsafe_allow_html=True)
            
#             with col3:
#                 if st.session_state.alert_page < total_pages:
#                     if st.button("Next →", key="alert_next"):
#                         st.session_state.alert_page += 1
#                         st.rerun()


with tab4:
    st.title("Frequently Asked Questions (FAQ)")
    faq_html = """
<div style="line-height: 1.8;">
<span style='font-size:1.25em; font-weight:bold;'>Who should create the plan – the RDL or the BDL?</span><br>
At this point we are still working on standardizing this process. Please collaborate with your RDL/BDL on the initial build. It is important to ensure this only occurs once as only the most recent build will be updated.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>Where will I be able to find my plan?</span><br>
All plans are generated in the Growth, New Product Smartsheet workspace, and put into the appropriate initiative area folder. <a href="https://app.smartsheet.com/browse/workspaces/GVmPC5VHjjQgWCPf6XGJ4Xvmg9vjCPFJfpGM93c1" target="_blank" style="color:#0074cc; text-decoration:underline;">Link to the workspace</a>.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>When should the PMAT dashboard be created?</span><br>
The PMAT dashboard for a project can be created duing the Aha - Approved Planning phase, as long as there are Aha impacts. It is possible to create one before there is a Strategic Theme, however, it is recommended to wait until there is one.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>If I have accidentally created multiple plans, which one will get updated?</span><br>
Only the most recently created plan will be updated. Please delete older versions or keep in mind that these will not be automatically updated.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>What criteria is used to bring capabilities / features under the right Aha impacted application?</span><br>
The capabilities and features are brought into the Application View impacted apps based on the ‘Project’ field in Rally. Any Rally artifacts that are unmapped or do not have a value will be brough into the ‘Other’ section.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>I have PPM Optics tasks built out, but I don't see them in my plan.</span><br>
To bring in Optics, the Aha must have the Optics PRJ field populated with the correct PRJ..<br><br>

<span style='font-size:1.25em; font-weight:bold;'>I updated something in Rally and/or Optics and it is not showing up when I update my plan.</span><br>
Rally and PPM Optics data is brought in through a third-party data source which refreshes roughly every day. Please be mindful of this lag.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>If I drag and drop a capability to a new section, will this get altered / moved when I update my plan?</span><br>
No, capabilities only need to be moved around on initial build. Once it is moved, any new features or updates to the capability will occur in place.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>I want to change the format of my spreadsheet. Will adding new rows or columns impact the update process?</span><br>
No, the update process will simply look for new information and bring at a cell level, meaning new rows / columns will not interrupt the update process. Additionally, no manually created rows/columns will be overwritten by the update process.<br><br>

<span style='font-size:1.25em; font-weight:bold;'>Will reordering the columns impact the update process?</span><br>
For the most part, no. The only column that must remain in place is the ‘Work Breakdown’ column. The others are free to move around.<br>
</div>
"""
    st.markdown(faq_html, unsafe_allow_html=True)

# AI Help Bot Tab
with tab5:
    st.header("AI Help Bot")

    # Enterprise KB status (indexed automatically at startup)
    st.success("Enterprise Knowledge Base Loaded")
    st.caption(
        "This assistant answers questions using the enterprise knowledge base that is indexed automatically by the backend."
    )

    # Simple chat UI
    if "help_bot_messages" not in st.session_state:
        st.session_state.help_bot_messages = []

    for msg in st.session_state.help_bot_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.help_bot_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Thinking..."):
            try:
                import requests

                # Convert the chat history
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.help_bot_messages[:-1]
                ]
                payload = {
                    "query": prompt,
                    "chat_history": history,
                    "portfolio_filter": "all",
                }

                resp = requests.post(f"{config.API_BASE_URL}/llm", json=payload)
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("response", "Could not generate answer")
                sources = data.get("sources_used", [])

                if sources:
                    answer += f"\n\n*Sources: {', '.join(sources)}*"

                st.session_state.help_bot_messages.append(
                    {"role": "assistant", "content": answer}
                )
                with st.chat_message("assistant"):
                    st.markdown(answer)

            except Exception as e:
                st.error(f"Error calling Help Bot API: {e}")
