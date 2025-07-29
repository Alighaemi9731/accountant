from datetime import datetime, timedelta
from config import PANELS
from config import TELEGRAM_ACCOUNTS
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os
from utils import convert_non_ascii_to_ascii, parse_date, reshape_rtl_text
from config import CARD_DETAILS, TOTAL
import random
import sqlite3

# Register a font that supports Persian characters
pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

def f(admin_name):
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = 'DejaVuSans'
    centered_style = styles['Normal'].clone('CenteredStyle')
    centered_style.alignment = 1  # 1 is for CENTER alignment
    return Paragraph(reshape_rtl_text(admin_name), centered_style)

def generate_pdf_from_summary(usage_summary, output_file, unpaid_remainder=0):
    # Create a SimpleDocTemplate object with specified output file
    pdf = SimpleDocTemplate(output_file, pagesize=letter)
    elements = []
    # Create data for the table
    data = [[f("نام ادمین"), f("مصرف کل"), f("قیمت هر گیگ"), f("مجموع")]]
    temp = 0
    for admin_name, summary in usage_summary.items():
        total_usage, admins_price_per_GB, total_cost = summary
        temp += total_cost
        data.append([f(admin_name), total_usage, admins_price_per_GB, f"{total_cost:,}"])
    
    # Add unpaid remainder row if there is any
    if unpaid_remainder > 0:
        data.append([f('باقیمانده قبلی'), None, None, f"{unpaid_remainder:,}"])
    
    # Calculate total including unpaid remainder
    total_amount = temp + unpaid_remainder
    data.append([f('مبلغ قابل پرداخت'), None, None, f"{total_amount:,}"])
    
    global TOTAL
    TOTAL += temp
    print(TOTAL)
    if temp > 10000000:
        print(20*"*" + "admin sell over 10M!!**" + 20*"*")

    random_key = random.choice(list(CARD_DETAILS.keys()))
    random_value = CARD_DETAILS[random_key]
    card_data = [[f('شماره کارت'), random_key, f("بنام"), f(random_value)]]
    card_table = Table(card_data)
    

    # Create the Table object
    table = Table(data)
    # Apply styles to the table
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.gray),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen)])
    
    # Add special styling for unpaid remainder row if it exists
    if unpaid_remainder > 0:
        style.add('BACKGROUND', (0, -2), (-1, -2), colors.lightcoral)  # Unpaid remainder row
        style.add('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold')    # Make it bold
    
    style2 = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.greenyellow),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        # Style for data rows
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        # New style for the last row (all columns)
                        ('BACKGROUND', (-1, -1), (-1, -1), colors.greenyellow),  # Change color to lightblue
                        ('FONTNAME', (-1, -1), (-1, -1), 'Helvetica'),  # Change font to regular Helvetica
                        ])
    table.setStyle(style)
    card_table.setStyle(style2)
    # Add the table to the elements list
    elements.append(table)
    elements.append(card_table)
    # Build the PDF document
    pdf.build(elements)

def create_pdf_invoice(admin_name, invoice_data, total_usage, file_name, prev_invoice_date, end_date, panel_number, telegram_account, parent_admin, row_par_name):
    
    # Create the nested directory structure if it doesn't exist
    folder_path = os.path.join("invoices",f'{telegram_account}', row_par_name)  # Combine telegram_account and parent_admin paths
    os.makedirs(folder_path, exist_ok=True)  # Create the directory recursively

    doc = SimpleDocTemplate(os.path.join(folder_path, file_name), pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Use the registered font
    styles['Normal'].fontName = 'DejaVuSans'
    styles['Heading2'].fontName = 'DejaVuSans'

    centered_style = styles['Normal'].clone('CenteredStyle')
    centered_style.alignment = 1  # 1 is for CENTER alignment

    # Custom styles
    header_table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightcoral),
        ('TEXTCOLOR', (0,0), (-1,0), colors.red),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-2), colors.beige),
        ('LINEBELOW', (0,0), (-1,0), 2, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.lightgrey]),  # Alternating row colors

        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen)  # Change to your desired color
    ])

    # Header data with reshaped and reordered RTL text for start and end date
    header_data = [
        ["Admin", reshape_rtl_text(convert_non_ascii_to_ascii(admin_name))],
        ["Panel", PANELS[panel_number]],
        ["Start Date", prev_invoice_date.strftime('%Y-%m-%d')],
        ["End Date", end_date.strftime('%Y-%m-%d')],
        ["usage", total_usage]
    ]

    # Create and style the header table
    header_table = Table(header_data, colWidths=[2*inch, 4*inch])
    header_table.setStyle(header_table_style)
    elements.append(header_table)

    # Table Data
    SUM = Paragraph(reshape_rtl_text("مجموع"), centered_style)
    data = [['Name', 'UUID', 'Start Date', 'Usage (GB)']] + invoice_data + [[SUM, '', '', total_usage]]

    # Create a table instance
    table = Table(data, colWidths=[2*inch, 2*inch, 1.5*inch, 1*inch])

    # Add style to the table
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-2), colors.beige),
        ('BACKGROUND', (-1,-1), (-1,-1), colors.blue),  # Total row background
        ('LINEBELOW', (0,0), (-1,0), 2, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.lightgrey])  # Alternating row colors
    ])
    table.setStyle(style)

    elements.append(table)
    doc.build(elements)
    print(f"Invoice created for {admin_name} as {file_name}")

