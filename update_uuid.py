import os
import json
import re
import shutil  # For creating the backup
from config import TELEGRAM_ACCOUNTS

def update_uuid():

    # Directory containing backup JSON files
    BACKUP_FOLDER = "downloads"

    # Path to the config.py file
    CONFIG_FILE_PATH = 'config.py'
    CONFIG_BACKUP_PATH = 'config_backup.py'

    # Step 1: Create a backup of the original config.py
    if not os.path.exists(CONFIG_BACKUP_PATH):
        shutil.copy(CONFIG_FILE_PATH, CONFIG_BACKUP_PATH)
        print(f"Backup created: {CONFIG_BACKUP_PATH}")
    else:
        print(f"Backup already exists: {CONFIG_BACKUP_PATH}")

    # Step 2: Collect all uuids from backup JSON files
    uuids_from_json = set()
    admin_data = []

    for filename in os.listdir(BACKUP_FOLDER):
        if filename.startswith("backup") and filename.endswith(".json"):
            # Extract the index `i` from the filename (e.g., backup1.json -> 1)
            file_index = filename.replace("backup", "").replace(".json", "")
            fa_number = f"fa{file_index}"
            
            file_path = os.path.join(BACKUP_FOLDER, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                admins = data.get("admin_users", [])
                admin_data.extend([(admin, fa_number) for admin in admins])  # Include `fa_number` for each admin
                for admin in admins:
                    uuids_from_json.add(admin["uuid"])

    # Step 3: Filter TELEGRAM_ACCOUNTS to retain only uuids present in the JSON files
    filtered_accounts = {
        key: value for key, value in TELEGRAM_ACCOUNTS.items() if key in uuids_from_json
    }

    # Step 4: Identify and add new uuids with conditions
    for admin, fa_number in admin_data:
        uuid = admin["uuid"]
        name = admin["name"]
        comment = admin["comment"]

        # Check conditions and if the uuid is not in filtered_accounts
        if uuid not in filtered_accounts and name != "Owner" and comment != "-":
            # Add the new entry to filtered_accounts with the specified format
            filtered_accounts[uuid] = [3, fa_number, 1000]

    # Step 5: Format the dictionary to maintain inline style
    formatted_accounts = "{\n" + ",\n".join(
        f'    "{key}": {value}' for key, value in filtered_accounts.items()
    ) + "\n}"

    # Step 6: Update the TELEGRAM_ACCOUNTS in the config.py file
    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        config_data = f.read()

    # Use regex to locate and replace the TELEGRAM_ACCOUNTS assignment
    pattern = re.compile(r"TELEGRAM_ACCOUNTS\s*=\s*{.*?}", re.DOTALL)
    replacement = f"TELEGRAM_ACCOUNTS = {formatted_accounts}"

    if pattern.search(config_data):
        updated_config_data = pattern.sub(replacement, config_data)
    else:
        raise ValueError("TELEGRAM_ACCOUNTS definition not found in config.py")

    # Write the updated data back to the config.py file
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(updated_config_data)

    print("TELEGRAM_ACCOUNTS has been updated in config.py.")
