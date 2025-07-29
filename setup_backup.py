#!/usr/bin/env python3
"""
Setup script for VPN Panel Accounting System Backup
This script helps you set up the backup system and check prerequisites.
"""

import os
import sys
import subprocess
import json

def run_command(command, check=False):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=check, 
            capture_output=True, 
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        return None

def check_git():
    """Check if git is installed"""
    print("🔍 Checking Git installation...")
    result = run_command("git --version", check=False)
    if result and result.returncode == 0:
        print(f"✅ Git is installed: {result.stdout.strip()}")
        return True
    else:
        print("❌ Git is not installed")
        print("📥 Please install Git:")
        print("   macOS: brew install git")
        print("   Ubuntu/Debian: sudo apt-get install git")
        print("   Windows: Download from https://git-scm.com/")
        return False

def check_gh_cli():
    """Check if GitHub CLI is installed"""
    print("\n🔍 Checking GitHub CLI installation...")
    result = run_command("gh --version", check=False)
    if result and result.returncode == 0:
        print(f"✅ GitHub CLI is installed: {result.stdout.split()[2]}")
        return True
    else:
        print("❌ GitHub CLI is not installed")
        print("📥 Please install GitHub CLI:")
        print("   macOS: brew install gh")
        print("   Ubuntu/Debian: sudo apt-get install gh")
        print("   Windows: winget install GitHub.cli")
        print("   Or visit: https://cli.github.com/")
        return False

def check_gh_auth():
    """Check if GitHub CLI is authenticated"""
    print("\n🔍 Checking GitHub CLI authentication...")
    result = run_command("gh auth status", check=False)
    if result and result.returncode == 0:
        print("✅ GitHub CLI is authenticated")
        # Extract username from auth status
        for line in result.stdout.split('\n'):
            if 'Logged in to github.com as' in line:
                username = line.split('Logged in to github.com as ')[1].split(' ')[0]
                print(f"   Username: {username}")
        return True
    else:
        print("❌ GitHub CLI is not authenticated")
        print("🔐 Please authenticate with GitHub:")
        print("   Run: gh auth login")
        print("   Follow the prompts to authenticate")
        return False

def check_repository():
    """Check if the repository exists"""
    print("\n🔍 Checking repository existence...")
    result = run_command("gh repo view alighaemi9731/accountant", check=False)
    if result and result.returncode == 0:
        print("✅ Repository 'alighaemi9731/accountant' exists")
        return True
    else:
        print("❌ Repository 'alighaemi9731/accountant' not found")
        print("📝 Please create the repository first:")
        print("   1. Go to https://github.com/new")
        print("   2. Repository name: accountant")
        print("   3. Make it private (recommended)")
        print("   4. Click 'Create repository'")
        return False

def create_repository():
    """Create the repository if it doesn't exist"""
    print("\n🔍 Creating repository...")
    result = run_command("gh repo create alighaemi9731/accountant --private --description 'VPN Panel Accounting System Backups'", check=False)
    if result and result.returncode == 0:
        print("✅ Repository created successfully")
        return True
    else:
        print("❌ Failed to create repository")
        print("📝 Please create it manually at https://github.com/new")
        return False

def test_backup():
    """Test the backup script"""
    print("\n🧪 Testing backup script...")
    if os.path.exists("backup_to_github.py"):
        print("✅ Backup script found")
        print("🚀 You can now run: python backup_to_github.py")
        return True
    else:
        print("❌ Backup script not found")
        return False

def main():
    """Main setup function"""
    print("🔧 VPN Panel Accounting System - Backup Setup")
    print("=" * 50)
    
    all_good = True
    
    # Check Git
    if not check_git():
        all_good = False
    
    # Check GitHub CLI
    if not check_gh_cli():
        all_good = False
    
    # Check authentication
    if not check_gh_auth():
        all_good = False
    
    # Check repository
    if not check_repository():
        print("\n📝 Would you like to create the repository now? (y/n): ", end="")
        response = input().lower().strip()
        if response in ['y', 'yes']:
            if create_repository():
                print("✅ Repository created successfully")
            else:
                all_good = False
        else:
            all_good = False
    
    # Test backup script
    if not test_backup():
        all_good = False
    
    print("\n" + "=" * 50)
    if all_good:
        print("🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("   1. Run backup: python backup_to_github.py")
        print("   2. Check your GitHub repository for the release")
        print("   3. Repeat backup whenever you want to save your progress")
    else:
        print("❌ Setup incomplete. Please fix the issues above and run this script again.")
        print("\n📋 Common issues:")
        print("   - Install missing tools (Git, GitHub CLI)")
        print("   - Authenticate with GitHub: gh auth login")
        print("   - Create the repository manually if needed")
    
    return all_good

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 