import os
import requests
from config import URLS
import uuid

def extract_uuid(url):
    # Find UUIDs in the URL using uuid.UUID
    uuids = [part for part in url.split('/') if len(part) == 36 and uuid.UUID(part, version=4)]
    if uuids:
        return uuids[0]  # return the first found UUID
    else:
        return None

def download_backup(url, index):
    # Extracting secret code (UUID) from URL
    secret_code = extract_uuid(url)
    
    # Modify URL to remove UUID part if present
    modified_url = '/'.join(part for part in url.split('/') if part != secret_code)
    
    # Sending a GET request with or without Basic Authentication based on the presence of secret code
    response = requests.get(modified_url, auth=(secret_code, ''))
    if response.status_code != 200:
        response = requests.get(url)

    if response.status_code == 200:
        print("Backup downloaded successfully for:", url)
        # Accessing and saving the content as JSON file
        backup_content = response.content
        file_name = os.path.join('downloads', f'backup{index}.json')
        with open(file_name, 'wb') as file:
            file.write(backup_content)
        print("Backup saved as", file_name)
    else:
        print("Error downloading backup for:", url, "Status code:", response.status_code, "Reason:", response.reason)

def download_all_backup_files():

    # Create a directory to store downloaded backups
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Loop through URLs and download backups
    for index, (name, url) in enumerate(URLS.items(), start=1):
        download_backup(url, index)
