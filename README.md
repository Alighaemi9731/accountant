# VPN Panel Accounting System

A professional GUI application for managing VPN panel business accounting, invoice generation, and payment tracking.

## Features

### 🏠 Dashboard
- Real-time statistics overview
- Total earnings, payments, and balances
- Recent activity tracking
- Last backup information

### 📥 Backup Management
- Download backups from multiple VPN panels
- Progress tracking with visual indicators
- Backup file management and status monitoring
- Automatic data synchronization
- **Automatic UUID updates** from downloaded backups
- **Config file synchronization** with new admin UUIDs

### 💰 Accounting System
- Admin account management
- Payment recording and tracking
- Balance calculations
- Payment history
- Multiple payment methods support

### 📄 Invoice Management
- Automated invoice generation
- Customizable date ranges
- PDF invoice creation with Persian support
- Invoice status tracking
- Direct PDF opening from application

### ⚙️ Settings
- Configurable pricing per GB
- Payment card management
- Application preferences

## Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Your Panels
Edit `config.py` to add your VPN panel URLs and admin information:

```python
URLS = {
    "panel1": "https://your-panel1.com/backup-url",
    "panel2": "https://your-panel2.com/backup-url",
    # Add more panels as needed
}

TELEGRAM_ACCOUNTS = {
    "admin-uuid-1": [telegram_id, 'fa_number', price_per_gb],
    "admin-uuid-2": [telegram_id, 'fa_number', price_per_gb],
    # Add your admin accounts
}
```

### Step 3: Run the Application
```bash
python gui_app.py
```

## Usage Guide

### First Time Setup

1. **Launch the Application**
   - Run `python gui_app.py`
   - The application will create a SQLite database automatically

2. **Download Backups**
   - Go to the "Download Backups" tab
   - Click "Download All Backups"
   - Wait for all panels to download

3. **Generate Initial Invoices**
   - Go to the "Invoices" tab
   - Set your desired date range
   - Click "Generate New Invoices"

### Daily Operations

#### Recording Payments
1. Go to the "Accounting" tab
2. Select an admin from the list
3. Fill in payment details:
   - Amount
   - Payment method (Telegram, Bank Transfer, Cash)
   - Reference number
   - Notes
4. Click "Record Payment"

#### Generating New Invoices
1. Download latest backups from "Download Backups" tab
   - **UUIDs are automatically updated** from new backups
   - New admins are automatically added to the system
2. Go to "Invoices" tab
3. Set the invoice period
4. Click "Generate New Invoices"
5. PDFs will be created in the `invoices/` folder

#### Monitoring Business
- Use the Dashboard to see overall statistics
- Check individual admin balances in the Accounting tab
- View recent activity and payment history

## File Structure

```
GUI/
├── gui_app.py                 # Main GUI application
├── enhanced_data_processing.py # Enhanced data processing with accounting
├── main.py                    # Original command-line version
├── config.py                  # Configuration and panel URLs
├── file_management.py         # Backup download functionality
├── data_processing.py         # Original data processing
├── pdf_generation.py          # PDF invoice generation
├── utils.py                   # Utility functions
├── update_uuid.py            # UUID management
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── downloads/                 # Downloaded backup files
├── invoices/                  # Generated PDF invoices
└── vpn_accounting.db         # SQLite database (created automatically)
```

## Database Schema

### admin_accounts
- `uuid`: Primary key, admin UUID
- `name`: Admin display name
- `telegram_id`: Telegram ID
- `panel_number`: Panel number
- `fa_number`: FA number
- `price_per_gb`: Price per GB in Tomans
- `total_earned`: Total earnings
- `total_paid`: Total payments received
- `last_payment_date`: Last payment date
- `last_invoice_date`: Last invoice date
- `status`: Account status (active/inactive)

### payments
- `id`: Primary key
- `admin_uuid`: Foreign key to admin_accounts
- `amount`: Payment amount
- `payment_date`: Payment date
- `payment_method`: Payment method
- `reference`: Reference number
- `notes`: Additional notes

### invoices
- `id`: Primary key
- `admin_uuid`: Foreign key to admin_accounts
- `invoice_date`: Invoice date
- `usage_gb`: Usage in GB
- `amount`: Invoice amount
- `status`: Invoice status (paid/unpaid)
- `pdf_path`: Path to PDF file

### backup_data
- `id`: Primary key
- `panel_number`: Panel number
- `backup_date`: Backup date
- `data_hash`: MD5 hash of backup data
- `file_path`: Path to backup file

## Configuration

### Panel URLs
Add your VPN panel backup URLs in `config.py`:

```python
URLS = {
    "panel_name": "https://panel-url.com/backup-endpoint",
}
```

### Admin Accounts
Configure admin accounts with their UUIDs and pricing:

```python
TELEGRAM_ACCOUNTS = {
    "admin-uuid": [telegram_id, 'fa_number', price_per_gb],
}
```

**Note**: Each admin can have a different price per GB. The system will use the individual admin's price from this configuration for invoice calculations.

### Payment Cards
Add your payment card information:

```python
CARD_DETAILS = {
    "card_number": "Card Holder Name",
}
```

## Troubleshooting

### Common Issues

1. **Download Fails**
   - Check your internet connection
   - Verify panel URLs are correct
   - Ensure authentication credentials are valid

2. **PDF Generation Fails**
   - Make sure DejaVuSans.ttf font file is present
   - Check if downloads folder contains backup files
   - Verify date format in admin comments

3. **Database Errors**
   - Delete `vpn_accounting.db` to reset database
   - Restart the application

4. **Import Errors**
   - Install all dependencies: `pip install -r requirements.txt`
   - Check Python version (3.7+ required)

### Performance Tips

- Close other applications when downloading large backups
- Regularly clean old backup files from downloads folder
- Use SSD storage for better database performance

## Security Notes

- Keep your panel URLs and authentication credentials secure
- Regularly backup the `vpn_accounting.db` file
- Don't share your config.py file with sensitive information

## Support

For issues and questions:
1. Check the troubleshooting section
2. Verify all dependencies are installed
3. Ensure your panel URLs are accessible
4. Check the console output for error messages

## License

This application is designed for VPN panel business management. Please ensure compliance with your local laws and regulations. 