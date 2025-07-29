#!/usr/bin/env python3
"""
VPN Panel Accounting System - GitHub Backup Script
This script creates a backup of the code and database to GitHub with proper versioning.
"""

import os
import sys
import subprocess
import json
import shutil
from datetime import datetime
import sqlite3
import tempfile

# Configuration
GITHUB_USERNAME = "alighaemi9731"
GITHUB_REPO = "accountant"
BACKUP_DIR = "backup_temp"
DATABASE_FILE = "vpn_accounting.db"

def run_command(command, cwd=None, check=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=cwd, 
            check=check, 
            capture_output=True, 
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {e.stderr}")
        return None

def check_git_installed():
    """Check if git is installed"""
    result = run_command("git --version", check=False)
    if result is None or result.returncode != 0:
        print("❌ Git is not installed. Please install git first.")
        return False
    print("✅ Git is installed")
    return True

def check_gh_cli_installed():
    """Check if GitHub CLI is installed"""
    result = run_command("gh --version", check=False)
    if result is None or result.returncode != 0:
        print("❌ GitHub CLI (gh) is not installed. Please install it first.")
        print("Installation guide: https://cli.github.com/")
        return False
    print("✅ GitHub CLI is installed")
    return True

def check_gh_authenticated():
    """Check if GitHub CLI is authenticated"""
    result = run_command("gh auth status", check=False)
    if result is None or result.returncode != 0:
        print("❌ GitHub CLI is not authenticated. Please run 'gh auth login' first.")
        return False
    print("✅ GitHub CLI is authenticated")
    return True

def create_backup_directory():
    """Create a temporary backup directory"""
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
    os.makedirs(BACKUP_DIR)
    print(f"✅ Created backup directory: {BACKUP_DIR}")

def copy_files_to_backup():
    """Copy necessary files to backup directory"""
    files_to_backup = [
        "*.py",
        "*.md",
        "*.txt",
        "*.ttf",
        "*.json",
        ".gitignore"
    ]
    
    # Copy Python files and other important files
    for pattern in files_to_backup:
        if pattern == "*.py":
            # Copy all Python files
            for file in os.listdir("."):
                if file.endswith(".py"):
                    shutil.copy2(file, BACKUP_DIR)
        elif pattern == "*.md":
            # Copy markdown files
            for file in os.listdir("."):
                if file.endswith(".md"):
                    shutil.copy2(file, BACKUP_DIR)
        elif pattern == "*.txt":
            # Copy text files
            for file in os.listdir("."):
                if file.endswith(".txt"):
                    shutil.copy2(file, BACKUP_DIR)
        elif pattern == "*.ttf":
            # Copy font files
            for file in os.listdir("."):
                if file.endswith(".ttf"):
                    shutil.copy2(file, BACKUP_DIR)
        elif pattern == "*.json":
            # Copy JSON files (but not backup files)
            for file in os.listdir("."):
                if file.endswith(".json") and not file.startswith("backup"):
                    shutil.copy2(file, BACKUP_DIR)
        elif pattern == ".gitignore":
            # Copy gitignore if it exists
            if os.path.exists(".gitignore"):
                shutil.copy2(".gitignore", BACKUP_DIR)
    
    # Copy database file if it exists
    if os.path.exists(DATABASE_FILE):
        shutil.copy2(DATABASE_FILE, BACKUP_DIR)
        print(f"✅ Copied database: {DATABASE_FILE}")
    else:
        print(f"⚠️  Database file not found: {DATABASE_FILE}")
    
    print("✅ Copied all necessary files to backup directory")

def create_readme_for_backup():
    """Create a README file for the backup"""
    backup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    readme_content = f"""# VPN Panel Accounting System - Backup

**Backup Date:** {backup_time}

## Files Included in This Backup

### Core Application Files
- `gui_app.py` - Main GUI application
- `enhanced_data_processing.py` - Enhanced data processing with accounting
- `pdf_generation.py` - PDF invoice generation
- `data_processing.py` - Original data processing
- `file_management.py` - Backup download functionality
- `utils.py` - Utility functions
- `update_uuid.py` - UUID management
- `main.py` - Command-line version
- `run_app.py` - Quick start script

### Configuration Files
- `config.py` - Panel URLs and admin configuration
- `config_backup.py` - Backup configuration
- `requirements.txt` - Python dependencies

### Database
- `vpn_accounting.db` - SQLite database with all accounting data

### Documentation
- `README.md` - Main documentation
- `QUICK_START.md` - Quick start guide

### Font Files
- `DejaVuSans.ttf` - Persian font for PDF generation

## How to Restore

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python gui_app.py`

## Backup Information

- **Backup Type:** Full code and database backup
- **Excluded:** downloads/ and invoices/ folders (regenerated data)
- **Database Status:** Complete with all admin accounts, payments, and invoice history

---
*This backup was created automatically by the backup script.*
"""
    
    with open(os.path.join(BACKUP_DIR, "BACKUP_README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("✅ Created backup README file")

def get_database_info():
    """Get information about the database for the backup description"""
    if not os.path.exists(DATABASE_FILE):
        return "Database file not found"
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get admin count
        cursor.execute("SELECT COUNT(*) FROM admin_accounts WHERE status = 'active'")
        admin_count = cursor.fetchone()[0]
        
        # Get total earned
        cursor.execute("SELECT SUM(total_earned) FROM admin_accounts")
        total_earned = cursor.fetchone()[0] or 0
        
        # Get total paid
        cursor.execute("SELECT SUM(total_paid) FROM admin_accounts")
        total_paid = cursor.fetchone()[0] or 0
        
        # Get payment count
        cursor.execute("SELECT COUNT(*) FROM payments")
        payment_count = cursor.fetchone()[0]
        
        # Get invoice count
        cursor.execute("SELECT COUNT(*) FROM invoice_additions")
        invoice_count = cursor.fetchone()[0]
        
        conn.close()
        
        return f"Active Admins: {admin_count}, Total Earned: {total_earned:,.0f}, Total Paid: {total_paid:,.0f}, Payments: {payment_count}, Invoices: {invoice_count}"
    
    except Exception as e:
        return f"Database error: {str(e)}"

def initialize_git_repo():
    """Initialize git repository in backup directory"""
    os.chdir(BACKUP_DIR)
    
    # Initialize git repository
    result = run_command("git init")
    if result is None:
        return False
    
    # Add all files
    result = run_command("git add .")
    if result is None:
        return False
    
    # Create initial commit
    backup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"Backup: {backup_time}"
    result = run_command(f'git commit -m "{commit_message}"')
    if result is None:
        return False
    
    print("✅ Initialized git repository")
    return True

def push_to_github():
    """Push the backup to GitHub repository"""
    print("📤 Pushing to GitHub...")
    
    # Add remote origin
    remote_cmd = f"git remote add origin https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"
    result = run_command(remote_cmd, check=False)
    
    # Push to main branch
    push_cmd = "git push -u origin main"
    result = run_command(push_cmd, check=False)
    
    if result is None or result.returncode != 0:
        # Try master branch if main fails
        push_cmd = "git push -u origin master"
        result = run_command(push_cmd, check=False)
        
        if result is None or result.returncode != 0:
            print("⚠️  Could not push to GitHub")
            print(f"   Error: {result.stderr if result else 'Unknown error'}")
            return False
    
    print("✅ Pushed to GitHub")
    return True

def create_local_backup():
    """Create a local backup as fallback"""
    backup_time = datetime.now()
    timestamp = backup_time.strftime('%Y%m%d-%H%M%S')
    local_backup_dir = f"backup_local_{timestamp}"
    
    print(f"📁 Creating local backup: {local_backup_dir}")
    
    # Go back to original directory if we're in backup_temp
    if os.getcwd().endswith(BACKUP_DIR):
        os.chdir("..")
    
    # Copy backup_temp to local backup
    if os.path.exists(BACKUP_DIR):
        shutil.copytree(BACKUP_DIR, local_backup_dir)
        print(f"✅ Local backup created: {local_backup_dir}")
        print(f"📋 Location: {os.path.abspath(local_backup_dir)}")
        return True
    else:
        print("❌ No backup files found to copy")
        return False

def create_github_release():
    """Create a GitHub release with the backup"""
    backup_time = datetime.now()
    tag_name = f"backup-{backup_time.strftime('%Y%m%d-%H%M%S')}"
    release_title = f"Backup - {backup_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Get database info for description
    db_info = get_database_info()
    
    release_description = f"""## VPN Panel Accounting System - Automated Backup

**Backup Date:** {backup_time.strftime('%Y-%m-%d %H:%M:%S')}

### What's Included
- Complete source code
- SQLite database with all accounting data
- Configuration files
- Documentation
- Font files for PDF generation

### Database Status
{db_info}

### Files Backed Up
- All Python source files
- Configuration files (config.py, requirements.txt)
- Database file (vpn_accounting.db)
- Documentation (README.md, QUICK_START.md)
- Font files (DejaVuSans.ttf)

### Excluded Files
- downloads/ folder (regenerated data)
- invoices/ folder (regenerated PDFs)
- Python cache files
- Temporary files

### How to Restore
1. Download this release
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python gui_app.py`

---
*This backup was created automatically by the backup script.*
"""
    
    # First, check if repository exists
    print("🔍 Checking repository existence...")
    check_repo_cmd = f"gh repo view {GITHUB_USERNAME}/{GITHUB_REPO}"
    result = run_command(check_repo_cmd, check=False)
    
    if result is None or result.returncode != 0:
        print(f"❌ Repository {GITHUB_USERNAME}/{GITHUB_REPO} not found")
        print("📝 Creating repository...")
        create_repo_cmd = f"gh repo create {GITHUB_USERNAME}/{GITHUB_REPO} --private --description 'VPN Panel Accounting System Backups'"
        result = run_command(create_repo_cmd, check=False)
        if result is None or result.returncode != 0:
            print(f"❌ Failed to create repository: {result.stderr if result else 'Unknown error'}")
            print("📝 Please create the repository manually at https://github.com/new")
            return False
        print("✅ Repository created successfully")
    
    # Create release using GitHub CLI with better error handling
    print("📤 Creating GitHub release...")
    release_cmd = f'''gh release create {tag_name} --title "{release_title}" --notes "{release_description}" --repo {GITHUB_USERNAME}/{GITHUB_REPO}'''
    
    # Use timeout to prevent hanging
    try:
        result = subprocess.run(
            release_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            print(f"❌ Failed to create GitHub release:")
            print(f"   Error: {result.stderr}")
            print(f"   Command: {release_cmd}")
            return False
        
        print(f"✅ Created GitHub release: {tag_name}")
        print(f"📋 Release URL: https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO}/releases/tag/{tag_name}")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ GitHub release creation timed out (60 seconds)")
        print("📝 This might be due to network issues or GitHub API limits")
        return False
    except Exception as e:
        print(f"❌ Unexpected error creating release: {e}")
        return False

def cleanup():
    """Clean up temporary files"""
    os.chdir("..")  # Go back to original directory
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
        print(f"✅ Cleaned up temporary directory: {BACKUP_DIR}")

def main():
    """Main backup function"""
    print("🚀 Starting VPN Panel Accounting System Backup")
    print("=" * 50)
    
    # Check prerequisites
    if not check_git_installed():
        return False
    
    if not check_gh_cli_installed():
        return False
    
    if not check_gh_authenticated():
        return False
    
    print("\n📋 Backup Configuration:")
    print(f"   GitHub Username: {GITHUB_USERNAME}")
    print(f"   Repository: {GITHUB_REPO}")
    print(f"   Database File: {DATABASE_FILE}")
    
    # Create backup
    print("\n📦 Creating backup...")
    create_backup_directory()
    copy_files_to_backup()
    create_readme_for_backup()
    
    # Initialize git and create release
    print("\n🔗 Creating GitHub release...")
    if not initialize_git_repo():
        print("❌ Failed to initialize git repository")
        cleanup()
        return False
    
    # Try to push to GitHub first
    if not push_to_github():
        print("❌ Failed to push to GitHub")
        print("📁 Creating local backup as fallback...")
        if create_local_backup():
            print("✅ Local backup created successfully!")
            print("📋 You can find your backup in the local directory")
        else:
            print("❌ Failed to create local backup")
        cleanup()
        return False
    
    if not create_github_release():
        print("❌ Failed to create GitHub release")
        print("\n💡 Troubleshooting tips:")
        print("   1. Check your internet connection")
        print("   2. Verify GitHub CLI authentication: gh auth status")
        print("   3. Try creating the repository manually at https://github.com/new")
        print("   4. Check GitHub API limits")
        
        # Create local backup as fallback
        print("\n📁 Creating local backup as fallback...")
        if create_local_backup():
            print("✅ Local backup created successfully!")
            print("📋 You can find your backup in the local directory")
        else:
            print("❌ Failed to create local backup")
        
        cleanup()
        return False
    
    # Cleanup
    cleanup()
    
    print("\n✅ Backup completed successfully!")
    print("🎉 Your code and database have been backed up to GitHub")
    print(f"📋 Repository: https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 