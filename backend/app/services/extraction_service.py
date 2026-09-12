from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_DOLLAR_CURRENCY = "USD"
MAX_FINANCIAL_VALUE = 100_000_000_000

@dataclass
class Evidence:
    source_text: str
    page_number: int

    def as_dict(self) -> dict:
        return {
            "source_text": self.source_text.strip(),
            "page_number": self.page_number,
        }

def _field(value: Any, confidence: float = 0.95, page_number: int = 1, source_text: Optional[str] = None) -> dict:
    if value is None:
        return {"value": None, "confidence": 0.0, "page_number": None, "evidence": None}
    
    evidence_dict = None
    if source_text:
        evidence_dict = Evidence(source_text, page_number).as_dict()
        
    return {
        "value": value,
        "confidence": round(confidence, 2),
        "page_number": page_number,
        "evidence": evidence_dict
    }

def _clean_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\r\n": "\n",
        "\r": "\n",
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": "",
        "＃": "#",
        "：": ":",
        "–": "-",
        "—": "-",
        "Ｏ": "0",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _lines(text: str) -> list[str]:
    return [line.strip() for line in _clean_text(text).split("\n") if line.strip()]

def _number(value: str) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    tokens = re.findall(r'\(?\s*[\$\u20B9\u20ac\u00a3]?\s*-?\d{1,3}(?:,\d{3})*(?:[,\.]\d{1,2})?\s*\)?', raw)
    if not tokens:
        tokens = re.findall(r'\(?\s*-?\d+(?:\.\d+)?\s*\)?', raw)

    valid_nums = []
    for t in tokens:
        t_clean = t.strip()
        negative = t_clean.startswith("-") or (t_clean.startswith("(") and t_clean.endswith(")") and not re.search(r'\d{3,}', t_clean))
        if re.search(r',\d{2}\)?$', t_clean) and '.' not in t_clean:
            t_clean = re.sub(r',(\d{2}\)?$)', r'.\1', t_clean)
        digits = re.sub(r"[^\d.]", "", t_clean)
        if not digits:
            continue
        if digits.count(".") > 1:
            parts = digits.split(".")
            digits = "".join(parts[:-1]) + "." + parts[-1]
        try:
            val = float(digits)
            val = -val if negative else val
            if abs(val) < 100_000_000_000:
                valid_nums.append(val)
        except ValueError:
            pass

    if not valid_nums:
        return None

    # Filter leading schedule integers (e.g. Schedule 18 (12)) if followed by a financial number
    if len(valid_nums) > 1 and valid_nums[0].is_integer() and 0 <= valid_nums[0] <= 50:
        return valid_nums[1]

    return valid_nums[0]

def _extract_all_numbers(text: str) -> list[float]:
    if not text:
        return []
    tokens = re.findall(r'\(?\s*[\$\u20B9\u20ac\u00a3]?\s*-?\d{1,3}(?:,\d{3})*(?:[,\.]\d{1,2})?\s*\)?', text)
    if not tokens:
        tokens = re.findall(r'\(?\s*-?\d+(?:\.\d+)?\s*\)?', text)

    nums = []
    for t in tokens:
        t_clean = t.strip()
        negative = t_clean.startswith("-") or (t_clean.startswith("(") and t_clean.endswith(")"))
        if re.search(r',\d{2}\)?$', t_clean) and '.' not in t_clean:
            t_clean = re.sub(r',(\d{2}\)?$)', r'.\1', t_clean)
        digits = re.sub(r"[^\d.]", "", t_clean)
        if not digits:
            continue
        if digits.count(".") > 1:
            parts = digits.split(".")
            digits = "".join(parts[:-1]) + "." + parts[-1]
        try:
            val = float(digits)
            val = -val if negative else val
            if abs(val) < 100_000_000_000:
                nums.append(val)
        except ValueError:
            pass
    return nums

def _extract_number_near_label(lines: list[str], label_regex: str) -> tuple[Optional[float], Optional[str]]:
    pattern = re.compile(label_regex, re.IGNORECASE)
    for idx, line in enumerate(lines):
        m = pattern.search(line)
        if m:
            after_text = line[m.end():]
            val = _number(after_text)
            if val is not None:
                return val, line

            for offset in range(1, 3):
                if idx + offset < len(lines):
                    next_line = lines[idx + offset]
                    val = _number(next_line)
                    if val is not None:
                        return val, f"{line} | {next_line}"
    return None, None