def create_invoices(descendant_admins: list, users: list, prev_invoice_date: str, panel_number: int, total_usages : list, end_date_str: str = None):
    date = parse_date(prev_invoice_date)
    if date:
        prev_invoice_date = date
    else:
        prev_invoice_date = parse_date("2023 1 1")
    
    # Use provided end_date_str if available, otherwise default to yesterday
    if end_date_str:
        end_date = parse_date(end_date_str)
        if not end_date:
            end_date = datetime.now() - timedelta(days=1)
    else:
        end_date = datetime.now() - timedelta(days=1)  # Yesterday's date

    # Get telegram account and price from the main admin (parent)
    telegram_account = None
    parent_price_per_gb = 1000  # Default fallback
    
    for admin in descendant_admins:
        admin_uuid = admin.get('uuid')
        if admin_uuid in TELEGRAM_ACCOUNTS:
            telegram_account = TELEGRAM_ACCOUNTS[admin_uuid][0]
            parent_price_per_gb = TELEGRAM_ACCOUNTS[admin_uuid][2]  # Parent's price
            break
    
    # If no admin found in TELEGRAM_ACCOUNTS, use a default
    if telegram_account is None:
        telegram_account = "default_account"
    row_par_name = descendant_admins[0].get('name', 'No Name')
    parent_admin_name = reshape_rtl_text(descendant_admins[0].get('name', 'No Name'))
    total_usage_main_admin = 0
    usage_summary = {}
    for admin in descendant_admins:
        admin_uuid = admin.get('uuid')
        admin_name = admin.get('name', 'No Name')

        # Filter users added by this admin, after the previous invoice date, and before today
        # Exclude users with usage_limit_GB equal to 1
        filtered_users = [user for user in users if user.get('added_by_uuid') == admin_uuid 
                          and user.get('start_date') is not None
                          and prev_invoice_date < datetime.strptime(user.get('start_date'), "%Y-%m-%d") <= end_date
                          and user.get('usage_limit_GB', 0) != 1]

        styles = getSampleStyleSheet()
        styles['Normal'].fontName = 'DejaVuSans'

        # Create a custom style for centered text
        centered_style = styles['Normal'].clone('CenteredStyle')
        centered_style.alignment = 1  # 1 is for CENTER alignment

        # Define a custom paragraph style with Courier font
        uuid_style = ParagraphStyle(
            name="custom_style",
            fontName="Courier",  # Use the Courier font
            spaceAfter=12,
            textColor=colors.black
        )

        # Reshape and reorder each user's name and use Paragraph with centered style
        invoice_data = [[Paragraph(reshape_rtl_text(user.get('name')[:15]), centered_style), 
                         Paragraph(user.get('uuid')[:18] + "...", uuid_style), 
                         user.get('start_date'), 
                         user.get('usage_limit_GB')] 
                         for user in filtered_users]
        total_usage = sum(user.get('usage_limit_GB', 0) for user in filtered_users)
        total_usage_main_admin += total_usage
        # Save to PDF file
        file_name = f"factor_{admin_name}.pdf"
        # Use parent's price per GB for all admins (main and children)
        admins_price_per_GB = parent_price_per_gb
        usage_summary[admin_name] = [total_usage, admins_price_per_GB, total_usage * admins_price_per_GB]
        create_pdf_invoice(reshape_rtl_text(admin_name), invoice_data, total_usage, file_name, prev_invoice_date, end_date, panel_number, telegram_account, parent_admin_name, row_par_name)
    
    
    # Calculate unpaid remainder from database for the main admin
    # This should be calculated BEFORE any current invoice amounts are added to the database
    unpaid_remainder = 0
    try:
        # Connect to database
        conn = sqlite3.connect('vpn_accounting.db')
        cursor = conn.cursor()
        
        # Get the main admin UUID (first admin in descendant_admins)
        main_admin_uuid = descendant_admins[0].get('uuid')
        
        # Get total earned and total paid for the main admin
        # This represents the balance from PREVIOUS invoices and payments only
        cursor.execute("""
            SELECT total_earned, total_paid FROM admin_accounts 
            WHERE uuid = ?
        """, (main_admin_uuid,))
        
        result = cursor.fetchone()
        if result:
            total_earned, total_paid = result
            total_earned = total_earned or 0
            total_paid = total_paid or 0
            
            # Calculate unpaid remainder from previous invoices only
            unpaid_remainder = total_earned - total_paid
            
            # Only include positive remainder (if there's unpaid amount)
            if unpaid_remainder < 0:
                unpaid_remainder = 0
            
            print(f"Admin {descendant_admins[0].get('name', 'Unknown')}: Previous earned={total_earned}, paid={total_paid}, unpaid_remainder={unpaid_remainder}")
        
        conn.close()
    except Exception as e:
        print(f"Warning: Could not get unpaid remainder from database: {e}")
        unpaid_remainder = 0
    
    # Create the nested directory structure if it doesn't exist
    folder_path = os.path.join("invoices",f'{telegram_account}', row_par_name)  # Combine telegram_account and parent_admin paths
    os.makedirs(folder_path, exist_ok=True)  # Create the directory recursively
    name_of_final_pdf = 'مجموع فاکتور ها.pdf'
    
    # Calculate current invoice total for debugging
    current_total = sum(summary[2] for summary in usage_summary.values())
    print(f"Current invoice total: {current_total:,}")
    print(f"Unpaid remainder from previous: {unpaid_remainder:,}")
    print(f"Total payable amount: {current_total + unpaid_remainder:,}")
    
    generate_pdf_from_summary(usage_summary, os.path.join(folder_path, name_of_final_pdf), unpaid_remainder)

    total_usages[0] += total_usage_main_admin


