# VPN Panel Accounting System - Backup

**Backup Date:** 2025-07-29 13:23:21

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
