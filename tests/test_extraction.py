from app.services.extraction_service import extract_document


def test_invoice_layout_values_are_extracted_without_tax_rate():
    text = """Subtotal $135.00 Sales Tax 8% $12.48 Shipping and Handling $10.00 Total Due $157.48 Invoice Details: Invoice #: 6825 Invoice date: Nov 03, 2022"""
    data = extract_document("invoice", text, [text])
    assert data["invoice_number"]["value"] == "6825"
    assert data["invoice_date"]["value"] == "2022-11-03"
    assert data["subtotal"]["value"] == 135.0
    assert data["tax_amount"]["value"] == 12.48
    assert data["total_amount"]["value"] == 157.48


def test_receipt_style_invoice_extracts_date_gst_total_and_change():
    text = """99 SPEED MART S/B (519537-X)
INVOICE NO : 18311/102/T0395
07:44PM 566890 17-02-18
489 TIGER BEER CAN 4*6*320M RM108.50 S
Total Sales (Inclusive GST) RM 108.50
CASH RM 150.00
CHANGE RM 41.50
GST Summary Amount(RM) Tax(RM)
S = 6% 102.36 6.14"""
    data = extract_document("invoice", text, [text])
    assert data["invoice_number"]["value"] == "18311/102/T0395"
    assert data["invoice_date"]["value"] == "2018-02-17"
    assert data["currency"]["value"] == "MYR"
    assert data["subtotal"]["value"] == 102.36
    assert data["tax_amount"]["value"] == 6.14
    assert data["total_amount"]["value"] == 108.50
    assert data["cash_paid"]["value"] == 150.00
    assert data["change"]["value"] == 41.50


def test_column_invoice_extracts_parties_and_summary_totals():
    text = """INVOICE
INVOICE NO. 118
DATE: March 9, 2022
BILL FROM
BLUE STREAK ELECTRONICS
30 Moyal Court
BILL TO
GEONICS LTD
1745 Meyers Drive
DESCRIPTION QUANTITY PRICE TOTAL
3M Scotchcast Electrical Resin 2 346.00 346.00
3M DP460 EG Epoxy Adhesive 4 226.00 226.00
Freight AE Blake Montreal to Aerospace Metal 6 136.00 136.00
Lead-time is a mere estimate 8 96.00 96.00
Subtotal 804
Sales Tax 8% 63.47
S&H 50
Total Due 916.47"""
    data = extract_document("invoice", text, [text])

    assert data["invoice_number"]["value"] == "118"
    assert data["invoice_date"]["value"] == "2022-03-09"
    assert data["vendor_name"]["value"] == "BLUE STREAK ELECTRONICS"
    assert data["customer_name"]["value"] == "GEONICS LTD"
    assert data["subtotal"]["value"] == 804.0
    assert data["tax_amount"]["value"] == 63.47
    assert data["total_amount"]["value"] == 916.47


def test_sparse_work_order_invoice_extracts_total_without_subtotal():
    text = """Invoice
Meld #298839
BEYOND DIGITAL IMAGING
36 Apple Creek Blvd.
MARKHAM, L3R 4Y4
Total: $5257
From
MARKHAM
Invoice date
Sept. 5, 2023
No. Description Quantity Rate Cost Amount
5991 3M SJ3550 Dual Lock Fastener 9 $367 $367 $3303"""
    data = extract_document("invoice", text, [text])

    assert data["invoice_number"]["value"] == "298839"
    assert data["invoice_date"]["value"] == "2023-09-05"
    assert data["vendor_name"]["value"] == "BEYOND DIGITAL IMAGING"
    assert data["total_amount"]["value"] == 5257.0
