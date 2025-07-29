from file_management import download_all_backup_files
from data_processing import process_invoices
from utils import delete_folder
from update_uuid import update_uuid
import os

def main():

    # download backups
    download_all_backup_files()

    # uuid update (now integrated into GUI - use gui_app.py instead)
    update_uuid()

    # delete pre invoices
    folder_to_delete = os.path.join("invoices")  # Replace with the actual path
    delete_folder(folder_to_delete)

    # generate new invoices
    process_invoices()

    print("Note: For GUI version with automatic UUID updates, run: python gui_app.py")


if __name__ == "__main__":
    main()