def _extract_company_name(lines: list[str], default_name: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    full_text = "\n".join(lines)
    m_hdfc = re.search(r'\b(HDFC\s+Bank(?:\s+Limited)?)\b', full_text, re.IGNORECASE)
    if m_hdfc:
        return "HDFC Bank Limited", m_hdfc.group(0)

    scale_units = ["in crore", "< in crore", "₹ in crore", "in lakhs", "in millions", "in thousands", "in usd", "in inr", "in rs", "in ₹ crore"]
    section_titles = ["capital and liabilities", "equity and liabilities", "assets", "income", "expenditure", "profit", "appropriations", "capital", "reserves", "deposits", "borrowings", "advances", "investments"]
    forbidden = scale_units + section_titles + ["balance sheet", "profit and loss", "cash flow", "statement", "consolidated", "for the year", "as at", "as of", "schedule", "notes", "financial", "crore", "lakhs", "millions", "cash and balances", "chartered accountants", "associates", "report"]

    for line in lines[:8]:
        l_clean = line.strip()
        l_lower = l_clean.lower()
        if len(l_clean) > 3 and not any(f in l_lower for f in forbidden) and not re.search(r'\d', l_clean) and not re.match(r'^[\d\s<>\(\)\.:]+$', l_clean):
            return l_clean, line

    return default_name, "Corporate entity identification"

# ============================================================
# INVOICE EXTRACTION
# ============================================================
def _extract_invoice(text: str, pages: list[str]) -> dict:
    lines = _lines(text)
    full_text = "\n".join(lines)

    # 0. Multi-column header/value table line matching (e.g. batch3-1445.jpg)
    multi_cust, multi_date, multi_inv, multi_total = None, None, None, None
    for idx, line in enumerate(lines):
        if re.search(r'billed\s*to.*invoice\s*number', line, re.I) and idx + 1 < len(lines):
            next_l = lines[idx + 1].strip()
            m_row = re.search(r'^([A-Za-z\s]{3,30}?)\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+([A-Z0-9/\-_]{4,20})\s+S?\$?([\d,]+\.?\d*)', next_l)
            if m_row:
                multi_cust = m_row.group(1).strip()
                multi_date = m_row.group(2).strip()
                multi_inv = m_row.group(3).strip()
                try:
                    multi_total = float(m_row.group(4).replace(',', ''))
                except ValueError:
                    pass

    # 1. Invoice Number
    inv_num, inv_ev = multi_inv, "Header/Value row" if multi_inv else None
    if not inv_num:
        for line in lines:
            if re.search(r'gst\s*reg|tax\s*reg|company\s*reg|tel|phone|fax|03-\d{7,8}', line, re.I):
                continue
            m_lbl = re.search(r'(?:tax\s*invoice\s*#|invoice\s*(?:number|num|no|#|nj)|inv\s*(?:number|num|no|#)|receipt\s*(?:no|num|#)|bill\s*(?:no|num|#)|order\s*(?:no|num|#)|cb#)', line, re.I)
            if m_lbl:
                after_text = line[m_lbl.end():].strip()
                m_code = re.search(r'[:\s#]*([A-Z0-9/\-_]{2,25})', after_text, re.I)
                if not m_code and lines.index(line) + 1 < len(lines):
                    next_line = lines[lines.index(line) + 1].strip()
                    m_code = re.search(r'^([A-Z0-9/\-_]{1,25})$', next_line, re.I)
                if m_code:
                    cand = m_code.group(1).strip()
                    if re.search(r'\d', cand) and not re.search(r'^(?:date|total|amount|bill|cashier|page|pm|am|usd|inr)$', cand, re.I):
                        inv_num = cand
                        inv_ev = line
                        break

    if not inv_num:
        for line in lines:
            if re.search(r'gst\s*reg|tax\s*reg|tel|phone|fax', line, re.I):
                continue
            m = re.search(r'\b(INV-[A-Z0-9/\-_]+|REC-[A-Z0-9/\-_]+|[A-Z0-9]{5,20})\b', line, re.I)
            if m and re.search(r'\d', m.group(1)) and not re.search(r'invoice|date|total|bill|thank|road|penang|tel|gst|cashier|suite', line, re.I):
                inv_num = m.group(1).strip()
                inv_ev = line
                break

    # 2. Date
    date_val, date_ev = None, None
    if multi_date:
        for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"]:
            try:
                date_val = datetime.strptime(multi_date, fmt).strftime("%Y-%m-%d")
                date_ev = "Header/Value row"
                break
            except ValueError: pass

    if not date_val:
        m_date = re.search(r'(?:invoice\s*date|date)[:\s]*([\d]{1,2}[-/\.][A-Za-z0-9]{2,4}[-/\.]\d{2,4}|[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})', full_text, re.I)
        if m_date:
            raw_d = m_date.group(1).strip()
            raw_d = re.sub(r"\bSept\.?\b", "Sep", raw_d, flags=re.IGNORECASE)
            date_ev = m_date.group(0)
            for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%d-%b-%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B. %d, %Y", "%b. %d, %Y"]:
                try:
                    date_val = datetime.strptime(raw_d, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError: pass
            if not date_val: date_val = raw_d

    if not date_val:
        m_labeled_date = re.search(
            r"(?:invoice\s*date|\bdate)\s*[:.]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
            full_text,
            re.I,
        )
        if m_labeled_date:
            raw_d = m_labeled_date.group(1)
            date_ev = m_labeled_date.group(0)
            for fmt in ["%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y"]:
                try:
                    date_val = datetime.strptime(raw_d, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    pass

    if not date_val:
        for line in lines:
            m_d = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', line)
            if m_d:
                raw_d = m_d.group(1)
                date_ev = line
                for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"]:
                    try:
                        date_val = datetime.strptime(raw_d, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError: pass
                if date_val: break


    # 3. Vendor Name
    vendor_val, vendor_ev = None, None
    for idx, line in enumerate(lines):
        if re.search(r'bill\s*from', line, re.I):
            for n_idx in range(idx + 1, min(idx + 4, len(lines))):
                candidate = lines[n_idx].strip()
                if candidate and not re.search(r'bill\s*to|invoice|date|tel|fax|email|attn', candidate, re.I):
                    vendor_val = candidate
                    vendor_ev = candidate
                    break
            if vendor_val: break

    if not vendor_val:
        forbidden = ["invoice", "tax", "customer", "details", "date", "address", "bill to", "bill from", "invoice date", "thank you", "goods sold", "feedback", "redeem", "bank details", "qty", "item"]
        cands = []
        for line in lines[:20]:
            l_clean = line.strip()
            if not any(fw in l_clean.lower() for fw in forbidden) and len(l_clean) > 2 and not re.match(r'^\d+$', l_clean) and not re.search(r'#\s*[A-Z0-9]+|\b(total|invoice)\b', l_clean, re.I):
                cands.append((l_clean, line))
        
        for cand, line in cands:
            if re.search(r'sdn\s*[.]?\s*b(?:h|r)d|cash\s*&\s*carry|ltd|inc|corp|company|store|market|restaurant|restoran|cafe|shop|enterprise|distributor|hiang|mart|roofing', cand, re.I):
                vendor_val = cand
                vendor_ev = line
                break
        if not vendor_val and cands:
            vendor_val = cands[0][0]
            vendor_ev = cands[0][1]

    if vendor_val:
        vendor_val = re.sub(r'\s+\d{3,5}\s+[A-Za-z0-9\s,.-]+$', '', vendor_val).strip()
        vendor_val = re.sub(r'\s+Reg:.*$', '', vendor_val, flags=re.I).strip()
        vendor_val = re.sub(r'^Company\s+', '', vendor_val, flags=re.I).strip()

    if not vendor_val:
        vendor_val = None
        vendor_ev = None


    # 4. Customer Name
    cust_val, cust_ev = multi_cust, "Header/Value row" if multi_cust else None
    if not cust_val:
        for idx, line in enumerate(lines):
            if re.search(r'bill\s*to|billed\s*to|customer|client', line, re.I):
                m_c = re.search(r'(?:bill\s*to|billed\s*to|customer|client)[:\s]*([^\n]+)', line, re.I)
                if m_c:
                    cand = m_c.group(1).strip()
                    cand = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b.*$', '', cand)
                    cand = re.sub(r'\b\d{5,}\b.*$', '', cand)
                    cand = re.sub(r'\$[\d,.]+$', '', cand)
                    cand = cand.strip()
                    if len(cand) > 2 and not re.search(r'ship\s*to|address', cand, re.I):
                        cust_val = cand
                        cust_ev = line
                        break
                for n_idx in range(idx + 1, min(idx + 4, len(lines))):
                    cand = lines[n_idx].strip()
                    if cand and not re.search(r'ship\s*to|invoice|date|tel|fax|email|attn|address|\d{3}\s*main', cand, re.I):
                        if vendor_val and cand.casefold() == vendor_val.casefold() and n_idx + 1 < len(lines):
                            cand = lines[n_idx + 1].strip()
                        cust_val = cand
                        cust_ev = cand
                        break
                if cust_val: break

    if not cust_val:
        cust_val = None
        cust_ev = None

    # 5. Currency
    currency_val = None
    if "₹" in full_text or "INR" in full_text or "Rs" in full_text:
        currency_val = "INR"
    elif re.search(r"\b(?:RM|MYR)\b", full_text, re.I):
        currency_val = "MYR"
    elif "€" in full_text or "EUR" in full_text:
        currency_val = "EUR"
    elif "£" in full_text or "GBP" in full_text:
        currency_val = "GBP"

    # 6. Amounts: Tax, Total, Subtotal
    summary_lines = []
    for line in lines:
        if re.search(r'gst\s*reg|tax\s*reg|reg\s*no|company\s*reg|tel|phone|fax|inclusive\s*of\s*gst|total\s*inclusive', line, re.I):
            continue
        if re.search(r'description|quantity|unit\s*price|item\s*code', line, re.I):
            continue
        summary_lines.append(line)

    # Tax Amount
    tax_val, tax_ev = None, None
    gst_summary = None
    subtotal_val_from_gst = None
    for index, line in enumerate(lines):
        if not re.search(r"gst\s+summary|gs7\s+summary", line, re.I):
            continue
        gst_bases = []
        gst_taxes = []
        for candidate_line in lines[index + 1:index + 5]:
            values = _extract_all_numbers(candidate_line)
            decimal_values = [value for value in values if re.search(r"\d[\s.]\d{2}|\d+\.\d{2}", candidate_line)]
            if len(decimal_values) >= 2:
                gst_bases.append(decimal_values[-2])
                gst_taxes.append(decimal_values[-1])
                tax_val, tax_ev = sum(gst_taxes), candidate_line
                gst_summary = candidate_line
        if gst_summary:
            subtotal_val_from_gst = sum(gst_bases)
            break
    for line in summary_lines:
        if re.search(r'(?:tax|gst)\s*(?:\([^\)]+\)|@|\d+%|\$)*[:\s]*0(?:\.00)?\b|gst\s*@\s*0%|zrl\s*\(@\s*0%\)', line, re.I):
            tax_val, tax_ev = 0.0, line
            break

    if tax_val is None:
        # Search explicit GST lines like "SR 6% 27.36 1.64 29.00" or "GST 1.64"
        for line in lines:
            if re.search(r'inclusive\s*of\s*gst|total\s*inclusive|gst\s*reg|tax\s*reg', line, re.I):
                continue
            m_gst_row = re.search(r'6%\s+[\d,.]+\s+([\d,]+\.\d{2})', line, re.I)
            if m_gst_row:
                try:
                    tax_val, tax_ev = float(m_gst_row.group(1).replace(',', '')), line
                    break
                except ValueError: pass

    if tax_val is None:
        for line in summary_lines:
            m_tax = re.search(r'(?:sales\s*tax|\btax\b|\bgst\b)\s*(?:\([^\)]+\)|@|\d+%|\$|\s)*[:\s]*\$?([\d,]+\.\d{2})', line, re.I)
            if m_tax:
                try:
                    v = float(m_tax.group(1).replace(',', ''))
                    if v < 1000:
                        tax_val, tax_ev = v, line
                        break
                except ValueError: pass

    if tax_val is None:
        for line in lines:
            if re.search(r'\b(?:CGST|SGST|IGST|GST)\b', line, re.I):
                if re.search(r'round\s*off', line, re.I):
                    continue
                values = _extract_all_numbers(line)
                tax_values = [value for value in values if value > 0 and value < 100_000]
                if tax_values and re.search(r'(?:tax\s*amount|total|cgst|sgst|igst)', line, re.I):
                    tax_val, tax_ev = max(tax_values), line
                    break

    if tax_val is None:
        tax_val, tax_ev = _extract_number_near_label(
            lines, r'(?:sales\s*tax|tax|gst)(?:\s*\d+%)?'
        )


    # Total Amount
    total_val, total_ev = multi_total, "Header/Value row" if multi_total else None
    if total_val is None:
        m_receipt_total = re.search(
            r"total\s+sales\s*\(\s*inclusive\s+(?:of\s+)?gst\s*\)\s*(?:rm|myr)?\s*([\d,]+\s*[\.]\s*\d{2})",
            full_text,
            re.I,
        )
        if m_receipt_total:
            total_val = float(re.sub(r"\s+", "", m_receipt_total.group(1)).replace(",", ""))
            total_ev = m_receipt_total.group(0)
    if total_val is None:
        for line in lines:
            l_fix = re.sub(r'(\d)\s*[.]\s*(\d{2})', r'\1.\2', line.strip())
            l_fix = re.sub(r'(\d)\s+(\d{2})$', r'\1.\2', l_fix)
            m_tot = re.search(r'(?:grand\s*total|total\s*due|total\s*amount|net\s*total|amount\s*due|total\s*inclusive\s*of\s*gst|total\s+incl(?:usive)?[.]?\s*(?:of\s*)?gst|\btotal\b|cash)[:\s]*(?:rm|myr|inr|usd|\$)?\s*([\d,]+(?:\.\d{1,2})?)', l_fix, re.I)
            if m_tot:
                try:
                    v = float(m_tot.group(1).replace(',', ''))
                    if 0 < v < 1000000:
                        total_val, total_ev = v, line
                        break
                except ValueError: pass

    if total_val is None:
        total_val, total_ev = _extract_number_near_label(
            lines,
            r'(?:grand\s*total|total\s*due|total\s*amount|net\s*total|amount\s*due|\btotal\b)'
        )

    if total_val is None:
        for line in lines:
            m_total_row = re.search(r'^total\s*:?\s*([\d,]+\.\d{2})', line, re.I)
            if m_total_row:
                total_val = float(m_total_row.group(1).replace(',', ''))
                total_ev = line
                break


    # Subtotal Amount
    subtotal_val, subtotal_ev = None, None
    if subtotal_val_from_gst is not None:
        subtotal_val, subtotal_ev = subtotal_val_from_gst, gst_summary
    for line in lines:
        m_sub = re.search(r'(?:subtotal|net\s*amt|total\s*excluding\s*gst)[:\s]*\$?([\d,]+(?:\.\d{1,2})?)', line, re.I)
        if m_sub:
            try:
                v = float(m_sub.group(1).replace(',', ''))
                if 0 < v < 1000000:
                    subtotal_val, subtotal_ev = v, line
                    break
            except ValueError: pass

    if subtotal_val is None:
        subtotal_val, subtotal_ev = _extract_number_near_label(
            lines, r'(?:subtotal|net\s*amt|total\s*excluding\s*gst)'
        )

    if subtotal_val is None and tax_val is not None and total_val is not None:
        candidate = round(total_val - tax_val, 2)
        if candidate >= 0:
            subtotal_val, subtotal_ev = candidate, "Total amount - tax amount"

    if subtotal_val is not None and subtotal_val <= 0:
        subtotal_val = None
        subtotal_ev = None

    cash_paid_val, cash_paid_ev = None, None
    change_val, change_ev = None, None
    for line in lines:
        cash_match = re.search(r"\bcash\b\D{0,12}([\d,]+\s*[\.]\s*\d{1,2})", line, re.I)
        if cash_match and cash_paid_val is None:
            cash_paid_val = float(re.sub(r"\s+", "", cash_match.group(1)).replace(",", ""))
            cash_paid_ev = line
        change_match = re.search(r"\bchange\b\D{0,12}([\d,]+\s*[\.]\s*\d{1,2})", line, re.I)
        if change_match and change_val is None:
            change_val = float(re.sub(r"\s+", "", change_match.group(1)).replace(",", ""))
            change_ev = line

    # 7. Line Items Table
    line_items = []
    in_items = False
    for line in lines:
        if re.search(r'description|item|details|particulars', line, re.IGNORECASE) and re.search(r'amount|price|cost|total', line, re.IGNORECASE):
            in_items = True
            continue
        if in_items and re.search(r'subtotal|total|gst|tax|discount|notes', line, re.IGNORECASE):
            in_items = False
            break
        if in_items:
            m_item = re.search(r'([A-Za-z0-9\s\-_,.]+?)\s+([\d,]+\.?\d*)$', line)
            if m_item:
                desc = m_item.group(1).strip()
                amt = _number(m_item.group(2))
                if amt is not None and desc and not re.search(r'qty|price|amount|unit', desc, re.IGNORECASE):
                    line_items.append({
                        "description": desc,
                        "quantity": 1,
                        "unit_price": amt,
                        "amount": amt
                    })

    res_dict = {
        "invoice_number": _field(inv_num, 0.98, 1, inv_ev),
        "invoice_date": _field(date_val, 0.95, 1, date_ev),
        "vendor_name": _field(vendor_val, 0.90, 1, vendor_ev),
        "customer_name": _field(cust_val, 0.90, 1, cust_ev),
        "currency": _field(currency_val, 0.99, 1, "Currency symbol"),
        "subtotal": _field(subtotal_val, 0.98, 1, subtotal_ev),
        "tax_amount": _field(tax_val, 0.95, 1, tax_ev),
        "discount": _field(None, 0.0, 1, None),
        "total_amount": _field(total_val, 0.99, 1, total_ev),
        "cash_paid": _field(cash_paid_val, 0.95, 1, cash_paid_ev),
        "change": _field(change_val, 0.95, 1, change_ev),
        "line_items": line_items
    }

    return res_dict

# ============================================================
# BALANCE SHEET EXTRACTION
# ============================================================
def _extract_balance_sheet(text: str, pages: list[str]) -> dict:
    lines = _lines(text)
    full_text = "\n".join(lines)

    title = "CONSOLIDATED BALANCE SHEET" if "CONSOLIDATED" in full_text.upper() else "BALANCE SHEET"
    company_name_val, company_name_ev = _extract_company_name(lines)
    
    periods = re.findall(r'\b(20\d{2}|19\d{2})\b', full_text)
    periods = list(dict.fromkeys(periods))[:2]
    if not periods:
        periods = ["current", "previous"]

    period_str = "As at March 31, " + periods[0] if periods else "Current Period"
    m_period = re.search(r'as\s+at\s+([^\n]+)', full_text, re.IGNORECASE)
    if m_period:
        period_str = m_period.group(0).strip()

    currency_val = "INR" if "crore" in full_text or "million" in full_text or "₹" in full_text or "Rs" in full_text else None

    assets_val, assets_ev = _extract_number_near_label(lines, r'TOTAL\s+ASSETS\b')
    cap_liab_val, cap_liab_ev = _extract_number_near_label(lines, r'TOTAL\s+(?:CAPITAL\s+AND\s+LIABILITIES|EQUITY\s+AND\s+LIABILITIES)')
    equity_val, equity_ev = _extract_number_near_label(lines, r'TOTAL\s+EQUITY\b|SHAREHOLDERS\'?\s+FUNDS\b')
    liab_val, liab_ev = _extract_number_near_label(lines, r'TOTAL\s+LIABILITIES\b|NON-CURRENT\s+LIABILITIES\b')

    in_cap_liab, in_assets = False, False
    cap_val, res_val, min_val = None, None, None

    for line in lines:
        if re.search(r'CAPITAL\s+AND\s+LIABILITIES|EQUITY\s+AND\s+LIABILITIES', line, re.I):
            in_cap_liab, in_assets = True, False
            continue
        elif re.search(r'^\s*ASSETS\s*$', line, re.I) or line.strip() == 'ASSETS':
            in_assets, in_cap_liab = True, False
            continue
            
        nums = _extract_all_numbers(line)
        if in_cap_liab:
            if re.search(r'^\s*Capital\b', line, re.I) and cap_val is None and nums:
                cap_val = nums[0]
            if re.search(r'Reserves\s+and\s+surplus', line, re.I) and res_val is None and nums:
                res_val = nums[0]
            if re.search(r'Minority\s+interest', line, re.I) and min_val is None and nums:
                min_val = nums[0]

            if cap_liab_val is None and re.search(r'^\s*Total\b', line, re.I) and nums:
                cap_liab_val, cap_liab_ev = nums[0], line
                    
        if in_assets:
            if assets_val is None and re.search(r'^\s*Total\b', line, re.I) and nums:
                assets_val, assets_ev = nums[0], line

    if equity_val is None and cap_val is not None and res_val is not None:
        equity_val = round(cap_val + res_val + (min_val or 0.0), 2)
        equity_ev = "Capital + Reserves & Surplus"

    return {
        "statement_title": _field(title, 0.99, 1, title),
        "company_name": _field(company_name_val, 0.92, 1, company_name_ev),
        "period": _field(period_str, 0.95, 1, period_str),
        "currency": _field(currency_val, 0.98, 1, currency_val),
        "total_assets": _field(assets_val, 0.96, 1, assets_ev),
        "total_liabilities": _field(liab_val, 0.90, 1, liab_ev),
        "total_equity": _field(equity_val, 0.90, 1, equity_ev),
        "total_capital_and_liabilities": _field(cap_liab_val, 0.96, 1, cap_liab_ev),
        "periods": periods,
        "line_items": []
    }

# ============================================================
# PROFIT & LOSS EXTRACTION
# ============================================================
def _extract_profit_and_loss(text: str, pages: list[str]) -> dict:
    lines = _lines(text)
    full_text = "\n".join(lines)

    title = "CONSOLIDATED PROFIT AND LOSS STATEMENT" if "CONSOLIDATED" in full_text.upper() else "PROFIT AND LOSS STATEMENT"
    company_name_val, company_name_ev = _extract_company_name(lines)
    
    m_period = re.search(r'for\s+the\s+year\s+ended\s+([^\n]+)', full_text, re.IGNORECASE)
    period_str = m_period.group(0).strip() if m_period else "Current Period"

    currency_val = "INR" if "crore" in full_text or "million" in full_text or "₹" in full_text or "Rs" in full_text else None

    rev_val, rev_ev = _extract_number_near_label(lines, r'REVENUE\s+FROM\s+OPERATIONS|TOTAL\s+REVENUE|TOTAL\s+INCOME')
    cogs_val, cogs_ev = _extract_number_near_label(lines, r'COST\s+OF\s+(?:MATERIALS\s+CONSUMED|SALES|GOODS)|INTEREST\s+EXPENDED')
    gross_prof_val, gross_prof_ev = _extract_number_near_label(lines, r'GROSS\s+PROFIT')
    op_exp_val, op_exp_ev = _extract_number_near_label(lines, r'OPERATING\s+EXPENSES|OTHER\s+EXPENSES|TOTAL\s+EXPENSES')
    op_prof_val, op_prof_ev = _extract_number_near_label(lines, r'PROFIT\s+BEFORE\s+TAX|OPERATING\s+PROFIT')
    tax_val, tax_ev = _extract_number_near_label(lines, r'PROVISIONS\s+AND\s+CONTINGENCIES|PROVISION\s+FOR\s+TAX|CURRENT\s+TAX|TAX\s+EXPENSE')
    net_prof_val, net_prof_ev = _extract_number_near_label(lines, r'CONSOLIDATED\s+NET\s+PROFIT|PROFIT\s+FOR\s+THE\s+(?:YEAR|PERIOD)|NET\s+PROFIT')

    in_income, in_exp = False, False
    for line in lines:
        if re.search(r'^\s*INCOME\s*$', line, re.I) or line.strip() == 'INCOME':
            in_income, in_exp = True, False
            continue
        elif re.search(r'^\s*EXPENDITURE\s*$', line, re.I) or line.strip() == 'EXPENDITURE':
            in_exp, in_income = True, False
            continue

        nums = _extract_all_numbers(line)
        if in_income and rev_val is None and re.search(r'^\s*Total\b|Total\s+Income', line, re.I) and nums:
            rev_val, rev_ev = nums[0], line
        if in_exp and op_exp_val is None and re.search(r'Operating\s+expenses', line, re.I) and nums:
            op_exp_val, op_exp_ev = nums[0], line
        if in_exp and cogs_val is None and re.search(r'^\s*Total\b|Interest\s+expended', line, re.I) and nums:
            cogs_val, cogs_ev = nums[0], line
        if net_prof_val is None and re.search(r'Consolidated\s+Net\s+Profit|Profit\s+for\s+the\s+year', line, re.I) and nums:
            net_prof_val, net_prof_ev = nums[0], line

    return {
        "statement_title": _field(title, 0.99, 1, title),
        "company_name": _field(company_name_val, 0.92, 1, company_name_ev),
        "period": _field(period_str, 0.95, 1, period_str),
        "currency": _field(currency_val, 0.98, 1, currency_val),
        "revenue": _field(rev_val, 0.96, 1, rev_ev),
        "cost_of_sales": _field(cogs_val, 0.95, 1, cogs_ev),
        "gross_profit": _field(gross_prof_val, 0.95, 1, gross_prof_ev),
        "operating_expenses": _field(op_exp_val, 0.92, 1, op_exp_ev),
        "operating_profit": _field(op_prof_val, 0.92, 1, op_prof_ev),
        "tax": _field(tax_val, 0.90, 1, tax_ev),
        "net_profit": _field(net_prof_val, 0.96, 1, net_prof_ev),
        "line_items": []
    }

# ============================================================
# CASH FLOW STATEMENT EXTRACTION
# ============================================================
def _extract_cash_flow(text: str, pages: list[str]) -> dict:
    lines = _lines(text)
    full_text = "\n".join(lines)

    title = "CONSOLIDATED CASH FLOW STATEMENT" if "CONSOLIDATED" in full_text.upper() else "CASH FLOW STATEMENT"
    company_name_val, company_name_ev = _extract_company_name(lines)
    
    m_period = re.search(r'for\s+the\s+year\s+ended\s+([^\n]+)', full_text, re.IGNORECASE)
    period_str = m_period.group(0).strip() if m_period else "Current Period"

    currency_val = "INR" if "crore" in full_text or "million" in full_text or "₹" in full_text or "Rs" in full_text else "USD"

    op_cf_val, op_cf_ev = _extract_number_near_label(lines, r'NET\s+CASH\s+FLOWS?\s+(?:FROM|IN)\s+OPERATING|CASH\s+FLOWS?\s+FROM\s+OPERATING')
    inv_cf_val, inv_cf_ev = _extract_number_near_label(lines, r'NET\s+CASH\s+FLOW\s+(?:FROM|USED\s+IN)\s+INVESTING|CASH\s+FLOWS?\s+FROM\s+INVESTING')
    fin_cf_val, fin_cf_ev = _extract_number_near_label(lines, r'NET\s+CASH\s+FLOW\s+(?:FROM|USED\s+IN)\s+FINANCING|CASH\s+FLOWS?\s+FROM\s+FINANCING')
    net_change_val, net_change_ev = _extract_number_near_label(lines, r'NET\s+(?:INCREASE|DECREASE)\s+IN\s+CASH|NET\s+CASH\s+FLOW')
    opening_cash_val, opening_cash_ev = _extract_number_near_label(lines, r'BEGINNING\s+OF\s+(?:THE\s+)?YEAR|OPENING\s+CASH|APRIL\s+1ST')
    closing_cash_val, closing_cash_ev = _extract_number_near_label(lines, r'END\s+OF\s+(?:THE\s+)?YEAR|CLOSING\s+CASH|MARCH\s+31ST')

    for line in lines:
        nums = _extract_all_numbers(line)
        if not nums:
            continue
        if op_cf_val is None and re.search(r'Net\s+cash\s+flows?\s+(?:from|used\s+in)?\s*operating', line, re.I):
            op_cf_val, op_cf_ev = nums[0], line
        elif inv_cf_val is None and re.search(r'Net\s+cash\s+flow\s+(?:from|used\s+in)?\s*investing', line, re.I):
            inv_cf_val, inv_cf_ev = nums[0], line
        elif fin_cf_val is None and re.search(r'Net\s+cash\s+flow\s+(?:from|used\s+in)?\s*financing', line, re.I):
            fin_cf_val, fin_cf_ev = nums[0], line
        elif net_change_val is None and re.search(r'Net\s+(?:increase|decrease)\s+in\s+cash', line, re.I):
            net_change_val, net_change_ev = nums[0], line
        elif opening_cash_val is None and re.search(r'beginning\s+of\s+the\s+year|April\s+1st', line, re.I):
            opening_cash_val, opening_cash_ev = nums[0], line
        elif closing_cash_val is None and re.search(r'end\s+of\s+the\s+year|March\s+31st', line, re.I):
            closing_cash_val, closing_cash_ev = nums[0], line

    return {
        "statement_title": _field(title, 0.99, 1, title),
        "company_name": _field(company_name_val, 0.92, 1, company_name_ev),
        "period": _field(period_str, 0.95, 1, period_str),
        "currency": _field(currency_val, 0.98, 1, currency_val),
        "operating_cash_flow": _field(op_cf_val, 0.95, 1, op_cf_ev),
        "investing_cash_flow": _field(inv_cf_val, 0.90, 1, inv_cf_ev),
        "financing_cash_flow": _field(fin_cf_val, 0.90, 1, fin_cf_ev),
        "opening_cash": _field(opening_cash_val, 0.90, 1, opening_cash_ev),
        "net_change_in_cash": _field(net_change_val, 0.95, 1, net_change_ev),
        "closing_cash": _field(closing_cash_val, 0.90, 1, closing_cash_ev),
        "line_items": []
    }

# ============================================================
# PUBLIC ENTRYPOINT
# ============================================================
def extract_document(document_type: str, text: str, pages: list[str]) -> dict:
    doc_type = document_type.lower().strip().replace(" ", "_")
    if doc_type in ["invoice", "invoices"]:
        result = _extract_invoice(text, pages)
    elif doc_type in ["balance_sheet", "balance_sheets"]:
        result = _extract_balance_sheet(text, pages)
    elif doc_type in ["profit_and_loss", "profit_and_losses", "profit_loss", "profit_&_loss"]:
        result = _extract_profit_and_loss(text, pages)
    elif doc_type in ["cash_flow", "cash_flows", "cash_flow_statement", "cash_flow_statements"]:
        result = _extract_cash_flow(text, pages)
    else:
        result = _extract_invoice(text, pages)

    # Preserve the complete OCR/native text so fields not covered by the typed
    # schema remain traceable instead of being silently discarded.
    result["raw_text"] = text
    result["page_texts"] = pages
    return result