# Quick Start Guide - VPN Panel Accounting System

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Your Panels
Edit `config.py` and add your panel URLs:

```python
URLS = {
    "mainsub": "https://your-panel1.com/backup-url",
    "sub2": "https://your-panel2.com/backup-url",
    # Add more panels...
}

TELEGRAM_ACCOUNTS = {
    "admin-uuid-1": [1, 'fa1', 1400],
    "admin-uuid-2": [2, 'fa2', 1400],
    # Add your admin accounts...
}
```

### Step 3: Launch the Application
```bash
python run_app.py
```

## 📋 First Time Setup

1. **Download Backups**
   - Click "Download Backups" tab
   - Click "Download All Backups"
   - Wait for completion

2. **Generate Invoices**
   - Click "Invoices" tab
   - Set date range (e.g., last 30 days)
   - Click "Generate New Invoices"
   - **Note**: UUIDs are automatically updated when downloading backups

3. **Record Payments**
   - Click "Accounting" tab
   - Select an admin
   - Enter payment details
   - Click "Record Payment"

## 💡 Daily Workflow

### Morning Routine
1. Download latest backups
2. Generate new invoices
3. Check dashboard for new earnings

### Payment Processing
1. Receive payment via Telegram
2. Record payment in Accounting tab
3. Update admin balance automatically

### End of Day
1. Review dashboard statistics
2. Check outstanding balances
3. Export reports if needed

## 🔧 Key Features

- **Dashboard**: Real-time business overview
- **Backup Management**: Automatic panel data sync
- **Accounting**: Payment tracking and balance management
- **Invoice Generation**: Professional PDF invoices
- **Settings**: Customizable pricing and payment methods

## 📊 Understanding the Interface

### Dashboard Tab
- Total earnings, payments, and balances
- Recent activity feed
- Last backup information

### Download Backups Tab
- Download all panel backups
- Progress tracking
- File management
- **Automatic UUID updates** from downloaded backups
- **Manual UUID update** option (Update UUIDs Only button)

### Accounting Tab
- Admin account list with balances
- Payment recording form
- Payment history

### Invoices Tab
- Generate new invoices
- View invoice history
- Open PDF files directly

### Settings Tab
- Configure pricing per GB
- Manage payment cards
- Application preferences

## 🎯 Pro Tips

1. **Regular Backups**: Download backups daily for accurate accounting
2. **Payment Tracking**: Record payments immediately when received
3. **Date Ranges**: Use appropriate date ranges for invoice generation
4. **Database Backup**: Regularly backup `vpn_accounting.db` file
5. **Monitor Balances**: Check admin balances regularly

## 🆘 Need Help?

- Check the main README.md for detailed documentation
- Verify all dependencies are installed
- Ensure panel URLs are accessible
- Check console output for error messages

## 📱 Mobile Access

While this is a desktop application, you can:
- Use remote desktop to access from mobile
- Set up automated backup downloads
- Use cloud storage for database backups

---

**Ready to start? Run `python run_app.py` and begin managing your VPN panel business professionally!** 