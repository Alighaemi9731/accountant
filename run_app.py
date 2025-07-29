#!/usr/bin/env python3
"""
VPN Panel Accounting System Launcher
"""

import sys
import subprocess
import importlib.util

def check_dependency(package_name):
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def install_dependency(package_name):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("VPN Panel Accounting System")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    
    print(f"Python version: {sys.version.split()[0]} ✓")
    
    # Required packages
    required_packages = [
        'tkinter',
        'requests',
        'reportlab',
        'arabic_reshaper',
        'bidi',
        'unidecode'
    ]
    
    missing_packages = []
    
    print("\nChecking dependencies...")
    for package in required_packages:
        if check_dependency(package):
            print(f"  {package} ✓")
        else:
            print(f"  {package} ✗")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        response = input("Would you like to install missing packages? (y/n): ")
        
        if response.lower() in ['y', 'yes']:
            print("\nInstalling missing packages...")
            for package in missing_packages:
                print(f"Installing {package}...")
                if install_dependency(package):
                    print(f"  {package} installed successfully ✓")
                else:
                    print(f"  Failed to install {package} ✗")
                    sys.exit(1)
        else:
            print("Please install the missing packages manually:")
            print("pip install -r requirements.txt")
            sys.exit(1)
    
    print("\nAll dependencies satisfied! ✓")
    
    # Check if config file exists
    try:
        import config
        print("Configuration file found ✓")
    except ImportError:
        print("Warning: config.py not found")
        print("Please create config.py with your panel URLs and admin information")
        response = input("Continue anyway? (y/n): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)
    
    # Launch the application
    print("\nLaunching VPN Panel Accounting System...")
    try:
        from gui_app import main as launch_app
        launch_app()
    except ImportError as e:
        print(f"Error: Could not import gui_app.py: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error launching application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 