#!/usr/bin/env python3
"""
Seed script for CentrAlign Task Worker Sandbox.
Generates:
1. Seed vendor and invoice dataset in sandbox/data/vendors.json
2. Authentic downloadable PDF invoices in sandbox/data/invoices/<vendor_slug>/
3. Freshly initialized SQLite database in sandbox/data/finance.db
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Ensure project root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from sandbox.config import (
    DATA_DIR,
    INVOICES_DIR,
    VENDORS_FILE,
    FINANCE_DB_PATH
)
from sandbox.finance_system.db import init_db, clear_payables

SEED_VENDORS = [
    {
        "id": "v-acme",
        "name": "Acme Cloud Corp",
        "slug": "acme-cloud",
        "category": "Cloud Infrastructure & Hosting",
        "contact_email": "billing@acmecloud.example.com",
        "layout": "table",
        "invoices": [
            {
                "invoice_no": "INV-ACME-1001",
                "issue_date": "2026-01-15",
                "due_date": "2026-02-15",
                "amount": 1450.00,
                "currency": "USD",
                "description": "Monthly Enterprise Kubernetes Cluster & Object Storage",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-ACME-1002",
                "issue_date": "2026-04-10",
                "due_date": "2026-05-10",
                "amount": 1820.50,
                "currency": "USD",
                "description": "Compute Instance Auto-scale Bursting & Egress Bandwidth",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-ACME-1003",
                "issue_date": "2026-07-22",
                "due_date": "2026-08-22",
                "amount": 2150.00,
                "currency": "USD",
                "description": "Dedicated Database Managed Instances & Daily Snapshots",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-ACME-1004",
                "issue_date": "2026-09-30",
                "due_date": "2026-10-30",
                "amount": 2490.75,
                "currency": "USD",
                "description": "Q3 Cloud Capacity Reservation & DDoS Shield Protection",
                "status": "Open"
            }
        ]
    },
    {
        "id": "v-global",
        "name": "Global Logistics Ltd",
        "slug": "global-logistics",
        "category": "Freight & Supply Chain",
        "contact_email": "accounts@globallogistics.example.com",
        "layout": "table",
        "invoices": [
            {
                "invoice_no": "INV-GL-501",
                "issue_date": "2025-11-05",
                "due_date": "2025-12-05",
                "amount": 5320.00,
                "currency": "USD",
                "description": "Regional Freight Haulage & Cross-Dock Warehousing",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-GL-502",
                "issue_date": "2026-02-18",
                "due_date": "2026-03-18",
                "amount": 4890.00,
                "currency": "USD",
                "description": "Cold Chain Refrigerated Transit Batch #8812",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-GL-503",
                "issue_date": "2026-05-12",
                "due_date": "2026-06-12",
                "amount": 6110.25,
                "currency": "USD",
                "description": "Air Express Consolidated Delivery Route NYC-CHI",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-GL-504",
                "issue_date": "2026-08-01",
                "due_date": "2026-09-01",
                "amount": 5740.00,
                "currency": "USD",
                "description": "Harbor Container Offload Handling & Customs Filing",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-GL-505",
                "issue_date": "2026-10-02",
                "due_date": "2026-11-02",
                "amount": 7250.00,
                "currency": "USD",
                "description": "End-to-End Fleet Transport & Expedited Delivery",
                "status": "Open"
            }
        ]
    },
    {
        "id": "v-vertex",
        "name": "Vertex Analytics",
        "slug": "vertex-analytics",
        "category": "Data Science & BI Platforms",
        "contact_email": "invoicing@vertexanalytics.example.com",
        "layout": "cards",  # Non-standard card grid layout to test agent layout generalization
        "invoices": [
            {
                "invoice_no": "INV-VA-201",
                "issue_date": "2026-02-01",
                "due_date": "2026-03-01",
                "amount": 3200.00,
                "currency": "USD",
                "description": "Predictive Pipeline SaaS Tier - 50 Seats",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-VA-202",
                "issue_date": "2026-04-15",
                "due_date": "2026-05-15",
                "amount": 3200.00,
                "currency": "USD",
                "description": "Predictive Pipeline SaaS Tier - 50 Seats",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-VA-203",
                "issue_date": "2026-06-30",
                "due_date": "2026-07-30",
                "amount": 3850.00,
                "currency": "USD",
                "description": "Predictive Pipeline SaaS Tier + Custom Vector Index Add-on",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-VA-204",
                "issue_date": "2026-09-15",
                "due_date": "2026-10-15",
                "amount": 4100.00,
                "currency": "USD",
                "description": "Enterprise BI Integration Suite & SLA Support Tier 1",
                "status": "Open"
            }
        ]
    },
    {
        "id": "v-nexus",
        "name": "Nexus Software Solutions",
        "slug": "nexus-software",
        "category": "Enterprise ERP & Workflow Dev",
        "contact_email": "billing@nexussoftware.example.com",
        "layout": "table",
        "invoices": [
            {
                "invoice_no": "INV-NX-801",
                "issue_date": "2026-03-10",
                "due_date": "2026-04-10",
                "amount": 9500.00,
                "currency": "USD",
                "description": "Phase 1 Custom Connector Engineering & Auth Gateway",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-NX-802",
                "issue_date": "2026-06-15",
                "due_date": "2026-07-15",
                "amount": 9500.00,
                "currency": "USD",
                "description": "Phase 2 Security Hardening & Automated Testing Suite",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-NX-803",
                "issue_date": "2026-09-28",
                "due_date": "2026-10-28",
                "amount": 10200.00,
                "currency": "USD",
                "description": "Production Cutover, On-Call Maintenance & Knowledge Transfer",
                "status": "Open"
            }
        ]
    },
    {
        "id": "v-prime",
        "name": "Prime Hardware & Supplies",
        "slug": "prime-supplies",
        "category": "Office Equipment & Datacenter Gear",
        "contact_email": "orders@primesupplies.example.com",
        "layout": "table",
        "invoices": [
            {
                "invoice_no": "INV-PHS-010",
                "issue_date": "2025-12-10",
                "due_date": "2026-01-10",
                "amount": 840.50,
                "currency": "USD",
                "description": "Ergonomic Peripherals & High-Speed Cable Bundles",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-PHS-011",
                "issue_date": "2026-02-14",
                "due_date": "2026-03-14",
                "amount": 1210.00,
                "currency": "USD",
                "description": "Datacenter Rack Power Distribution Units (PDUs)",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-PHS-012",
                "issue_date": "2026-04-20",
                "due_date": "2026-05-20",
                "amount": 675.25,
                "currency": "USD",
                "description": "High-Durability Surge Arrestors & Fiber Optic Jumpers",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-PHS-013",
                "issue_date": "2026-07-04",
                "due_date": "2026-08-04",
                "amount": 1890.00,
                "currency": "USD",
                "description": "Dual-Monitor Mounts, Power Banks & Smart Strips",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-PHS-014",
                "issue_date": "2026-08-25",
                "due_date": "2026-09-25",
                "amount": 1430.80,
                "currency": "USD",
                "description": "Cat6e Shielded Spools & Patch Panel Modular Blocks",
                "status": "Paid"
            },
            {
                "invoice_no": "INV-PHS-015",
                "issue_date": "2026-10-05",
                "due_date": "2026-11-05",
                "amount": 2195.40,
                "currency": "USD",
                "description": "Smart UPS 3000VA Backup Power Station Battery Modules",
                "status": "Open"
            }
        ]
    }
]

def generate_invoice_pdf(vendor: dict, inv: dict, output_path: Path):
    """Generates an authentic PDF invoice file using ReportLab."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold'
    )
    meta_style = ParagraphStyle(
        'InvoiceMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569')
    )
    bold_style = ParagraphStyle(
        'InvoiceBold',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )

    story = []

    # Header block
    header_data = [
        [
            Paragraph(f"<b>{vendor['name']}</b><br/>{vendor['category']}<br/>{vendor['contact_email']}", meta_style),
            Paragraph("<b>INVOICE</b>", title_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[340, 200])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceBefore=5, spaceAfter=15))

    # Bill-to & Invoice Metadata
    details_data = [
        [
            Paragraph("<b>BILL TO:</b><br/>CentrAlign Enterprises Inc.<br/>100 Technology Plaza, Suite 400<br/>accounts-payable@centralign.example.com", meta_style),
            Paragraph(
                f"<b>Invoice #:</b> {inv['invoice_no']}<br/>"
                f"<b>Issue Date:</b> {inv['issue_date']}<br/>"
                f"<b>Due Date:</b> <font color='#DC2626'><b>{inv['due_date']}</b></font><br/>"
                f"<b>Status:</b> {inv['status']}",
                meta_style
            )
        ]
    ]
    details_table = Table(details_data, colWidths=[340, 200])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 20))

    # Line Item Table
    line_data = [
        ["Line Item Description", "Qty", "Unit Price", "Total Amount"],
        [inv['description'], "1", f"{inv['currency']} {inv['amount']:,.2f}", f"{inv['currency']} {inv['amount']:,.2f}"]
    ]
    line_table = Table(line_data, colWidths=[300, 60, 90, 90])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))

    # Summary Box
    summary_data = [
        ["", "Subtotal:", f"{inv['currency']} {inv['amount']:,.2f}"],
        ["", "Tax / VAT (0.00%):", f"{inv['currency']} 0.00"],
        ["", "Total Due:", f"{inv['currency']} {inv['amount']:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[300, 140, 100])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (1, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 2), (-1, 2), 12),
        ('TEXTCOLOR', (1, 2), (-1, 2), colors.HexColor('#0F172A')),
        ('LINEABOVE', (1, 2), (-1, 2), 1, colors.HexColor('#0F172A')),
        ('TOPPADDING', (1, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (1, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    # Payment Remittance Footer
    footer_text = (
        "<b>Payment Remittance Instructions:</b><br/>"
        "Please remit payment via ACH / Electronic Wire to account ending in #9942.<br/>"
        f"Reference Invoice Number <b>{inv['invoice_no']}</b> on wire memo. Thank you for your business!"
    )
    story.append(Paragraph(footer_text, meta_style))

    doc.build(story)

def main():
    print("[Seeding] Initializing CentrAlign Task Worker Sandbox Data...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Reset / initialize SQLite database
    print("[Database] Initializing SQLite Finance database...")
    clear_payables()
    print("   -> SQLite payables cleared & ready at:", FINANCE_DB_PATH)

    # 2. Generate JSON catalog & PDF files
    catalog = []
    total_invoices = 0

    for vendor in SEED_VENDORS:
        v_copy = dict(vendor)
        v_copy["invoices"] = []
        vendor_pdf_dir = INVOICES_DIR / vendor["slug"]
        vendor_pdf_dir.mkdir(parents=True, exist_ok=True)

        for inv in vendor["invoices"]:
            pdf_filename = f"{inv['invoice_no']}.pdf"
            pdf_rel_path = f"/download/{vendor['slug']}/{pdf_filename}"
            pdf_file_path = vendor_pdf_dir / pdf_filename

            # Build PDF
            generate_invoice_pdf(vendor, inv, pdf_file_path)

            inv_entry = dict(inv)
            inv_entry["pdf_url"] = pdf_rel_path
            inv_entry["pdf_file"] = str(pdf_file_path.relative_to(DATA_DIR)).replace("\\", "/")
            v_copy["invoices"].append(inv_entry)
            total_invoices += 1

        catalog.append(v_copy)

    with open(VENDORS_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"[Catalog] Seeded {len(catalog)} vendors with {total_invoices} total invoices to {VENDORS_FILE}")
    print("[PDFs] Generated authentic PDF documents in:", INVOICES_DIR)

if __name__ == "__main__":
    main()
