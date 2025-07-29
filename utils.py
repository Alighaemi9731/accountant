
import json
import shutil
from unidecode import unidecode
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display
import os

def read_json_file(file_path):
    with open(file_path, 'r', encoding="utf-8") as file:
        data = json.load(file)
    return data

def delete_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return  # Exit the function without attempting deletion
    try:
        shutil.rmtree(folder_path)
        print(f"Folder '{folder_path}' and its contents deleted successfully.")
    except OSError as e:
        print(f"Error deleting folder '{folder_path}': {e}")


def find_descendants(selected_admin_uuid, admin_users, descendants=None, processed_uuids=None):
    if descendants is None:
        descendants = []
    if processed_uuids is None:
        processed_uuids = set()

    for admin in admin_users:
        admin_uuid = admin.get('uuid')
        if admin.get('parent_admin_uuid') == selected_admin_uuid and admin_uuid not in processed_uuids:
            descendants.append(admin)
            processed_uuids.add(admin_uuid)
            find_descendants(admin_uuid, admin_users, descendants, processed_uuids)

    return descendants

def convert_non_ascii_to_ascii(input_text):
    return unidecode(input_text)

def parse_date(date_string):
    if date_string is None:
        return None
    for date_format in ["%Y-%m-%d", "%Y %m %d", "%Y/%m/%d"]:
        try:
            return datetime.strptime(date_string, date_format)
        except ValueError:
            continue
    return None

# Function to reshape and reorder RTL text
def reshape_rtl_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)