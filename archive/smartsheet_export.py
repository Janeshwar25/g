import upload
import csv
import time
from collections import defaultdict

WORKSPACE_ID = 8268500079798148
FOLDER_ID = 8409716968712068
SHEET_NAME = 'AI Generated Plan AHA 2278 Test'
FILE_PATH = 'new_plan.csv'

def smartsheet_upload(file, sheet_name = SHEET_NAME):
    smartsheet_client = upload.Smartsheet("Xp6HlTGmnxPx9fhE5lIrDuZ5nFvdb7P9KOxNQ")
    smartsheet_client.errors_as_exceptions(True)

    with open(file, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)
        data_rows = list(reader)

    columns = []

    for i, col_name in enumerate(headers):
        col_def = {
            'title' : col_name,
            'type' : 'TEXT_NUMBER'
        }
        if i == 0:
            col_def['primary'] = True
        columns.append(col_def)

    new_sheet_spec = upload.models.Sheet({
        'name' : sheet_name,
        'columns' : columns
    })

    created_sheet = smartsheet_client.Folders.create_sheet_in_folder(8409716968712068, new_sheet_spec).data
    sheet_id = created_sheet.id

    column_map = {col.title: col.id for col in created_sheet.columns}
    primary_col_title = headers[0]

    level_parents = {}

    for line in data_rows:
        full_value = line[0]
        indent_level = len(full_value) - len(full_value.lstrip(' '))
        task_name = full_value.strip()

        row = upload.models.Row()
        row.to_bottom = True

        cells = []
        for header, value in zip(headers, line):
            val = value.strip()
            if header == primary_col_title:
                val = task_name
            cells.append({'column_id' : column_map[header], 'value' : val})
        row.cells = cells

        if indent_level > 0 and (indent_level - 1) in level_parents:
            row.parent_id = level_parents[indent_level - 1]
        
        added_row = smartsheet_client.Sheets.add_rows(sheet_id, [row]).data[0]
        level_parents[indent_level] = added_row.id

# start_time = time.time()
# smartsheet_upload(FILE_PATH, "test 2")
# end_time = time.time()

# elapsed_time = end_time - start_time
# print(elapsed_time)