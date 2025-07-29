from pdf_generation import create_invoices
import os
from utils import read_json_file, find_descendants

def process_invoices():
    # find the backup data files path
    downloads_folder = "downloads"
    json_file_paths = [os.path.join(downloads_folder, filename) for filename in os.listdir(downloads_folder) if filename.endswith(".json")]
    json_file_paths.sort()
    panel_number = 1
    dic = {}
    for json_file in json_file_paths:
        data = read_json_file(json_file)
        admin_users = data.get('admin_users', [])
        for admin in admin_users:
            if ((admin['name'] != 'Owner') & (admin['comment'] != '-')):
                if admin['name'] in dic.keys():
                    dic[admin['name']] += 1
                else:
                    dic[admin['name']] = 1
                prev_invoice_date = admin['comment']
                descendants = [admin]
                descendant_admins = find_descendants(admin['uuid'], admin_users, descendants)
                total_usage = [0]
                create_invoices(descendant_admins, data.get('users', []), prev_invoice_date, panel_number, total_usage)
        panel_number += 1

    print("\nrepeated ones:\n")
    for key, val in dic.items():
        if val > 1:
            print(key, val)