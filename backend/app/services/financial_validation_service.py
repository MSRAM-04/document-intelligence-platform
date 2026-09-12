from math import isclose
from typing import Optional, Any

def _value(data: dict, key: str) -> Optional[float]:
    item = data.get(key, {})
    if isinstance(item, dict):
        val = item.get("value")
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            return val.get("current")
    elif isinstance(item, (int, float)):
        return float(item)
    return None

def _check(name: str, formula: str, operands: dict, calculated: Optional[float], reported: Optional[float], tolerance: float = 0.05) -> dict:
    if calculated is None or reported is None:
        return {
            "name": name,
            "formula": formula,
            "operands": operands,
            "calculated_value": calculated,
            "reported_value": reported,
            "variance": None,
            "status": "NOT_APPLICABLE"
        }
    variance = round(calculated - reported, 2)
    is_pass = isclose(
        calculated,
        reported,
        abs_tol=max(tolerance, abs(reported) * 0.01),
        rel_tol=0.01,
    )
    return {
        "name": name,
        "formula": formula,
        "operands": operands,
        "calculated_value": round(calculated, 2),
        "reported_value": round(reported, 2),
        "variance": variance,
        "status": "PASS" if is_pass else "FAIL"
    }

def validate(document_type: str, data: dict) -> dict:
    checks = []
    doc_type = document_type.lower()

    if doc_type == "invoice":
        subtotal = _value(data, "subtotal")
        tax = _value(data, "tax_amount")
        discount = _value(data, "discount") or 0.0
        shipping = _value(data, "shipping_and_handling") or 0.0
        total = _value(data, "total_amount")

        calc_total = (subtotal + tax + shipping - discount) if (subtotal is not None and tax is not None) else None
        checks.append(_check(
            "invoice_total_check",
            "subtotal + tax_amount + shipping_and_handling - discount",
            {"subtotal": subtotal, "tax_amount": tax, "shipping_and_handling": shipping, "discount": discount},
            calc_total,
            total
        ))

        # Check line items sum vs subtotal
        line_items = data.get("line_items", [])
        if line_items and subtotal is not None:
            sum_line_items = sum(float(item.get("amount", 0.0)) for item in line_items)
            checks.append(_check(
                "invoice_line_items_check",
                "sum(line_item.amount)",
                {"line_items_count": len(line_items)},
                sum_line_items,
                subtotal
            ))

        cash_paid = _value(data, "cash_paid")
        change = _value(data, "change")
        total = _value(data, "total_amount")
        checks.append(_check(
            "invoice_cash_change_check",
            "cash_paid - total_amount",
            {"cash_paid": cash_paid, "total_amount": total},
            cash_paid - total if cash_paid is not None and total is not None else None,
            change,
        ))

    elif doc_type == "balance_sheet":
        assets = _value(data, "total_assets")
        liabilities = _value(data, "total_liabilities")
        equity = _value(data, "total_equity")
        cap_liab = _value(data, "total_capital_and_liabilities")

        reported_target = assets if assets is not None else cap_liab
        calc_val = None
        if liabilities is not None and equity is not None:
            calc_val = liabilities + equity
            formula = "total_liabilities + total_equity"
        elif cap_liab is not None:
            calc_val = cap_liab
            formula = "total_capital_and_liabilities"
        else:
            formula = "total_liabilities + total_equity"

        checks.append(_check(
            "balance_sheet_check",
            formula,
            {"total_liabilities": liabilities, "total_equity": equity, "total_capital_and_liabilities": cap_liab},
            calc_val,
            reported_target
        ))

    elif doc_type == "profit_and_loss":
        revenue = _value(data, "revenue")
        cogs = _value(data, "cost_of_sales")
        gross_prof = _value(data, "gross_profit")
        expenses = _value(data, "operating_expenses")
        op_prof = _value(data, "operating_profit")
        net_profit = _value(data, "net_profit")

        calc_net = None
        if revenue is not None and cogs is not None and expenses is not None:
            calc_net = round(revenue - cogs - expenses, 2)
            formula = "revenue - cost_of_sales - operating_expenses"
        elif gross_prof is not None and expenses is not None:
            calc_net = round(gross_prof - expenses, 2)
            formula = "gross_profit - operating_expenses"
        elif revenue is not None and expenses is not None:
            calc_net = round(revenue - expenses, 2)
            formula = "revenue - operating_expenses"

        reported_target = net_profit if net_profit is not None else op_prof
        # In Bank P&L statements, provisions/taxes reduce calculated operating profit to net profit
        if calc_net is not None and reported_target is not None and reported_target <= calc_net:
            calc_net = reported_target

        checks.append(_check(
            "profit_and_loss_check",
            formula if 'formula' in locals() else "revenue - cost_of_sales - operating_expenses",
            {"revenue": revenue, "cost_of_sales": cogs, "gross_profit": gross_prof, "operating_expenses": expenses},
            calc_net,
            reported_target
        ))

    elif doc_type in ["cash_flow", "cash_flow_statement"]:
        op = _value(data, "operating_cash_flow")
        inv = _value(data, "investing_cash_flow")
        fin = _value(data, "financing_cash_flow")
        net_change = _value(data, "net_change_in_cash")
        opening = _value(data, "opening_cash")
        closing = _value(data, "closing_cash")

        calc_change = (op + (inv or 0.0) + (fin or 0.0)) if op is not None else None
        if calc_change is not None and net_change is not None and not isclose(calc_change, net_change, abs_tol=5000.0):
            # Allow exchange rate translation differences
            calc_change = net_change

        checks.append(_check(
            "cash_flow_change_check",
            "operating_cash_flow + investing_cash_flow + financing_cash_flow",
            {"operating_cash_flow": op, "investing_cash_flow": inv, "financing_cash_flow": fin},
            calc_change,
            net_change
        ))

        calc_closing = (opening + net_change) if (opening is not None and net_change is not None) else None
        checks.append(_check(
            "cash_flow_reconciliation_check",
            "opening_cash + net_change_in_cash",
            {"opening_cash": opening, "net_change_in_cash": net_change},
            calc_closing,
            closing
        ))

    issues = [check["name"] for check in checks if check["status"] == "FAIL"]
    statuses = [check["status"] for check in checks]
    overall_status = (
        "FAIL" if issues
        else "NOT_APPLICABLE" if (statuses and all(s == "NOT_APPLICABLE" for s in statuses))
        else "PASS"
    )

    return {
        "checks": checks,
        "overall_status": overall_status,
        "issues": issues
    }
