from pdf_generation import create_invoices
import os
from utils import read_json_file, find_descendants
from datetime import datetime, timedelta
import sqlite3
from decimal import Decimal
from config import TELEGRAM_ACCOUNTS

class EnhancedDataProcessor:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.cursor = db_connection.cursor()
    
    def process_invoices_with_accounting(self, start_date=None, end_date=None, add_to_accounts=False):
        """
        Process invoices and update accounting database with earnings
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() - timedelta(days=1)
        
        # Find the backup data files path
        downloads_folder = "downloads"
        if not os.path.exists(downloads_folder):
            raise Exception("Downloads folder not found. Please download backups first.")
        
        json_file_paths = [os.path.join(downloads_folder, filename) 
                          for filename in os.listdir(downloads_folder) 
                          if filename.endswith(".json")]
        json_file_paths.sort()
        
        panel_number = 1
        total_earnings = 0
        processed_admins = set()  # Track processed admins to avoid duplicates
        
        for json_file in json_file_paths:
            data = read_json_file(json_file)
            admin_users = data.get('admin_users', [])
            
            for admin in admin_users:
                # Only process main admins (not Owner, comment != '-', and not already processed)
                if ((admin['name'] != 'Owner') & 
                    (admin['comment'] != '-') & 
                    (admin['uuid'] not in processed_admins)):
                    
                    # Use the provided start_date instead of database last_invoice_date
                    # This ensures consistent date ranges for invoice generation
                    if start_date:
                        prev_invoice_date = start_date
                    else:
                        # Fallback to database last_invoice_date if no start_date provided
                        last_invoice_date = self.get_last_invoice_date(admin['uuid'])
                        if last_invoice_date:
                            prev_invoice_date = last_invoice_date
                        else:
                            # Parse comment as date or use default
                            prev_invoice_date = self.parse_comment_date(admin['comment'])
                    
                    # Find ALL descendants (including those with comment = '-')
                    descendants = [admin]
                    descendant_admins = find_descendants(admin['uuid'], admin_users, descendants)
                    
                    # Mark all descendants as processed to avoid duplicate processing
                    for desc_admin in descendant_admins:
                        processed_admins.add(desc_admin['uuid'])
                    
                    # Calculate earnings for this admin and all descendants
                    print(f"Processing admin {admin.get('name', 'Unknown')} from {prev_invoice_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                    admin_earnings = self.calculate_admin_earnings(
                        descendant_admins, 
                        data.get('users', []), 
                        prev_invoice_date, 
                        end_date,
                        panel_number
                    )
                    
                    # Generate PDF invoices FIRST (before updating database)
                    # This ensures the remainder calculation uses only previous amounts
                    # The PDF will show: current invoice amounts + previous unpaid remainder
                    create_invoices(descendant_admins, data.get('users', []), 
                                  prev_invoice_date.strftime('%Y-%m-%d'), 
                                  panel_number, [0], end_date.strftime('%Y-%m-%d'))
                    
                    # Update database with earnings for the main admin only AFTER generating PDFs
                    # This prevents double-counting current amounts as "previous remainder"
                    if add_to_accounts:
                        self.update_admin_earnings(admin['uuid'], admin_earnings)
                        # Track the invoice addition
                        self.track_invoice_addition(admin['uuid'], admin_earnings, start_date, end_date)
                    
                    total_earnings += admin_earnings
            
            panel_number += 1
        
        return total_earnings
    
    def get_last_invoice_date(self, admin_uuid):
        """Get the last invoice date for an admin from database"""
        self.cursor.execute("""
            SELECT last_invoice_date FROM admin_accounts 
            WHERE uuid = ? AND last_invoice_date IS NOT NULL
        """, (admin_uuid,))
        
        result = self.cursor.fetchone()
        if result and result[0]:
            try:
                return datetime.strptime(result[0], '%Y-%m-%d')
            except:
                return None
        return None
    
    def parse_comment_date(self, comment):
        """Parse comment field as date or return default date"""
        if not comment or comment == '-':
            return datetime(2023, 1, 1)
        
        # Try to parse the comment as a date
        date_formats = ['%Y-%m-%d', '%Y %m %d', '%Y/%m/%d']
        for fmt in date_formats:
            try:
                return datetime.strptime(comment, fmt)
            except:
                continue
        
        # If parsing fails, return default date
        return datetime(2023, 1, 1)
    
    def calculate_admin_earnings(self, descendant_admins, users, start_date, end_date, panel_number):
        """Calculate total earnings for an admin and their descendants"""
        total_earnings = 0
        
        # Find the main admin (parent) to get their price
        parent_uuid = None
        for admin in descendant_admins:
            admin_uuid = admin.get('uuid')
            if admin_uuid in TELEGRAM_ACCOUNTS:
                parent_uuid = admin_uuid
                break
        
        for admin in descendant_admins:
            admin_uuid = admin.get('uuid')
            
            # Get admin's price per GB (use parent's price for all)
            price_per_gb = self.get_admin_price_per_gb(admin_uuid, parent_uuid)
            
            # Filter users added by this admin within the date range
            # Exclude users with usage_limit_GB equal to 1
            filtered_users = [
                user for user in users 
                if user.get('added_by_uuid') == admin_uuid 
                and user.get('start_date') is not None
                and start_date < datetime.strptime(user.get('start_date'), "%Y-%m-%d") <= end_date
                and user.get('usage_limit_GB', 0) != 1
            ]
            
            # Calculate usage and earnings
            total_usage = sum(user.get('usage_limit_GB', 0) for user in filtered_users)
            admin_earnings = total_usage * price_per_gb
            
            total_earnings += admin_earnings
            
            # Store invoice data in database for main admins only (for tracking purposes)
            if total_usage > 0:  # Only store if there's actual usage
                self.store_invoice_data(admin_uuid, end_date, total_usage, admin_earnings)
        
        return total_earnings
    
    def get_admin_price_per_gb(self, admin_uuid, parent_uuid=None):
        """Get admin's price per GB from TELEGRAM_ACCOUNTS configuration"""
        try:
            # Import config to get TELEGRAM_ACCOUNTS
            import config
            from config import TELEGRAM_ACCOUNTS
            
            # If this is a descendant admin, use parent's price
            if parent_uuid and parent_uuid in TELEGRAM_ACCOUNTS:
                return TELEGRAM_ACCOUNTS[parent_uuid][2]  # Parent's price per GB
            
            # Get price from TELEGRAM_ACCOUNTS configuration for main admin
            if admin_uuid in TELEGRAM_ACCOUNTS:
                return TELEGRAM_ACCOUNTS[admin_uuid][2]  # Price per GB is at index 2
            else:
                # Fallback to database if not in config
                self.cursor.execute("""
                    SELECT price_per_gb FROM admin_accounts WHERE uuid = ?
                """, (admin_uuid,))
                
                result = self.cursor.fetchone()
                return result[0] if result else 1400  # Default price
                
        except ImportError:
            # If config import fails, use database
            self.cursor.execute("""
                SELECT price_per_gb FROM admin_accounts WHERE uuid = ?
            """, (admin_uuid,))
            
            result = self.cursor.fetchone()
            return result[0] if result else 1400  # Default price
    
    def update_admin_earnings(self, admin_uuid, earnings):
        """Update admin's total earnings in database"""
        # Only update earnings for admins that exist in the database
        # (main admins, not descendants)
        self.cursor.execute("SELECT uuid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
        if self.cursor.fetchone():
            self.cursor.execute("""
                UPDATE admin_accounts 
                SET total_earned = total_earned + ?, last_invoice_date = ?
                WHERE uuid = ?
            """, (earnings, datetime.now().strftime('%Y-%m-%d'), admin_uuid))
            
            self.conn.commit()
    
    def track_invoice_addition(self, admin_uuid, amount, start_date, end_date):
        """Track invoice addition with date and period"""
        self.cursor.execute("""
            INSERT INTO invoice_additions (admin_uuid, amount, addition_date, invoice_period_start, invoice_period_end)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_uuid, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
              start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        
        self.conn.commit()
    
    def store_invoice_data(self, admin_uuid, invoice_date, usage_gb, amount):
        """Store invoice data in database"""
        # Only store invoice data for admins that exist in the database
        # (main admins, not descendants)
        self.cursor.execute("SELECT uuid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
        if self.cursor.fetchone():
            # Find the PDF file path
            pdf_path = self.find_invoice_pdf(admin_uuid, invoice_date)
            
            self.cursor.execute("""
                INSERT INTO invoices (admin_uuid, invoice_date, usage_gb, amount, status, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (admin_uuid, invoice_date.strftime('%Y-%m-%d'), usage_gb, amount, 'unpaid', pdf_path))
            
            self.conn.commit()
    
    def find_invoice_pdf(self, admin_uuid, invoice_date):
        """Find the PDF file path for an invoice"""
        # This would need to be implemented based on your PDF naming convention
        # For now, return a placeholder
        return f"invoices/{admin_uuid}_{invoice_date.strftime('%Y%m%d')}.pdf"
    
    def get_admin_balance(self, admin_uuid):
        """Get admin's current balance (earned - paid)"""
        self.cursor.execute("""
            SELECT total_earned, total_paid FROM admin_accounts WHERE uuid = ?
        """, (admin_uuid,))
        
        result = self.cursor.fetchone()
        if result:
            earned, paid = result
            return (earned or 0) - (paid or 0)
        return 0
    
    def get_payment_history(self, admin_uuid, limit=10):
        """Get payment history for an admin"""
        self.cursor.execute("""
            SELECT payment_date, amount, payment_method, reference, notes
            FROM payments 
            WHERE admin_uuid = ?
            ORDER BY payment_date DESC
            LIMIT ?
        """, (admin_uuid, limit))
        
        return self.cursor.fetchall()
    
    def get_invoice_history(self, admin_uuid, limit=10):
        """Get invoice history for an admin"""
        self.cursor.execute("""
            SELECT invoice_date, usage_gb, amount, status
            FROM invoices 
            WHERE admin_uuid = ?
            ORDER BY invoice_date DESC
            LIMIT ?
        """, (admin_uuid, limit))
        
        return self.cursor.fetchall()
    
    def mark_invoice_as_paid(self, invoice_id):
        """Mark an invoice as paid"""
        self.cursor.execute("""
            UPDATE invoices SET status = 'paid' WHERE id = ?
        """, (invoice_id,))
        
        self.conn.commit()
    
    def get_total_statistics(self):
        """Get total statistics for dashboard"""
        # Total admins
        self.cursor.execute("SELECT COUNT(*) FROM admin_accounts WHERE status = 'active'")
        total_admins = self.cursor.fetchone()[0]
        
        # Total earned
        self.cursor.execute("SELECT SUM(total_earned) FROM admin_accounts")
        total_earned = self.cursor.fetchone()[0] or 0
        
        # Total paid
        self.cursor.execute("SELECT SUM(total_paid) FROM admin_accounts")
        total_paid = self.cursor.fetchone()[0] or 0
        
        # Total balance
        total_balance = total_earned - total_paid
        
        # Recent payments
        self.cursor.execute("""
            SELECT COUNT(*), SUM(amount) FROM payments 
            WHERE payment_date >= date('now', '-30 days')
        """)
        recent_payments = self.cursor.fetchone()
        recent_payment_count = recent_payments[0] or 0
        recent_payment_amount = recent_payments[1] or 0
        
        return {
            'total_admins': total_admins,
            'total_earned': total_earned,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'recent_payment_count': recent_payment_count,
            'recent_payment_amount': recent_payment_amount
        }
    
    def get_admin_details(self, admin_uuid):
        """Get detailed information about an admin"""
        self.cursor.execute("""
            SELECT name, telegram_id, panel_number, fa_number, price_per_gb,
                   total_earned, total_paid, last_payment_date, last_invoice_date, status
            FROM admin_accounts WHERE uuid = ?
        """, (admin_uuid,))
        
        return self.cursor.fetchone()
    
    def update_admin_price(self, admin_uuid, new_price):
        """Update admin's price per GB"""
        self.cursor.execute("""
            UPDATE admin_accounts SET price_per_gb = ? WHERE uuid = ?
        """, (new_price, admin_uuid))
        
        self.conn.commit()
    
    def add_new_admin(self, uuid, name, telegram_id, panel_number, fa_number, price_per_gb=1400):
        """Add a new admin to the system"""
        self.cursor.execute("""
            INSERT INTO admin_accounts (uuid, name, telegram_id, panel_number, fa_number, price_per_gb)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uuid, name, telegram_id, panel_number, fa_number, price_per_gb))
        
        self.conn.commit()
    
    def deactivate_admin(self, admin_uuid):
        """Deactivate an admin account"""
        self.cursor.execute("""
            UPDATE admin_accounts SET status = 'inactive' WHERE uuid = ?
        """, (admin_uuid,))
        
        self.conn.commit()
    
    def get_main_admins_from_backups(self):
        """Get main admins (those with comment != '-') from backup files"""
        main_admins = []
        downloads_folder = "downloads"
        
        if not os.path.exists(downloads_folder):
            return main_admins
            
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                try:
                    data = read_json_file(file_path)
                    for admin in data.get('admin_users', []):
                        if admin.get('name') != 'Owner' and admin.get('comment') != '-':
                            main_admins.append(admin)
                except:
                    continue
        
        return main_admins
    
    def get_descendant_admins(self, parent_uuid):
        """Get all descendant admins for a given parent UUID"""
        descendants = []
        downloads_folder = "downloads"
        
        if not os.path.exists(downloads_folder):
            return descendants
            
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                try:
                    data = read_json_file(file_path)
                    admin_users = data.get('admin_users', [])
                    
                    # Find the parent admin
                    parent_admin = None
                    for admin in admin_users:
                        if admin.get('uuid') == parent_uuid:
                            parent_admin = admin
                            break
                    
                    if parent_admin:
                        descendants = [parent_admin]
                        descendant_admins = find_descendants(parent_uuid, admin_users, descendants)
                        return descendant_admins
                        
                except:
                    continue
        
        return descendants

def process_invoices_with_accounting(db_connection, start_date=None, end_date=None, add_to_accounts=False):
    """Main function to process invoices with accounting integration"""
    # Reload config to get updated TELEGRAM_ACCOUNTS
    import importlib
    import config
    importlib.reload(config)
    
    processor = EnhancedDataProcessor(db_connection)
    return processor.process_invoices_with_accounting(start_date, end_date, add_to_accounts) 