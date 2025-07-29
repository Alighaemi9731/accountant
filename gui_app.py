import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from datetime import datetime, timedelta
import threading
import importlib
from file_management import download_all_backup_files
from data_processing import process_invoices
from utils import delete_folder, read_json_file, find_descendants
import config
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

class VPNAccountingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VPN Panel Accounting System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize database
        self.init_database()
        
        # Create main container
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_download_tab()
        self.create_accounting_tab()
        self.create_invoices_tab()
        
        # Initialize admin accounts from config
        self.sync_admin_accounts_with_config()
        
        # Load initial data
        self.load_dashboard_data()
        
    def init_database(self):
        """Initialize SQLite database for accounting data"""
        self.conn = sqlite3.connect('vpn_accounting.db')
        self.cursor = self.conn.cursor()
        
        # Create tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_accounts (
                uuid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                telegram_id INTEGER,
                panel_number INTEGER,
                fa_number TEXT,
                price_per_gb INTEGER DEFAULT 1400,
                total_earned DECIMAL(15,2) DEFAULT 0,
                total_paid DECIMAL(15,2) DEFAULT 0,
                last_payment_date TEXT,
                last_invoice_date TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_uuid TEXT,
                amount DECIMAL(15,2),
                payment_date TEXT,
                payment_method TEXT,
                reference TEXT,
                notes TEXT,
                FOREIGN KEY (admin_uuid) REFERENCES admin_accounts (uuid)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_uuid TEXT,
                invoice_date TEXT,
                usage_gb INTEGER,
                amount DECIMAL(15,2),
                status TEXT DEFAULT 'unpaid',
                pdf_path TEXT,
                FOREIGN KEY (admin_uuid) REFERENCES admin_accounts (uuid)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_number INTEGER,
                backup_date TEXT,
                data_hash TEXT,
                file_path TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_additions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_uuid TEXT,
                amount DECIMAL(15,2),
                addition_date TEXT,
                invoice_period_start TEXT,
                invoice_period_end TEXT,
                FOREIGN KEY (admin_uuid) REFERENCES admin_accounts (uuid)
            )
        ''')
        
        self.conn.commit()
        

        
        self.conn.commit()
    
    def format_amount_for_display(self, amount):
        """Convert amount to display format (divide by 1000)"""
        if amount is None:
            return "0"
        return f"{amount / 1000:,.0f}"
    
    def parse_amount_from_input(self, input_text):
        """Convert input text to actual amount (multiply by 1000)"""
        if not input_text or input_text.strip() == "":
            return 0
        try:
            # Remove commas and convert to float
            clean_text = input_text.replace(',', '').strip()
            display_amount = float(clean_text)
            # Multiply by 1000 to get actual amount
            return int(display_amount * 1000)
        except ValueError:
            return 0
    
    def sync_admin_accounts_with_config(self):
        """Synchronize admin accounts with TELEGRAM_ACCOUNTS config - add new and remove deleted"""
        importlib.reload(config)  # ensures latest file content
        telegram_accounts = config.TELEGRAM_ACCOUNTS  # fresh dictionary
        
        new_admins_count = 0
        removed_admins_count = 0
        
        # Get all UUIDs currently in the database
        self.cursor.execute("SELECT uuid FROM admin_accounts")
        db_uuids = {row[0] for row in self.cursor.fetchall()}
        
        # Get all UUIDs from config
        config_uuids = set(telegram_accounts.keys())
        
        # Find admins to remove (in database but not in config)
        uuids_to_remove = db_uuids - config_uuids
        
        # Remove admins that are no longer in config
        for uuid in uuids_to_remove:
            # Check if admin has any financial data
            self.cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM payments WHERE admin_uuid = ?) as payment_count,
                    (SELECT COUNT(*) FROM invoice_additions WHERE admin_uuid = ?) as invoice_count,
                    total_earned, total_paid
                FROM admin_accounts WHERE uuid = ?
            """, (uuid, uuid, uuid))
            
            result = self.cursor.fetchone()
            if result:
                payment_count, invoice_count, total_earned, total_paid = result
                
                # If admin has financial data, mark as inactive instead of deleting
                if payment_count > 0 or invoice_count > 0 or (total_earned or 0) > 0 or (total_paid or 0) > 0:
                    self.cursor.execute("UPDATE admin_accounts SET status = 'inactive' WHERE uuid = ?", (uuid,))
                    print(f"Admin {uuid} marked as inactive (has financial data)")
                else:
                    # Safe to delete if no financial data
                    self.cursor.execute("DELETE FROM admin_accounts WHERE uuid = ?", (uuid,))
                    print(f"Admin {uuid} deleted (no financial data)")
                
                removed_admins_count += 1
        
        # Add new admins from config
        for uuid, data in telegram_accounts.items():
            telegram_id, fa_number, price_per_gb = data
            
            # Check if admin already exists
            self.cursor.execute("SELECT uuid FROM admin_accounts WHERE uuid = ?", (uuid,))
            if not self.cursor.fetchone():
                # Get admin name from backup files if available
                admin_name = self.get_admin_name_from_backups(uuid)
                
                # Use the price from the data tuple (already imported from config)
                price_per_gb = data[2]  # Price per GB is at index 2
                
                # Add all admins from TELEGRAM_ACCOUNTS to the database
                self.cursor.execute('''
                    INSERT INTO admin_accounts (uuid, name, telegram_id, panel_number, fa_number, price_per_gb)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (uuid, admin_name or f"Admin_{uuid[:8]}", telegram_id, telegram_id, fa_number, price_per_gb))
                
                new_admins_count += 1
                print(f"New admin added: {admin_name or f'Admin_{uuid[:8]}'} ({uuid})")
        
        # Update admin names from backup files
        self.update_admin_names_from_backups()
        
        self.conn.commit()
        
        # Return counts
        return new_admins_count, removed_admins_count
    
    def initialize_admin_accounts(self):
        """Initialize admin accounts from TELEGRAM_ACCOUNTS config (legacy method)"""
        new_admins_count, removed_admins_count = self.sync_admin_accounts_with_config()
        return new_admins_count
    
    def get_admin_name_from_backups(self, uuid):
        """Get admin name from backup files"""
        downloads_folder = "downloads"
        if not os.path.exists(downloads_folder):
            return None
            
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                try:
                    data = read_json_file(file_path)
                    for admin in data.get('admin_users', []):
                        if admin.get('uuid') == uuid:
                            return admin.get('name')
                except:
                    continue
        return None
    
    def update_admin_names_from_backups(self):
        """Update admin names in database from backup files"""
        downloads_folder = "downloads"
        if not os.path.exists(downloads_folder):
            return
        
        # Get all admin names from backup files
        admin_names = {}
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                try:
                    data = read_json_file(file_path)
                    for admin in data.get('admin_users', []):
                        uuid = admin.get('uuid')
                        name = admin.get('name')
                        if uuid and name:
                            admin_names[uuid] = name
                except:
                    continue
        
        # Update admin names in database
        for uuid, name in admin_names.items():
            self.cursor.execute("""
                UPDATE admin_accounts 
                SET name = ? 
                WHERE uuid = ? AND (name LIKE 'Admin_%' OR name IS NULL)
            """, (name, uuid))
        
        self.conn.commit()
    
    def create_dashboard_tab(self):
        """Create dashboard tab with overview statistics"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Title
        title_label = ttk.Label(dashboard_frame, text="VPN Panel Accounting Dashboard", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Statistics frame
        stats_frame = ttk.Frame(dashboard_frame)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Create statistics widgets
        self.total_admins_var = tk.StringVar(value="0")
        self.total_earned_var = tk.StringVar(value="0 تومان")
        self.total_paid_var = tk.StringVar(value="0 تومان")
        self.total_balance_var = tk.StringVar(value="0 تومان")
        self.last_backup_var = tk.StringVar(value="Never")
        
        # Statistics labels
        stats_data = [
            ("Total Admins", self.total_admins_var),
            ("Total Earned", self.total_earned_var),
            ("Total Paid", self.total_paid_var),
            ("Total Balance", self.total_balance_var),
            ("Last Backup", self.last_backup_var)
        ]
        
        for i, (label, var) in enumerate(stats_data):
            frame = ttk.Frame(stats_frame)
            frame.grid(row=i//3, column=i%3, padx=10, pady=10, sticky='ew')
            
            ttk.Label(frame, text=label, font=('Arial', 12, 'bold')).pack()
            ttk.Label(frame, textvariable=var, font=('Arial', 14)).pack()
        
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_frame, text="Recent Activity", padding=10)
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Activity treeview
        self.activity_tree = ttk.Treeview(activity_frame, columns=('Date', 'Admin', 'Action', 'Amount'), 
                                         show='headings', height=10)
        self.activity_tree.heading('Date', text='Date')
        self.activity_tree.heading('Admin', text='Admin')
        self.activity_tree.heading('Action', text='Action')
        self.activity_tree.heading('Amount', text='Amount')
        
        self.activity_tree.column('Date', width=150)
        self.activity_tree.column('Admin', width=200)
        self.activity_tree.column('Action', width=150)
        self.activity_tree.column('Amount', width=150)
        
        scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=scrollbar.set)
        
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        refresh_btn = ttk.Button(dashboard_frame, text="Refresh Dashboard", 
                                command=self.load_dashboard_data)
        refresh_btn.pack(pady=10)
    
    def create_download_tab(self):
        """Create download tab for managing backup downloads"""
        download_frame = ttk.Frame(self.notebook)
        self.notebook.add(download_frame, text="Download Backups")
        
        # Title
        title_label = ttk.Label(download_frame, text="Download Panel Backups", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Download controls frame
        controls_frame = ttk.LabelFrame(download_frame, text="Download Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Download button (handles everything automatically)
        self.download_btn = ttk.Button(controls_frame, text="Download All Backups", 
                                      command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(controls_frame, variable=self.progress_var, 
                                           maximum=len(config.URLS))
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        # Status label
        self.download_status = ttk.Label(controls_frame, text="Ready to download")
        self.download_status.pack(side=tk.RIGHT, padx=5)
        
        # Backup files frame
        backup_frame = ttk.LabelFrame(download_frame, text="Backup Files", padding=10)
        backup_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Backup treeview
        self.backup_tree = ttk.Treeview(backup_frame, 
                                       columns=('Panel', 'File', 'Size', 'Date', 'Status'), 
                                       show='headings', height=15)
        self.backup_tree.heading('Panel', text='Panel')
        self.backup_tree.heading('File', text='File Name')
        self.backup_tree.heading('Size', text='Size')
        self.backup_tree.heading('Date', text='Date')
        self.backup_tree.heading('Status', text='Status')
        
        self.backup_tree.column('Panel', width=100)
        self.backup_tree.column('File', width=200)
        self.backup_tree.column('Size', width=100)
        self.backup_tree.column('Date', width=150)
        self.backup_tree.column('Status', width=100)
        
        scrollbar = ttk.Scrollbar(backup_frame, orient=tk.VERTICAL, command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=scrollbar.set)
        
        self.backup_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load existing backup files
        self.load_backup_files()
    
    def create_accounting_tab(self):
        """Create accounting tab for managing admin accounts and payments"""
        accounting_frame = ttk.Frame(self.notebook)
        self.notebook.add(accounting_frame, text="Accounting")
        
        # Title
        title_label = ttk.Label(accounting_frame, text="Admin Account Management", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Main content frame
        self.accounting_content_frame = ttk.Frame(accounting_frame)
        self.accounting_content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create pages
        self.create_admin_list_page()
        self.create_admin_detail_page()
        
        # Show admin list page initially
        self.show_admin_list_page()
        
        # Load admin data
        self.load_admin_accounts()
    
    def create_admin_list_page(self):
        """Create the admin list page"""
        self.admin_list_page = ttk.Frame(self.accounting_content_frame)
        
        # Header with refresh button
        header_frame = ttk.Frame(self.admin_list_page)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Admin Accounts", font=('Arial', 14, 'bold')).pack(side=tk.LEFT)
        
        # Right side buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="🔄 Refresh Names", 
                  command=self.refresh_admin_names).pack(side=tk.RIGHT)
        
        # Search frame
        search_frame = ttk.Frame(self.admin_list_page)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_admins)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40, font=('Arial', 11))
        self.search_entry.pack(side=tk.LEFT, padx=(10, 0))
        self.search_entry.insert(0, "Type admin name or FA number...")
        self.search_entry.config(foreground='gray')
        self.search_entry.bind('<FocusIn>', self.on_search_focus_in)
        self.search_entry.bind('<FocusOut>', self.on_search_focus_out)
        
        # Clear search button
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(10, 0))
        
        # Admin treeview with scrollbars
        tree_frame = ttk.Frame(self.admin_list_page)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.admin_tree = ttk.Treeview(tree_frame, 
                                      columns=('Name', 'Panel', 'Earned', 'Paid', 'Balance'), 
                                      show='headings', height=20)
        self.admin_tree.heading('Name', text='Name')
        self.admin_tree.heading('Panel', text='FA Number')
        self.admin_tree.heading('Earned', text='Earned (K)')
        self.admin_tree.heading('Paid', text='Paid (K)')
        self.admin_tree.heading('Balance', text='Balance (K)')
        
        # Column widths
        self.admin_tree.column('Name', width=200, minwidth=150)
        self.admin_tree.column('Panel', width=100, minwidth=80)
        self.admin_tree.column('Earned', width=120, minwidth=100)
        self.admin_tree.column('Paid', width=120, minwidth=100)
        self.admin_tree.column('Balance', width=120, minwidth=100)
        
        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.admin_tree.yview)
        self.admin_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.admin_tree.xview)
        self.admin_tree.configure(xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.admin_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        # Configure grid weights
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind single-click event to open admin detail page
        self.admin_tree.bind('<ButtonRelease-1>', self.open_admin_detail_page)
        
        # Instructions with improved styling
        instruction_frame = ttk.Frame(self.admin_list_page)
        instruction_frame.pack(pady=10)
        
        instruction_label = ttk.Label(instruction_frame, 
                                     text="💡 Click on any admin to view their details", 
                                     font=('Arial', 10, 'italic'), foreground='#666666')
        instruction_label.pack()
        
        # Add a subtle separator
        separator = ttk.Separator(self.admin_list_page, orient='horizontal')
        separator.pack(fill=tk.X, padx=20, pady=5)
    
    def create_admin_detail_page(self):
        """Create the admin detail page"""
        self.admin_detail_page = ttk.Frame(self.accounting_content_frame)
        
        # Header with back button
        header_frame = ttk.Frame(self.admin_detail_page)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.back_btn = ttk.Button(header_frame, text="← Back to Admin List", 
                                  command=self.show_admin_list_page)
        self.back_btn.pack(side=tk.LEFT)
        
        self.selected_admin_title = ttk.Label(header_frame, text="", 
                                             font=('Arial', 14, 'bold'))
        self.selected_admin_title.pack(side=tk.RIGHT)
        
        # Main content area with scrollbar
        content_canvas = tk.Canvas(self.admin_detail_page, bg='white')
        content_scrollbar = ttk.Scrollbar(self.admin_detail_page, orient=tk.VERTICAL, 
                                         command=content_canvas.yview)
        self.content_scrollable_frame = ttk.Frame(content_canvas)
        
        self.content_scrollable_frame.bind(
            "<Configure>",
            lambda e: content_canvas.configure(scrollregion=content_canvas.bbox("all"))
        )
        
        content_canvas.create_window((0, 0), window=self.content_scrollable_frame, anchor="nw")
        content_canvas.configure(yscrollcommand=content_scrollbar.set)
        
        # Configure the scrollable frame to expand horizontally
        content_canvas.bind('<Configure>', lambda e: content_canvas.itemconfig(
            content_canvas.find_withtag("all")[0], width=e.width))
        

        
        # Pack canvas and scrollbar to fill the entire detail page
        content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Admin info section
        admin_info_frame = ttk.LabelFrame(self.content_scrollable_frame, text="Admin Information", padding=15)
        admin_info_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Admin details grid
        details_frame = ttk.Frame(admin_info_frame)
        details_frame.pack(fill=tk.X)
        
        # Row 1
        ttk.Label(details_frame, text="Name:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.admin_name_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.admin_name_var, font=('Arial', 11)).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Label(details_frame, text="FA Number:", font=('Arial', 11, 'bold')).grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.admin_fa_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.admin_fa_var, font=('Arial', 11)).grid(row=0, column=3, sticky=tk.W, pady=5, padx=(10, 0))
        
        # Row 2
        ttk.Label(details_frame, text="Total Earned:", font=('Arial', 11, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.admin_earned_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.admin_earned_var, font=('Arial', 11), foreground='green').grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Label(details_frame, text="Total Paid:", font=('Arial', 11, 'bold')).grid(row=1, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.admin_paid_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.admin_paid_var, font=('Arial', 11), foreground='blue').grid(row=1, column=3, sticky=tk.W, pady=5, padx=(10, 0))
        
        # Row 3 - Balance
        ttk.Label(details_frame, text="Remaining Balance:", font=('Arial', 12, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=10)
        self.admin_balance_var = tk.StringVar()
        balance_label = ttk.Label(details_frame, textvariable=self.admin_balance_var, 
                                 font=('Arial', 12, 'bold'), foreground='red')
        balance_label.grid(row=2, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        
        # Row 4 - Indebtedness button
        indebtedness_button = ttk.Button(details_frame, text="💰 Add Indebtedness", 
                                        command=self.add_indebtedness_for_current_admin)
        indebtedness_button.grid(row=2, column=2, sticky=tk.W, pady=10, padx=(20, 0))
        
        # Payment entry section
        payment_entry_frame = ttk.LabelFrame(self.content_scrollable_frame, text="Record New Payment", padding=15)
        payment_entry_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Payment form
        payment_form_frame = ttk.Frame(payment_entry_frame)
        payment_form_frame.pack(fill=tk.X)
        
        ttk.Label(payment_form_frame, text="Amount (K تومان):", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.payment_amount = ttk.Entry(payment_form_frame, width=20, font=('Arial', 11))
        self.payment_amount.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Label(payment_form_frame, text="Date:", font=('Arial', 11, 'bold')).grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.payment_date = ttk.Entry(payment_form_frame, width=15, font=('Arial', 11))
        self.payment_date.grid(row=0, column=3, sticky=tk.W, pady=5, padx=(10, 0))
        self.payment_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Payment buttons
        payment_buttons_frame = ttk.Frame(payment_entry_frame)
        payment_buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(payment_buttons_frame, text="💾 Record Payment", 
                  command=self.record_payment, style='Accent.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(payment_buttons_frame, text="🗑️ Clear Form", 
                  command=self.clear_payment_form).pack(side=tk.LEFT)
        
        # Invoice history section
        invoice_frame = ttk.LabelFrame(self.content_scrollable_frame, text="📄 Invoice History", padding=15)
        invoice_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Invoice treeview
        invoice_tree_frame = ttk.Frame(invoice_frame)
        invoice_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.invoice_tree = ttk.Treeview(invoice_tree_frame, columns=('Period', 'Amount'), 
                                        show='headings', height=8)
        self.invoice_tree.heading('Period', text='Invoice Period')
        self.invoice_tree.heading('Amount', text='Amount (K تومان)')
        
        self.invoice_tree.column('Period', width=250, anchor='center')
        self.invoice_tree.column('Amount', width=150, anchor='e')
        
        # Invoice treeview scrollbar
        invoice_scrollbar = ttk.Scrollbar(invoice_tree_frame, orient=tk.VERTICAL, 
                                         command=self.invoice_tree.yview)
        self.invoice_tree.configure(yscrollcommand=invoice_scrollbar.set)
        
        self.invoice_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        invoice_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Invoice buttons frame (under the list)
        invoice_buttons_frame = ttk.Frame(invoice_frame)
        invoice_buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.edit_invoice_btn = ttk.Button(invoice_buttons_frame, text="✏️ Edit Selected Invoice", 
                                          command=self.edit_selected_invoice, state='disabled')
        self.edit_invoice_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.delete_invoice_btn = ttk.Button(invoice_buttons_frame, text="🗑️ Delete Selected Invoice", 
                                            command=self.delete_selected_invoice, state='disabled')
        self.delete_invoice_btn.pack(side=tk.RIGHT)
        
        # Payment history section
        payment_frame = ttk.LabelFrame(self.content_scrollable_frame, text="💰 Payment History", padding=15)
        payment_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Payment treeview
        payment_tree_frame = ttk.Frame(payment_frame)
        payment_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.payment_tree = ttk.Treeview(payment_tree_frame, columns=('Date', 'Amount'), 
                                        show='headings', height=8)
        self.payment_tree.heading('Date', text='Date')
        self.payment_tree.heading('Amount', text='Amount (K تومان)')
        
        self.payment_tree.column('Date', width=150, anchor='center')
        self.payment_tree.column('Amount', width=150, anchor='e')
        
        # Payment treeview scrollbar
        payment_scrollbar = ttk.Scrollbar(payment_tree_frame, orient=tk.VERTICAL, 
                                         command=self.payment_tree.yview)
        self.payment_tree.configure(yscrollcommand=payment_scrollbar.set)
        
        self.payment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        payment_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Payment delete button (under the list)
        payment_delete_frame = ttk.Frame(payment_frame)
        payment_delete_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.delete_payment_btn = ttk.Button(payment_delete_frame, text="🗑️ Delete Selected Payment", 
                                            command=self.delete_selected_payment, state='disabled')
        self.delete_payment_btn.pack(side=tk.RIGHT)
        
        # Bind selection events for deletion
        self.payment_tree.bind('<<TreeviewSelect>>', self.on_payment_select)
        self.invoice_tree.bind('<<TreeviewSelect>>', self.on_invoice_select)
        

        
        # Store canvas reference for global mousewheel handler
        self.content_canvas = content_canvas
        
        # Global mousewheel binding - captures events regardless of widget focus
        self.root.bind_all("<MouseWheel>", self._on_mousewheel_global)      # Windows / macOS
        self.root.bind_all("<Button-4>", self._on_mousewheel_global)        # Linux scroll-up
        self.root.bind_all("<Button-5>", self._on_mousewheel_global)        # Linux scroll-down
    
    def manage_indebtedness(self):
        """Add indebtedness as an invoice record"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Indebtedness")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"500x400+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Add Indebtedness", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Admin selection frame
        admin_frame = ttk.LabelFrame(main_frame, text="Select Admin", padding=15)
        admin_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Get all admins
        self.cursor.execute('''
            SELECT name, fa_number, total_earned, total_paid
            FROM admin_accounts
            ORDER BY name
        ''')
        admins = self.cursor.fetchall()
        
        # Admin selection dropdown
        ttk.Label(admin_frame, text="Admin:", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        admin_var = tk.StringVar()
        admin_names = [f"{admin[0]} ({admin[1]})" for admin in admins]
        admin_combo = ttk.Combobox(admin_frame, textvariable=admin_var, values=admin_names, 
                                  state='readonly', font=('Arial', 11))
        admin_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Current balance display
        balance_frame = ttk.Frame(admin_frame)
        balance_frame.pack(fill=tk.X, pady=(15, 0))
        
        current_balance_var = tk.StringVar(value="Select an admin to view current balance")
        ttk.Label(balance_frame, text="Current Balance:", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(balance_frame, textvariable=current_balance_var, font=('Arial', 11)).pack(anchor=tk.W, pady=(5, 0))
        
        # Indebtedness form frame
        form_frame = ttk.LabelFrame(main_frame, text="Indebtedness Details", padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Amount field
        ttk.Label(form_frame, text="Indebtedness Amount (K تومان):", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var, font=('Arial', 11))
        amount_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Notes field
        ttk.Label(form_frame, text="Notes (optional):", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        notes_var = tk.StringVar()
        notes_entry = ttk.Entry(form_frame, textvariable=notes_var, font=('Arial', 11))
        notes_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def update_balance_display(*args):
            """Update balance display when admin is selected"""
            if admin_var.get():
                admin_name = admin_var.get().split(' (')[0]
                for admin in admins:
                    if admin[0] == admin_name:
                        earned, paid = admin[2], admin[3]
                        balance = earned - paid
                        current_balance_var.set(f"Balance: {self.format_amount_for_display(balance)}K تومان")
                        break
        
        def add_indebtedness():
            """Add indebtedness as invoice record"""
            if not admin_var.get():
                messagebox.showwarning("Warning", "Please select an admin")
                return
            
            if not amount_var.get():
                messagebox.showwarning("Warning", "Please enter indebtedness amount")
                return
            
            admin_name = admin_var.get().split(' (')[0]
            amount = self.parse_amount_from_input(amount_var.get())
            notes = notes_var.get()
            
            # Get admin UUID
            self.cursor.execute("SELECT uuid FROM admin_accounts WHERE name = ?", (admin_name,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Admin not found")
                return
            
            admin_uuid = result[0]
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Add indebtedness as invoice record
            self.cursor.execute('''
                INSERT INTO invoice_additions (admin_uuid, amount, addition_date, invoice_period_start, invoice_period_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (admin_uuid, amount, current_date, "Start Up Indebtedness", "Start Up Indebtedness"))
            
            # Update admin total earned
            self.cursor.execute('''
                UPDATE admin_accounts 
                SET total_earned = total_earned + ?
                WHERE uuid = ?
            ''', (amount, admin_uuid))
            
            self.conn.commit()
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            messagebox.showinfo("Success", f"Indebtedness of {self.format_amount_for_display(amount)}K تومان added for {admin_name}")
            dialog.destroy()
        
        # Bind admin selection to update balance
        admin_var.trace('w', update_balance_display)
        
        # Buttons
        ttk.Button(button_frame, text="💾 Add Indebtedness", command=add_indebtedness, 
                  style='Accent.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def add_indebtedness_for_current_admin(self):
        """Add indebtedness for the currently selected admin"""
        # Get current admin name
        admin_name = self.admin_name_var.get()
        if not admin_name:
            messagebox.showwarning("Warning", "No admin selected")
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Indebtedness - {admin_name}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)  # Prevent resizing
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"500x400+{x}+{y}")
        
        # Main frame with proper spacing
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text=f"Add Indebtedness for {admin_name}", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 15))
        
        # Current balance display
        balance_frame = ttk.LabelFrame(main_frame, text="Current Status", padding=15)
        balance_frame.pack(fill=tk.X, pady=(0, 15))
        
        current_balance_var = tk.StringVar(value=self.admin_balance_var.get())
        ttk.Label(balance_frame, text="Current Balance:", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(balance_frame, textvariable=current_balance_var, font=('Arial', 11)).pack(anchor=tk.W, pady=(5, 0))
        
        # Indebtedness form frame
        form_frame = ttk.LabelFrame(main_frame, text="Indebtedness Details", padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Amount field
        ttk.Label(form_frame, text="Indebtedness Amount (K تومان):", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var, font=('Arial', 11))
        amount_entry.pack(fill=tk.X, pady=(5, 10))
        
        # Notes field
        ttk.Label(form_frame, text="Notes (optional):", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        notes_var = tk.StringVar()
        notes_entry = ttk.Entry(form_frame, textvariable=notes_var, font=('Arial', 11))
        notes_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons frame - ensure it's always at the bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        
        def add_indebtedness():
            """Add indebtedness as invoice record"""
            if not amount_var.get():
                messagebox.showwarning("Warning", "Please enter indebtedness amount")
                return
            
            amount = self.parse_amount_from_input(amount_var.get())
            notes = notes_var.get()
            
            # Get admin UUID
            self.cursor.execute("SELECT uuid FROM admin_accounts WHERE name = ?", (admin_name,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Admin not found")
                return
            
            admin_uuid = result[0]
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Add indebtedness as invoice record
            self.cursor.execute('''
                INSERT INTO invoice_additions (admin_uuid, amount, addition_date, invoice_period_start, invoice_period_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (admin_uuid, amount, current_date, "Start Up Indebtedness", "Start Up Indebtedness"))
            
            # Update admin total earned
            self.cursor.execute('''
                UPDATE admin_accounts 
                SET total_earned = total_earned + ?
                WHERE uuid = ?
            ''', (amount, admin_uuid))
            
            self.conn.commit()
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            
            # Refresh admin detail page
            self.cursor.execute("""
                SELECT uuid, name, fa_number, total_earned, total_paid 
                FROM admin_accounts WHERE name = ?
            """, (admin_name,))
            result = self.cursor.fetchone()
            
            if result:
                admin_uuid, name, fa_number, total_earned, total_paid = result
                remainder = total_earned - total_paid
                
                # Update admin detail page
                self.admin_earned_var.set(f"{self.format_amount_for_display(total_earned)}K تومان")
                self.admin_paid_var.set(f"{self.format_amount_for_display(total_paid)}K تومان")
                self.admin_balance_var.set(f"{self.format_amount_for_display(remainder)}K تومان")
                
                # Reload history
                self.load_admin_invoice_history(admin_uuid)
                self.load_admin_payment_history(admin_uuid)
            
            messagebox.showinfo("Success", f"Indebtedness of {self.format_amount_for_display(amount)}K تومان added for {admin_name}")
            dialog.destroy()
        
        # Buttons
        ttk.Button(button_frame, text="💾 Add Indebtedness", command=add_indebtedness, 
                  style='Accent.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def _on_mousewheel_global(self, event):
        """Global mousewheel handler for admin detail page scrolling"""
        if hasattr(self, 'content_canvas'):
            if event.delta:                               # Windows / macOS
                step = -1 if event.delta > 0 else 1       # one unit per tick
                self.content_canvas.yview_scroll(step, "units")
            else:                                         # X11 (Linux) – wheel mapped to buttons
                if event.num == 4:                        # scroll up
                    self.content_canvas.yview_scroll(-1, "units")
                elif event.num == 5:                      # scroll down
                    self.content_canvas.yview_scroll(1, "units")
    
    def show_admin_list_page(self):
        """Show the admin list page"""
        self.admin_detail_page.pack_forget()
        self.admin_list_page.pack(fill=tk.BOTH, expand=True)
        self.load_admin_accounts()
    
    def show_admin_detail_page(self):
        """Show the admin detail page"""
        self.admin_list_page.pack_forget()
        self.admin_detail_page.pack(fill=tk.BOTH, expand=True)
    

    
    def filter_admins(self, *args):
        """Filter admin list based on search term"""
        if not hasattr(self, 'admin_tree'):
            return
        search_term = self.search_var.get().lower()
        
        # Don't filter if it's the placeholder text
        if search_term == "type admin name or fa number...":
            self.load_admin_accounts()
            return
        
        # Clear current display
        for item in self.admin_tree.get_children():
            self.admin_tree.delete(item)
        
        # Get all admin accounts (only active ones)
        self.cursor.execute('''
            SELECT name, fa_number, total_earned, total_paid
            FROM admin_accounts
            WHERE status = 'active' OR status IS NULL
            ORDER BY name
        ''')
        
        # Configure alternating row colors for filtered results
        self.admin_tree.tag_configure('even_row', background='#f8f9fa', foreground='#2c3e50')
        self.admin_tree.tag_configure('odd_row', background='#ffffff', foreground='#2c3e50')
        
        filtered_count = 0
        for row in self.cursor.fetchall():
            name, fa_number, earned, paid = row
            earned = earned or 0
            paid = paid or 0
            balance = earned - paid
            
            # Filter by search term
            if search_term in name.lower() or search_term in fa_number.lower():
                # Apply alternating row colors
                tag = 'even_row' if filtered_count % 2 == 0 else 'odd_row'
                
                self.admin_tree.insert('', 'end', values=(
                    name, 
                    fa_number, 
                    self.format_amount_for_display(earned),
                    self.format_amount_for_display(paid),
                    self.format_amount_for_display(balance)
                ), tags=(tag,))
                filtered_count += 1
    
    def clear_search(self):
        """Clear search and show all admins"""
        self.search_var.set("")
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, "Type admin name or FA number...")
        self.search_entry.config(foreground='gray')
        self.load_admin_accounts()
    
    def on_search_focus_in(self, event):
        """Handle search entry focus in"""
        if self.search_entry.get() == "Type admin name or FA number...":
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(foreground='black')
    
    def on_search_focus_out(self, event):
        """Handle search entry focus out"""
        if not self.search_entry.get():
            self.search_entry.insert(0, "Type admin name or FA number...")
            self.search_entry.config(foreground='gray')
    
    def open_admin_detail_page(self, event):
        """Open admin detail page when admin is clicked"""
        selection = self.admin_tree.selection()
        if selection:
            item = self.admin_tree.item(selection[0])
            admin_name = item['values'][0]
            
            # Get admin details
            self.cursor.execute("""
                SELECT uuid, name, fa_number, total_earned, total_paid 
                FROM admin_accounts WHERE name = ?
            """, (admin_name,))
            result = self.cursor.fetchone()
            
            if result:
                admin_uuid, name, fa_number, total_earned, total_paid = result
                remainder = total_earned - total_paid
                
                # Update admin detail page
                self.selected_admin_title.config(text=f"Admin: {name}")
                self.admin_name_var.set(name)
                self.admin_fa_var.set(fa_number)
                self.admin_earned_var.set(f"{self.format_amount_for_display(total_earned)}K تومان")
                self.admin_paid_var.set(f"{self.format_amount_for_display(total_paid)}K تومان")
                self.admin_balance_var.set(f"{self.format_amount_for_display(remainder)}K تومان")
                
                # Load history
                self.load_admin_invoice_history(admin_uuid)
                self.load_admin_payment_history(admin_uuid)
                
                # Reset selection states
                self.delete_payment_btn.config(state='disabled')
                self.delete_invoice_btn.config(state='disabled')
                
                # Show detail page
                self.show_admin_detail_page()
    

    

    
    def refresh_admin_names(self):
        """Refresh admin names from backup files"""
        try:
            self.update_admin_names_from_backups()
            self.load_admin_accounts()
            messagebox.showinfo("Success", "Admin names updated from backup files!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update admin names: {str(e)}")
    
    def create_invoices_tab(self):
        """Create invoices tab for managing and generating invoices"""
        invoices_frame = ttk.Frame(self.notebook)
        self.notebook.add(invoices_frame, text="Invoices")
        
        # Title
        title_label = ttk.Label(invoices_frame, text="Invoice Management", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Controls frame
        controls_frame = ttk.Frame(invoices_frame)
        controls_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Generate invoices button
        self.generate_btn = ttk.Button(controls_frame, text="Generate New Invoices", 
                                      command=self.generate_invoices)
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        
        # Date range frame
        date_frame = ttk.LabelFrame(controls_frame, text="Invoice Period", padding=5)
        date_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(date_frame, text="From:").pack(side=tk.LEFT)
        self.start_date = ttk.Entry(date_frame, width=12)
        self.start_date.pack(side=tk.LEFT, padx=5)
        self.start_date.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        
        ttk.Label(date_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        self.end_date = ttk.Entry(date_frame, width=12)
        self.end_date.pack(side=tk.LEFT, padx=5)
        self.end_date.insert(0, (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
        
        # Add invoice amounts button
        self.add_invoice_amounts_btn = ttk.Button(controls_frame, text="Add Invoice Amounts to Accounts", 
                                                 command=self.add_invoice_amounts_to_accounts)
        self.add_invoice_amounts_btn.pack(side=tk.LEFT, padx=5)
    

    
    def start_download(self):
        """Start backup download in a separate thread"""
        self.download_btn.config(state='disabled')
        self.download_status.config(text="Downloading...")
        self.progress_var.set(0)
        
        # Start download in separate thread
        thread = threading.Thread(target=self.download_backups)
        thread.daemon = True
        thread.start()
    
    def download_backups(self):
        """Download all backup files"""
        try:
            # Create downloads directory
            if not os.path.exists('downloads'):
                os.makedirs('downloads')
            
            # Download each backup
            for i, (name, url) in enumerate(config.URLS.items(), 1):
                self.root.after(0, lambda i=i: self.progress_var.set(i))
                self.root.after(0, lambda name=name: self.download_status.config(text=f"Downloading {name}..."))
                
                # Import and use the download function
                from file_management import download_backup
                download_backup(url, i)
            
            # Update status
            self.root.after(0, lambda: self.download_status.config(text="Updating UUIDs..."))
            
            # Update UUIDs from downloaded backups
            self.update_uuids_from_backups()
            
            # Update status
            self.root.after(0, lambda: self.download_status.config(text="Download completed!"))
            self.root.after(0, lambda: self.download_btn.config(state='normal'))
            self.root.after(0, self.load_backup_files)
            
            # Update database in main thread
            self.root.after(0, self.update_backup_database)
            
            # Refresh admin accounts in database in main thread
            def refresh_admin_data():
                new_admins, removed_admins = self.sync_admin_accounts_with_config()
                self.load_admin_accounts()
                self.load_dashboard_data()
                
                if new_admins > 0 and removed_admins > 0:
                    messagebox.showinfo("Success", 
                        f"Download completed!\n"
                        f"✅ {new_admins} new admin(s) added\n"
                        f"❌ {removed_admins} admin(s) removed/marked inactive")
                elif new_admins > 0:
                    messagebox.showinfo("Success", f"Download completed!\n{new_admins} new admin(s) have been added to the database.")
                elif removed_admins > 0:
                    messagebox.showinfo("Success", f"Download completed!\n{removed_admins} admin(s) removed/marked inactive")
            
            self.root.after(0, refresh_admin_data)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}"))
            self.root.after(0, lambda: self.download_status.config(text="Download failed"))
            self.root.after(0, lambda: self.download_btn.config(state='normal'))
    
    def load_backup_files(self):
        """Load and display backup files"""
        # Clear existing items
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)
        
        downloads_folder = "downloads"
        if not os.path.exists(downloads_folder):
            return
        
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                try:
                    # Get file stats
                    stat = os.stat(file_path)
                    size = f"{stat.st_size / 1024:.1f} KB"
                    date = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    
                    # Extract panel number
                    panel_num = filename.replace('backup', '').replace('.json', '')
                    panel_name = config.PANELS.get(int(panel_num), f"Panel {panel_num}")
                    
                    self.backup_tree.insert('', 'end', values=(panel_name, filename, size, date, 'Ready'))
                except Exception as e:
                    self.backup_tree.insert('', 'end', values=(filename, '', '', '', f'Error: {str(e)}'))
    
    def update_backup_database(self):
        """Update backup database with new files"""
        downloads_folder = "downloads"
        if not os.path.exists(downloads_folder):
            return
        
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.json'):
                file_path = os.path.join(downloads_folder, filename)
                panel_num = int(filename.replace('backup', '').replace('.json', ''))
                
                # Calculate file hash
                import hashlib
                with open(file_path, 'rb') as f:
                    data_hash = hashlib.md5(f.read()).hexdigest()
                
                # Check if already exists
                self.cursor.execute("SELECT id FROM backup_data WHERE panel_number = ? AND data_hash = ?", 
                                  (panel_num, data_hash))
                if not self.cursor.fetchone():
                    self.cursor.execute('''
                        INSERT INTO backup_data (panel_number, backup_date, data_hash, file_path)
                        VALUES (?, ?, ?, ?)
                    ''', (panel_num, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_hash, file_path))
        
        self.conn.commit()
    
    def update_uuids_from_backups(self):
        """Update UUIDs from downloaded backup files"""
        try:
            # Import config to get current TELEGRAM_ACCOUNTS
            import config
            
            # Directory containing backup JSON files
            BACKUP_FOLDER = "downloads"
            CONFIG_FILE_PATH = 'config.py'
            CONFIG_BACKUP_PATH = 'config_backup.py'
            
            # Step 1: Create a backup of the original config.py
            if not os.path.exists(CONFIG_BACKUP_PATH):
                import shutil
                shutil.copy(CONFIG_FILE_PATH, CONFIG_BACKUP_PATH)
                print(f"Backup created: {CONFIG_BACKUP_PATH}")
            
            # Step 2: Collect all uuids from backup JSON files
            uuids_from_json = set()
            admin_data = []
            
            for filename in os.listdir(BACKUP_FOLDER):
                if filename.startswith("backup") and filename.endswith(".json"):
                    # Extract the index from the filename (e.g., backup1.json -> 1)
                    file_index = filename.replace("backup", "").replace(".json", "")
                    fa_number = f"fa{file_index}"
                    
                    file_path = os.path.join(BACKUP_FOLDER, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        admins = data.get("admin_users", [])
                        admin_data.extend([(admin, fa_number) for admin in admins])
                        for admin in admins:
                            uuids_from_json.add(admin["uuid"])
            
            # Step 3: Filter TELEGRAM_ACCOUNTS to retain only uuids present in the JSON files
            filtered_accounts = {
                key: value for key, value in config.TELEGRAM_ACCOUNTS.items() if key in uuids_from_json
            }
            
            # Step 4: Identify and add new uuids with conditions
            new_admins_added = 0
            for admin, fa_number in admin_data:
                uuid = admin["uuid"]
                name = admin["name"]
                comment = admin["comment"]
                
                # Check conditions and if the uuid is not in filtered_accounts
                if uuid not in filtered_accounts and name != "Owner" and comment != "-":
                    # Add the new entry to filtered_accounts with the specified format
                    # Use 1400 as default price for new admins (same as original update_uuid.py)
                    filtered_accounts[uuid] = [3, fa_number, 1400]
                    new_admins_added += 1
            
            # Step 5: Format the dictionary to maintain inline style
            formatted_accounts = "{\n" + ",\n".join(
                f'    "{key}": {value}' for key, value in filtered_accounts.items()
            ) + "\n}"
            
            # Step 6: Update the TELEGRAM_ACCOUNTS in the config.py file
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                config_data = f.read()
            
            # Use regex to locate and replace the TELEGRAM_ACCOUNTS assignment
            import re
            pattern = re.compile(r"TELEGRAM_ACCOUNTS\s*=\s*{.*?}", re.DOTALL)
            replacement = f"TELEGRAM_ACCOUNTS = {formatted_accounts}"
            
            if pattern.search(config_data):
                updated_config_data = pattern.sub(replacement, config_data)
            else:
                raise ValueError("TELEGRAM_ACCOUNTS definition not found in config.py")
            
            # Write the updated data back to the config.py file
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                f.write(updated_config_data)
            
            print(f"TELEGRAM_ACCOUNTS has been updated in config.py. {new_admins_added} new admins added.")
            
            # Reload config module to get updated TELEGRAM_ACCOUNTS
            import importlib
            importlib.reload(config)
            
            return new_admins_added
            
        except Exception as e:
            print(f"Error updating UUIDs: {str(e)}")
            raise e
    

    

    
    def load_dashboard_data(self):
        """Load dashboard statistics"""
        # Get total admins
        self.cursor.execute("SELECT COUNT(*) FROM admin_accounts WHERE status = 'active'")
        total_admins = self.cursor.fetchone()[0]
        self.total_admins_var.set(str(total_admins))
        
        # Get total earned
        self.cursor.execute("SELECT SUM(total_earned) FROM admin_accounts")
        total_earned = self.cursor.fetchone()[0] or 0
        self.total_earned_var.set(f"{total_earned:,.0f} تومان")
        
        # Get total paid
        self.cursor.execute("SELECT SUM(total_paid) FROM admin_accounts")
        total_paid = self.cursor.fetchone()[0] or 0
        self.total_paid_var.set(f"{total_paid:,.0f} تومان")
        
        # Calculate balance
        balance = total_earned - total_paid
        self.total_balance_var.set(f"{balance:,.0f} تومان")
        
        # Get last backup date
        self.cursor.execute("SELECT MAX(backup_date) FROM backup_data")
        last_backup = self.cursor.fetchone()[0]
        self.last_backup_var.set(last_backup or "Never")
        
        # Load recent activity
        self.load_recent_activity()
    
    def load_recent_activity(self):
        """Load recent activity in dashboard"""
        # Clear existing items
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)
        
        # Get recent payments
        self.cursor.execute('''
            SELECT p.payment_date, a.name, 'Payment', p.amount
            FROM payments p
            JOIN admin_accounts a ON p.admin_uuid = a.uuid
            ORDER BY p.payment_date DESC
            LIMIT 20
        ''')
        
        for row in self.cursor.fetchall():
            self.activity_tree.insert('', 'end', values=row)
    
    def load_admin_accounts(self):
        """Load admin accounts in accounting tab"""
        # Clear existing items
        for item in self.admin_tree.get_children():
            self.admin_tree.delete(item)
        
        # Get admin accounts (only active ones)
        self.cursor.execute('''
            SELECT name, fa_number, total_earned, total_paid
            FROM admin_accounts
            WHERE status = 'active' OR status IS NULL
            ORDER BY name
        ''')
        
        # Configure alternating row colors
        self.admin_tree.tag_configure('even_row', background='#f8f9fa', foreground='#2c3e50')
        self.admin_tree.tag_configure('odd_row', background='#ffffff', foreground='#2c3e50')
        
        for i, row in enumerate(self.cursor.fetchall()):
            name, fa_number, earned, paid = row
            earned = earned or 0
            paid = paid or 0
            balance = earned - paid
            
            # Apply alternating row colors
            tag = 'even_row' if i % 2 == 0 else 'odd_row'
            
            self.admin_tree.insert('', 'end', values=(
                name, 
                fa_number, 
                self.format_amount_for_display(earned),
                self.format_amount_for_display(paid),
                self.format_amount_for_display(balance)
            ), tags=(tag,))
    

    
    def record_payment(self):
        """Record a payment for selected admin"""
        # Get admin name from the detail page
        admin_name = self.admin_name_var.get()
        if not admin_name:
            messagebox.showwarning("Warning", "No admin selected")
            return
        
        # Get admin UUID
        self.cursor.execute("SELECT uuid FROM admin_accounts WHERE name = ?", (admin_name,))
        result = self.cursor.fetchone()
        if not result:
            messagebox.showerror("Error", "Admin not found")
            return
        
        admin_uuid = result[0]
        
        # Get payment details
        try:
            amount = self.parse_amount_from_input(self.payment_amount.get())
        except:
            messagebox.showerror("Error", "Invalid amount")
            return
        
        payment_date = self.payment_date.get()
        if not payment_date:
            messagebox.showerror("Error", "Please enter payment date")
            return
        
        # Record payment
        self.cursor.execute('''
            INSERT INTO payments (admin_uuid, amount, payment_date, payment_method, reference, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_uuid, amount, payment_date, '', '', ''))
        
        # Update admin account
        self.cursor.execute('''
            UPDATE admin_accounts 
            SET total_paid = total_paid + ?, last_payment_date = ?
            WHERE uuid = ?
        ''', (amount, payment_date, admin_uuid))
        
        self.conn.commit()
        
        # Refresh displays
        self.load_admin_accounts()
        self.load_dashboard_data()
        self.clear_payment_form()
        
        messagebox.showinfo("Success", f"Payment of {self.format_amount_for_display(amount)}K تومان recorded for {admin_name}")
        
        # Refresh admin detail page
        self.cursor.execute("SELECT total_earned, total_paid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
        result = self.cursor.fetchone()
        if result:
            total_earned, total_paid = result
            remainder = total_earned - total_paid
            self.admin_earned_var.set(f"{self.format_amount_for_display(total_earned)}K تومان")
            self.admin_paid_var.set(f"{self.format_amount_for_display(total_paid)}K تومان")
            self.admin_balance_var.set(f"{self.format_amount_for_display(remainder)}K تومان")
            self.load_admin_payment_history(admin_uuid)
            # Reset payment and invoice selection
            self.delete_payment_btn.config(state='disabled')
            self.delete_invoice_btn.config(state='disabled')
    
    def clear_payment_form(self):
        """Clear payment form"""
        self.payment_amount.delete(0, tk.END)
        self.payment_date.delete(0, tk.END)
        self.payment_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
    
    def load_admin_invoice_history(self, admin_uuid):
        """Load invoice history for selected admin"""
        # Clear existing items
        for item in self.invoice_tree.get_children():
            self.invoice_tree.delete(item)
        
        # Get invoice additions for this admin (ordered by date ascending for payment calculation)
        self.cursor.execute("""
            SELECT id, addition_date, amount, invoice_period_start, invoice_period_end
            FROM invoice_additions 
            WHERE admin_uuid = ?
            ORDER BY addition_date ASC
        """, (admin_uuid,))
        
        invoice_results = self.cursor.fetchall()
        
        # Get total payments for this admin
        self.cursor.execute("""
            SELECT SUM(amount) FROM payments WHERE admin_uuid = ?
        """, (admin_uuid,))
        
        total_payments_result = self.cursor.fetchone()
        total_payments = total_payments_result[0] if total_payments_result[0] else 0
        
        # Calculate which invoices are paid
        cumulative_invoice_amount = 0
        paid_invoice_ids = []
        
        for invoice_id, addition_date, amount, start_date, end_date in invoice_results:
            cumulative_invoice_amount += amount
            if cumulative_invoice_amount <= total_payments:
                paid_invoice_ids.append(invoice_id)
        
        # Now display invoices in reverse order (newest first) with color coding
        self.cursor.execute("""
            SELECT id, addition_date, amount, invoice_period_start, invoice_period_end
            FROM invoice_additions 
            WHERE admin_uuid = ?
            ORDER BY addition_date DESC
        """, (admin_uuid,))
        
        results = self.cursor.fetchall()
        total_invoiced = 0
        
        for invoice_id, addition_date, amount, start_date, end_date in results:
            # Format the invoice period (from-to dates)
            if start_date and end_date:
                # Extract just the date part from start and end dates
                start_part = start_date.split()[0] if ' ' in start_date else start_date
                end_part = end_date.split()[0] if ' ' in end_date else end_date
                period_text = f"{start_part} to {end_part}"
            else:
                # Fallback to addition date if period dates are not available
                date_part = addition_date.split()[0] if ' ' in addition_date else addition_date
                period_text = date_part
            
            # Format amount with simplified display
            formatted_amount = self.format_amount_for_display(amount)
            
            # Insert into treeview with appropriate tag
            item = self.invoice_tree.insert('', 'end', values=(period_text, formatted_amount))
            
            # Color code based on payment status
            if invoice_id in paid_invoice_ids:
                self.invoice_tree.item(item, tags=('paid',))
            else:
                self.invoice_tree.item(item, tags=('unpaid',))
            
            total_invoiced += amount
        
        # Add total row if there are invoices
        if results:
            self.invoice_tree.insert('', 'end', values=('TOTAL', self.format_amount_for_display(total_invoiced)), tags=('total',))
            
            # Configure tags for styling
            self.invoice_tree.tag_configure('paid', background='#d4edda', foreground='#155724')  # Green for paid
            self.invoice_tree.tag_configure('unpaid', background='#f8f9fa', foreground='#2c3e50')  # Default for unpaid
            self.invoice_tree.tag_configure('total', background='#e8f5e8', font=('Arial', 10, 'bold'))
        
        # Store invoice IDs for deletion (in reverse order to match display)
        self.invoice_ids = [row[0] for row in results]
    
    def load_admin_payment_history(self, admin_uuid):
        """Load payment history for selected admin"""
        # Clear existing items
        for item in self.payment_tree.get_children():
            self.payment_tree.delete(item)
        
        # Get payments for this admin
        self.cursor.execute("""
            SELECT id, payment_date, amount
            FROM payments 
            WHERE admin_uuid = ?
            ORDER BY payment_date DESC
        """, (admin_uuid,))
        
        results = self.cursor.fetchall()
        total_paid = 0
        
        # Store payment IDs for deletion
        self.payment_ids = []
        
        for payment_id, payment_date, amount in results:
            # Extract just the date part from payment_date
            date_part = payment_date.split()[0] if ' ' in payment_date else payment_date
            
            # Format amount with simplified display
            formatted_amount = self.format_amount_for_display(amount)
            
            # Insert into treeview
            self.payment_tree.insert('', 'end', values=(date_part, formatted_amount))
            total_paid += amount
            self.payment_ids.append(payment_id)
        
        # Add total row if there are payments
        if results:
            self.payment_tree.insert('', 'end', values=('TOTAL', self.format_amount_for_display(total_paid)), tags=('total',))
            self.payment_tree.tag_configure('total', background='#e8f5e8', font=('Arial', 10, 'bold'))
    
    def on_payment_select(self, event):
        """Handle payment selection in treeview"""
        selection = self.payment_tree.selection()
        if selection:
            # Get the selected item
            selected_item = selection[0]
            item_values = self.payment_tree.item(selected_item, 'values')
            
            # Don't enable delete for TOTAL row
            if item_values[0] != 'TOTAL':
                self.delete_payment_btn.config(state='normal')
            else:
                self.delete_payment_btn.config(state='disabled')
        else:
            self.delete_payment_btn.config(state='disabled')
    
    def on_invoice_select(self, event):
        """Handle invoice selection in treeview"""
        selection = self.invoice_tree.selection()
        if selection:
            # Get the selected item
            selected_item = selection[0]
            item_values = self.invoice_tree.item(selected_item, 'values')
            
            # Don't enable buttons for TOTAL row
            if item_values[0] != 'TOTAL':
                self.edit_invoice_btn.config(state='normal')
                self.delete_invoice_btn.config(state='normal')
            else:
                self.edit_invoice_btn.config(state='disabled')
                self.delete_invoice_btn.config(state='disabled')
        else:
            self.edit_invoice_btn.config(state='disabled')
            self.delete_invoice_btn.config(state='disabled')
    
    def delete_selected_payment(self):
        """Delete the selected payment record"""
        selection = self.payment_tree.selection()
        if not selection:
            return
        
        selected_item = selection[0]
        item_values = self.payment_tree.item(selected_item, 'values')
        
        # Don't allow deletion of TOTAL row
        if item_values[0] == 'TOTAL':
            return
        
        # Find the index of the selected item (excluding TOTAL row)
        children = self.payment_tree.get_children()
        selected_index = children.index(selected_item)
        
        if selected_index >= len(self.payment_ids):
            return
        
        payment_id = self.payment_ids[selected_index]
        
        # Get payment details for confirmation
        self.cursor.execute("""
            SELECT p.amount, p.payment_date, a.name 
            FROM payments p 
            JOIN admin_accounts a ON p.admin_uuid = a.uuid 
            WHERE p.id = ?
        """, (payment_id,))
        
        result = self.cursor.fetchone()
        if not result:
            return
        
        amount, payment_date, admin_name = result
        date_part = payment_date.split()[0] if ' ' in payment_date else payment_date
        
        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete this payment?\n\n"
            f"Admin: {admin_name}\n"
            f"Date: {date_part}\n"
            f"Amount: {self.format_amount_for_display(amount)}K تومان"
        )
        
        if confirm:
            # Get admin UUID for updating total_paid
            self.cursor.execute("SELECT admin_uuid FROM payments WHERE id = ?", (payment_id,))
            admin_uuid = self.cursor.fetchone()[0]
            
            # Delete the payment
            self.cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            
            # Update admin's total_paid
            self.cursor.execute("""
                UPDATE admin_accounts 
                SET total_paid = total_paid - ? 
                WHERE uuid = ?
            """, (amount, admin_uuid))
            
            self.conn.commit()
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            
            # Refresh admin detail page
            self.cursor.execute("SELECT total_earned, total_paid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
            result = self.cursor.fetchone()
            if result:
                total_earned, total_paid = result
                remainder = total_earned - total_paid
                self.admin_earned_var.set(f"{self.format_amount_for_display(total_earned)}K تومان")
                self.admin_paid_var.set(f"{self.format_amount_for_display(total_paid)}K تومان")
                self.admin_balance_var.set(f"{self.format_amount_for_display(remainder)}K تومان")
                self.load_admin_payment_history(admin_uuid)
            
            messagebox.showinfo("Success", f"Payment of {self.format_amount_for_display(amount)}K تومان deleted successfully!")
    
    def delete_selected_invoice(self):
        """Delete the selected invoice record"""
        selection = self.invoice_tree.selection()
        if not selection:
            return
        
        selected_item = selection[0]
        item_values = self.invoice_tree.item(selected_item, 'values')
        
        # Don't allow deletion of TOTAL row
        if item_values[0] == 'TOTAL':
            return
        
        # Find the index of the selected item (excluding TOTAL row)
        children = self.invoice_tree.get_children()
        selected_index = children.index(selected_item)
        
        if selected_index >= len(self.invoice_ids):
            return
        
        invoice_id = self.invoice_ids[selected_index]
        
        # Get invoice details for confirmation
        self.cursor.execute("""
            SELECT ia.amount, ia.addition_date, ia.invoice_period_start, ia.invoice_period_end, a.name, ia.admin_uuid
            FROM invoice_additions ia
            JOIN admin_accounts a ON ia.admin_uuid = a.uuid 
            WHERE ia.id = ?
        """, (invoice_id,))
        
        result = self.cursor.fetchone()
        if not result:
            return
        
        amount, addition_date, start_date, end_date, admin_name, admin_uuid = result
        
        # Format period for display
        if start_date and end_date:
            start_part = start_date.split()[0] if ' ' in start_date else start_date
            end_part = end_date.split()[0] if ' ' in end_date else end_date
            period_text = f"{start_part} to {end_part}"
        else:
            date_part = addition_date.split()[0] if ' ' in addition_date else addition_date
            period_text = date_part
        
        # Check if this invoice is paid (green)
        is_paid = self.is_invoice_paid(invoice_id, admin_uuid)
        
        if is_paid:
            # Calculate which payments need to be reduced
            payment_reductions = self.calculate_payment_reductions_for_invoice(invoice_id, admin_uuid, amount)
            
            if payment_reductions:
                # Show detailed confirmation for paid invoice deletion
                reduction_text = "\n".join([f"• Payment {p['date']}: -{self.format_amount_for_display(p['amount'])}K تومان" for p in payment_reductions])
                
                confirm = messagebox.askyesno(
                    "Confirm Paid Invoice Deletion", 
                    f"⚠️ WARNING: This invoice is PAID and will affect payment history!\n\n"
                    f"Admin: {admin_name}\n"
                    f"Period: {period_text}\n"
                    f"Amount: {self.format_amount_for_display(amount)}K تومان\n\n"
                    f"The following payment amounts will be reduced:\n{reduction_text}\n\n"
                    f"Are you sure you want to proceed?"
                )
            else:
                confirm = messagebox.askyesno(
                    "Confirm Invoice Deletion", 
                    f"Are you sure you want to delete this invoice?\n\n"
                    f"Admin: {admin_name}\n"
                    f"Period: {period_text}\n"
                    f"Amount: {self.format_amount_for_display(amount)}K تومان\n\n"
                    f"⚠️ Warning: This will reduce the admin's total_earned amount!"
                )
        else:
            # Regular confirmation for unpaid invoice
            confirm = messagebox.askyesno(
                "Confirm Invoice Deletion", 
                f"Are you sure you want to delete this invoice?\n\n"
                f"Admin: {admin_name}\n"
                f"Period: {period_text}\n"
                f"Amount: {self.format_amount_for_display(amount)}K تومان\n\n"
                f"⚠️ Warning: This will reduce the admin's total_earned amount!"
            )
        
        if confirm:
            # Delete the invoice
            self.cursor.execute("DELETE FROM invoice_additions WHERE id = ?", (invoice_id,))
            
            # Update admin's total_earned
            self.cursor.execute("""
                UPDATE admin_accounts 
                SET total_earned = total_earned - ? 
                WHERE uuid = ?
            """, (amount, admin_uuid))
            
            # If invoice was paid, reduce corresponding payment amounts
            if is_paid and payment_reductions:
                self.reduce_payment_amounts(payment_reductions, admin_uuid)
            
            self.conn.commit()
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            
            # Refresh admin detail page
            self.cursor.execute("SELECT total_earned, total_paid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
            result = self.cursor.fetchone()
            if result:
                total_earned, total_paid = result
                remainder = total_earned - total_paid
                self.admin_earned_var.set(f"{total_earned:,.0f} تومان")
                self.admin_paid_var.set(f"{total_paid:,.0f} تومان")
                self.admin_balance_var.set(f"{remainder:,.0f} تومان")
                self.load_admin_invoice_history(admin_uuid)
                self.load_admin_payment_history(admin_uuid)
            
            # Reset invoice selection
            self.delete_invoice_btn.config(state='disabled')
            self.edit_invoice_btn.config(state='disabled')
            
            if is_paid:
                messagebox.showinfo("Success", 
                                  f"Paid invoice of {amount:,.0f} تومان deleted successfully!\n"
                                  f"Payment amounts have been adjusted accordingly.")
            else:
                messagebox.showinfo("Success", f"Invoice of {amount:,.0f} تومان deleted successfully!")
    
    def edit_selected_invoice(self):
        """Edit the selected invoice amount"""
        selection = self.invoice_tree.selection()
        if not selection:
            return
        
        selected_item = selection[0]
        item_values = self.invoice_tree.item(selected_item, 'values')
        
        # Don't allow editing of TOTAL row
        if item_values[0] == 'TOTAL':
            return
        
        # Find the index of the selected item (excluding TOTAL row)
        children = self.invoice_tree.get_children()
        selected_index = children.index(selected_item)
        
        if selected_index >= len(self.invoice_ids):
            return
        
        invoice_id = self.invoice_ids[selected_index]
        
        # Get invoice details
        self.cursor.execute("""
            SELECT ia.amount, ia.addition_date, ia.invoice_period_start, ia.invoice_period_end, a.name, ia.admin_uuid
            FROM invoice_additions ia
            JOIN admin_accounts a ON ia.admin_uuid = a.uuid 
            WHERE ia.id = ?
        """, (invoice_id,))
        
        result = self.cursor.fetchone()
        if not result:
            return
        
        old_amount, addition_date, start_date, end_date, admin_name, admin_uuid = result
        
        # Format period for display
        if start_date and end_date:
            start_part = start_date.split()[0] if ' ' in start_date else start_date
            end_part = end_date.split()[0] if ' ' in end_date else end_date
            period_text = f"{start_part} to {end_part}"
        else:
            date_part = addition_date.split()[0] if ' ' in addition_date else addition_date
            period_text = date_part
        
        # Create edit dialog
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title("Edit Invoice Amount")
        edit_dialog.geometry("400x200")
        edit_dialog.transient(self.root)
        edit_dialog.grab_set()
        
        # Center the dialog
        edit_dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Dialog content
        ttk.Label(edit_dialog, text=f"Edit Invoice for {admin_name}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(edit_dialog, text=f"Period: {period_text}", font=('Arial', 10)).pack()
        
        # Amount entry
        amount_frame = ttk.Frame(edit_dialog)
        amount_frame.pack(pady=20)
        
        ttk.Label(amount_frame, text="New Amount (K تومان):", font=('Arial', 11, 'bold')).pack()
        new_amount_var = tk.StringVar(value=self.format_amount_for_display(old_amount))
        amount_entry = ttk.Entry(amount_frame, textvariable=new_amount_var, width=20, font=('Arial', 11))
        amount_entry.pack(pady=5)
        amount_entry.focus()
        
        # Buttons
        button_frame = ttk.Frame(edit_dialog)
        button_frame.pack(pady=20)
        
        def save_changes():
            try:
                new_amount = self.parse_amount_from_input(new_amount_var.get())
                if new_amount < 0:
                    messagebox.showerror("Error", "Amount cannot be negative")
                    return
                
                # Calculate the difference
                amount_difference = new_amount - old_amount
                
                # Update the invoice amount
                self.cursor.execute("UPDATE invoice_additions SET amount = ? WHERE id = ?", (new_amount, invoice_id))
                
                # Update admin's total_earned
                self.cursor.execute("""
                    UPDATE admin_accounts 
                    SET total_earned = total_earned + ? 
                    WHERE uuid = ?
                """, (amount_difference, admin_uuid))
                
                self.conn.commit()
                
                # Refresh displays
                self.load_admin_accounts()
                self.load_dashboard_data()
                
                # Refresh admin detail page
                self.cursor.execute("SELECT total_earned, total_paid FROM admin_accounts WHERE uuid = ?", (admin_uuid,))
                result = self.cursor.fetchone()
                if result:
                    total_earned, total_paid = result
                    remainder = total_earned - total_paid
                    self.admin_earned_var.set(f"{self.format_amount_for_display(total_earned)}K تومان")
                    self.admin_paid_var.set(f"{self.format_amount_for_display(total_paid)}K تومان")
                    self.admin_balance_var.set(f"{self.format_amount_for_display(remainder)}K تومان")
                    self.load_admin_invoice_history(admin_uuid)
                
                edit_dialog.destroy()
                # Reset button states
                self.edit_invoice_btn.config(state='disabled')
                self.delete_invoice_btn.config(state='disabled')
                messagebox.showinfo("Success", f"Invoice amount updated from {self.format_amount_for_display(old_amount)}K to {self.format_amount_for_display(new_amount)}K تومان")
                
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number")
        
        def cancel_edit():
            edit_dialog.destroy()
        
        ttk.Button(button_frame, text="💾 Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Cancel", command=cancel_edit).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to save
        amount_entry.bind('<Return>', lambda e: save_changes())
        amount_entry.bind('<Escape>', lambda e: cancel_edit())
    
    def is_invoice_paid(self, invoice_id, admin_uuid):
        """Check if an invoice is paid (green) based on payment history"""
        # Get all invoices for this admin (ordered by date ascending)
        self.cursor.execute("""
            SELECT id, amount FROM invoice_additions 
            WHERE admin_uuid = ? 
            ORDER BY addition_date ASC
        """, (admin_uuid,))
        
        invoices = self.cursor.fetchall()
        
        # Get total payments for this admin
        self.cursor.execute("""
            SELECT SUM(amount) FROM payments WHERE admin_uuid = ?
        """, (admin_uuid,))
        
        total_payments_result = self.cursor.fetchone()
        total_payments = total_payments_result[0] if total_payments_result[0] else 0
        
        # Calculate which invoices are paid
        cumulative_invoice_amount = 0
        paid_invoice_ids = []
        
        for inv_id, inv_amount in invoices:
            cumulative_invoice_amount += inv_amount
            if cumulative_invoice_amount <= total_payments:
                paid_invoice_ids.append(inv_id)
        
        return invoice_id in paid_invoice_ids
    
    def calculate_payment_reductions_for_invoice(self, invoice_id, admin_uuid, invoice_amount):
        """Calculate which payment amounts should be reduced when deleting a paid invoice"""
        # Get all invoices for this admin (ordered by date ascending)
        self.cursor.execute("""
            SELECT id, amount FROM invoice_additions 
            WHERE admin_uuid = ? 
            ORDER BY addition_date ASC
        """, (admin_uuid,))
        
        invoices = self.cursor.fetchall()
        
        # Get all payments for this admin (ordered by date ascending)
        self.cursor.execute("""
            SELECT id, amount, payment_date FROM payments 
            WHERE admin_uuid = ? 
            ORDER BY payment_date ASC
        """, (admin_uuid,))
        
        payments = self.cursor.fetchall()
        
        # Find the position of the invoice to be deleted
        invoice_position = None
        cumulative_invoice_amount = 0
        for i, (inv_id, inv_amount) in enumerate(invoices):
            if inv_id == invoice_id:
                invoice_position = i
                break
            cumulative_invoice_amount += inv_amount
        
        if invoice_position is None:
            return []
        
        # Calculate which payments were used to pay this invoice
        payment_reductions = []
        remaining_amount_to_reduce = invoice_amount
        
        # Find which payments were used to pay this specific invoice
        cumulative_payment_amount = 0
        for payment_id, payment_amount, payment_date in payments:
            cumulative_payment_amount += payment_amount
            
            # If this payment was used to pay invoices up to and including our target invoice
            if cumulative_payment_amount > cumulative_invoice_amount:
                # Calculate how much of this payment was used for our target invoice
                amount_used_for_this_invoice = min(
                    remaining_amount_to_reduce,
                    cumulative_payment_amount - cumulative_invoice_amount
                )
                
                if amount_used_for_this_invoice > 0:
                    payment_reductions.append({
                        'payment_id': payment_id,
                        'amount': amount_used_for_this_invoice,
                        'date': payment_date.split()[0] if ' ' in payment_date else payment_date
                    })
                    remaining_amount_to_reduce -= amount_used_for_this_invoice
                
                if remaining_amount_to_reduce <= 0:
                    break
        
        return payment_reductions
    
    def reduce_payment_amounts(self, payment_reductions, admin_uuid):
        """Reduce payment amounts based on the calculated reductions"""
        total_reduction = 0
        
        for reduction in payment_reductions:
            payment_id = reduction['payment_id']
            amount_to_reduce = reduction['amount']
            
            # Get current payment amount
            self.cursor.execute("SELECT amount FROM payments WHERE id = ?", (payment_id,))
            current_amount = self.cursor.fetchone()[0]
            
            # Calculate new amount
            new_amount = current_amount - amount_to_reduce
            
            if new_amount > 0:
                # Update payment amount
                self.cursor.execute("UPDATE payments SET amount = ? WHERE id = ?", (new_amount, payment_id))
            else:
                # Delete payment if amount becomes zero or negative
                self.cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            
            total_reduction += amount_to_reduce
        
        # Update admin's total_paid
        self.cursor.execute("""
            UPDATE admin_accounts 
            SET total_paid = total_paid - ? 
            WHERE uuid = ?
        """, (total_reduction, admin_uuid))
    
    def generate_invoices(self):
        """Generate invoices for the selected period"""
        try:
            start_date = datetime.strptime(self.start_date.get(), '%Y-%m-%d')
            end_date = datetime.strptime(self.end_date.get(), '%Y-%m-%d')
        except:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
            return
        
        # Check if backups exist
        if not os.path.exists('downloads') or not os.listdir('downloads'):
            messagebox.showerror("Error", "No backup files found. Please download backups first.")
            return
        
        # Generate invoices with accounting integration
        try:
            # Delete old invoices
            delete_folder("invoices")
            
            # Import enhanced data processing
            from enhanced_data_processing import process_invoices_with_accounting
            
            # Process invoices with accounting (without adding to admin accounts)
            total_earnings = process_invoices_with_accounting(self.conn, start_date, end_date)
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            
            messagebox.showinfo("Success", 
                              f"Invoices generated successfully!\nTotal earnings: {self.format_amount_for_display(total_earnings)}K تومان\n\nNote: Use 'Add Invoice Amounts to Accounts' button to add these amounts to admin accounts.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate invoices: {str(e)}")
    
    def add_invoice_amounts_to_accounts(self):
        """Add generated invoice amounts to admin accounts"""
        try:
            # Check if invoices exist
            if not os.path.exists('invoices'):
                messagebox.showwarning("Warning", "No invoices found. Please generate invoices first.")
                return
            
            # Import enhanced data processing to calculate amounts
            from enhanced_data_processing import process_invoices_with_accounting
            
            # Get the date range from the GUI
            try:
                start_date = datetime.strptime(self.start_date.get(), '%Y-%m-%d')
                end_date = datetime.strptime(self.end_date.get(), '%Y-%m-%d')
            except:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
                return
            
            # Calculate earnings and add to admin accounts
            total_earnings = process_invoices_with_accounting(self.conn, start_date, end_date, add_to_accounts=True)
            
            # Refresh displays
            self.load_admin_accounts()
            self.load_dashboard_data()
            
            messagebox.showinfo("Success", 
                              f"Invoice amounts added to admin accounts!\nTotal earnings: {self.format_amount_for_display(total_earnings)}K تومان")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add invoice amounts: {str(e)}")
    
    def update_invoice_database(self, start_date, end_date):
        """Update invoice database with generated invoices"""
        # This would need to be implemented to parse the generated PDFs
        # and extract invoice data to store in the database
        pass
    
    def load_invoices(self):
        """Load invoices in the invoices tab"""
        # Clear existing items
        for item in self.invoices_tree.get_children():
            self.invoices_tree.delete(item)
        
        # Get invoices from database
        self.cursor.execute('''
            SELECT invoice_date, 
                   (SELECT name FROM admin_accounts WHERE uuid = i.admin_uuid) as admin_name,
                   usage_gb, amount, status, pdf_path
            FROM invoices i
            ORDER BY invoice_date DESC
        ''')
        
        for row in self.cursor.fetchall():
            self.invoices_tree.insert('', 'end', values=row)
    
    def open_invoice_pdf(self, event):
        """Open invoice PDF file"""
        selection = self.invoices_tree.selection()
        if selection:
            item = self.invoices_tree.item(selection[0])
            pdf_path = item['values'][5]
            
            if pdf_path and os.path.exists(pdf_path):
                import subprocess
                import platform
                
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', pdf_path])
                elif platform.system() == 'Windows':
                    subprocess.call(['start', pdf_path], shell=True)
                else:  # Linux
                    subprocess.call(['xdg-open', pdf_path])
            else:
                messagebox.showwarning("Warning", "PDF file not found")
    


def main():
    root = tk.Tk()
    app = VPNAccountingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 