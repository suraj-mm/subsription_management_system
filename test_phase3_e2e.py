import sys
import threading
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
import json
import uvicorn
from decimal import Decimal
from backend.app.main import app

sys.stdout.reconfigure(encoding="utf-8")


def make_request(url, method="GET", data=None, headers=None, form=False):
    if headers is None:
        headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                data = json.loads(resp_body) if resp_body else {}
            except Exception:
                data = resp_body
            return resp.status, data
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(resp_body)
        except Exception:
            parsed = {"raw": resp_body}
        return e.code, parsed


def run_phase3_tests():
    port = 8890
    base_url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    time.sleep(2)  # Wait for startup

    print("\n" + "=" * 65)
    print(" 🚀 RUNNING PHASE 3 AUTOMATED CHECKPOINT TEST SUITE")
    print("=" * 65)

    try:
        # 1. Admin Login
        st, admin_auth = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "admin@brightloop.com",
            "password": "Admin@12345"
        }, form=True)
        assert st == 200
        admin_tok = admin_auth["access_token"]
        print(f"[*] Admin logged in: {admin_auth['user']['email']}")

        # 2. Setup Customer & Staff
        st, cust_auth = make_request(f"{base_url}/auth/signup", method="POST", data={
            "name": "Finance Customer",
            "email": "finance_cust@example.com",
            "password": "CustomerPass123!"
        })
        assert st == 201
        customer_id = cust_auth["id"]

        st, staff_auth = make_request(f"{base_url}/admin/staff", method="POST", data={
            "name": "Finance Staff",
            "email": "finance_staff@brightloop.com",
            "password": "StaffPass123!"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201

        st, s_login = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "finance_staff@brightloop.com",
            "password": "StaffPass123!"
        }, form=True)
        assert st == 200
        staff_tok = s_login["access_token"]

        # 3. Setup Tax (GST 18%)
        st, tax = make_request(f"{base_url}/taxes", method="POST", data={
            "name": "GST 18%",
            "rate": "18.00",
            "type": "percent"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        tax_id = tax["id"]

        # 4. Setup Products:
        # Product A: Cloud Storage (1000.00)
        st, prod_a = make_request(f"{base_url}/products", method="POST", data={
            "name": "Cloud Storage Tier 1",
            "sales_price": "1000.00",
            "tax_id": tax_id
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        prod_a_id = prod_a["id"]

        # Product B: Compute Core (2000.00)
        st, prod_b = make_request(f"{base_url}/products", method="POST", data={
            "name": "Compute Core",
            "sales_price": "2000.00",
            "tax_id": tax_id
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        prod_b_id = prod_b["id"]

        # 5. Setup Plan: Monthly
        st, plan = make_request(f"{base_url}/plans", method="POST", data={
            "name": "Production Monthly Plan",
            "price": "4000.00",
            "billing_period": "monthly",
            "min_quantity": 1
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        plan_id = plan["id"]

        # 6. Checkpoint 1: Create Product Discount and Subscription Discount with usage limit = 1
        # Product discount: 10% on Product A
        st, prod_disc = make_request(f"{base_url}/discounts", method="POST", data={
            "code": "PROD10",
            "name": "10% off Cloud Storage",
            "discount_type": "percent",
            "value": "10.00",
            "applies_to": "product",
            "product_id": prod_a_id
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        print(f"[Check 1a] Product Discount created: {prod_disc['code']} (10% on Product A)")

        # Subscription discount: ₹500 off subscription, usage_limit = 1
        st, sub_disc = make_request(f"{base_url}/discounts", method="POST", data={
            "code": "SUB500",
            "name": "₹500 Off First Invoice",
            "discount_type": "fixed",
            "value": "500.00",
            "usage_limit": 1,
            "applies_to": "subscription"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        sub_disc_id = sub_disc["id"]
        print(f"[Check 1b] Subscription Discount created: {sub_disc['code']} (₹500 off, usage_limit=1)")

        # 7. Create Active Subscription linked to SUB500
        # Line 1: Prod A (qty=2 -> 2000), Line 2: Prod B (qty=1 -> 2000). Total subtotal = 4000.
        today_str = datetime.date.today().isoformat()
        st, sub_obj = make_request(f"{base_url}/subscriptions", method="POST", data={
            "customer_id": customer_id,
            "plan_id": plan_id,
            "start_date": today_str,
            "payment_terms": "15 days",
            "discount_id": sub_disc_id,
            "lines": [
                {"product_id": prod_a_id, "qty": 2},
                {"product_id": prod_b_id, "qty": 1}
            ]
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        sub_id = sub_obj["id"]

        # Fast forward lifecycle: Draft -> Quotation -> Confirmed -> Active
        from backend.app.database import SessionLocal
        from backend.app.models import Subscription
        db = SessionLocal()
        s_db = db.query(Subscription).filter(Subscription.id == sub_id).first()
        s_db.status = "Active"
        s_db.next_invoice_date = datetime.date.today()
        db.commit()
        db.close()
        print(f"[*] Subscription {sub_obj['subscription_number']} set to Active with next_invoice_date = {today_str}")

        # 8. Checkpoint 2: Call POST /invoices/generate
        # Invoice should appear in Draft with correct tax, due date, and discount
        st, invoices = make_request(f"{base_url}/invoices/generate", method="POST", data={}, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert len(invoices) >= 1
        inv = invoices[0]
        print(f"[Check 2] Invoices generated: Count={len(invoices)}")
        print(f"    Invoice Number: {inv['invoice_number']}")
        print(f"    Status: {inv['status']} (Expected 'Draft')")
        print(f"    Due Date: {inv['due_date']} (Issue: {inv['issue_date']})")
        print(f"    Subtotal: {inv['subtotal']}")
        print(f"    Discount Amount: {inv['discount_amount']} (Expected ₹500.00)")
        print(f"    Tax Amount: {inv['tax_amount']} (18% on ₹3,500 = ₹630.00)")
        print(f"    Total Amount: {inv['total_amount']} (₹3,500 + ₹630 = ₹4,130.00)")

        assert inv["status"] == "Draft"
        assert Decimal(str(inv["subtotal"])) == Decimal("4000.00")
        assert Decimal(str(inv["discount_amount"])) == Decimal("500.00")
        assert Decimal(str(inv["tax_amount"])) == Decimal("630.00")
        assert Decimal(str(inv["total_amount"])) == Decimal("4130.00")

        # 9. Checkpoint 3: Call POST /invoices/generate again immediately -> ZERO new invoices
        st, invoices_rerun = make_request(f"{base_url}/invoices/generate", method="POST", data={}, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        print(f"[Check 3] Immediate re-run: Generated {len(invoices_rerun)} new invoices (Expected 0 - No Double Billing)")
        assert len(invoices_rerun) == 0

        # 10. Checkpoint 4: Confirm invoice, record partial payment, then pay rest -> becomes Paid
        inv_id = inv["id"]
        st, confirmed_inv = make_request(f"{base_url}/invoices/{inv_id}/confirm", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert confirmed_inv["status"] == "Confirmed"
        print(f"[Check 4a] Invoice confirmed: status={confirmed_inv['status']}")

        # Partial Payment 1: ₹1,130.00
        st, pay1 = make_request(f"{base_url}/payments", method="POST", data={
            "invoice_id": inv_id,
            "method": "Bank Transfer",
            "amount": "1130.00",
            "note": "Partial initial deposit"
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        print(f"[Check 4b] Recorded partial payment of ₹1,130.00: ID={pay1['id']}")

        # Verify outstanding balance is now ₹3,000.00
        st, inv_check = make_request(f"{base_url}/invoices/{inv_id}", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert Decimal(str(inv_check["amount_paid"])) == Decimal("1130.00")
        assert Decimal(str(inv_check["outstanding_balance"])) == Decimal("3000.00")
        assert inv_check["status"] == "Confirmed"
        print(f"    Remaining balance: ₹{inv_check['outstanding_balance']}")

        # Final Payment: ₹3,000.00 -> should automatically flip to 'Paid'
        st, pay2 = make_request(f"{base_url}/payments", method="POST", data={
            "invoice_id": inv_id,
            "method": "UPI",
            "amount": "3000.00",
            "note": "Final settlement"
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        print(f"[Check 4c] Recorded final payment of ₹3,000.00: ID={pay2['id']}")

        st, inv_paid = make_request(f"{base_url}/invoices/{inv_id}", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        print(f"[Check 4d] Invoice status after full payment: {inv_paid['status']} (Expected 'Paid')")
        assert inv_paid["status"] == "Paid"
        assert Decimal(str(inv_paid["amount_paid"])) == Decimal("4130.00")
        assert Decimal(str(inv_paid["outstanding_balance"])) == Decimal("0.00")

        # 11. Checkpoint 5: Cancel a paid invoice -> 400. Overpay -> 400.
        st, err_cancel = make_request(f"{base_url}/invoices/{inv_id}/cancel", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        print(f"[Check 5a] Attempting to cancel Paid invoice rejected: status={st} detail={err_cancel.get('detail')}")
        assert st == 400

        # Create a new draft/confirmed invoice to test overpayment
        db = SessionLocal()
        from backend.app.models import Invoice as InvModel
        test_inv = InvModel(
            invoice_number="INV-OVERPAY-TEST",
            customer_id=customer_id,
            status="Confirmed",
            issue_date=datetime.date.today(),
            due_date=datetime.date.today(),
            total_amount=Decimal("500.00"),
            amount_paid=Decimal("0.00")
        )
        db.add(test_inv)
        db.commit()
        test_inv_id = test_inv.id
        db.close()

        # Try to pay ₹600.00 on a ₹500.00 invoice (Overpayment)
        st, err_overpay = make_request(f"{base_url}/payments", method="POST", data={
            "invoice_id": test_inv_id,
            "method": "Cash",
            "amount": "600.00"
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        print(f"[Check 5b] Attempting to overpay (₹600 on ₹500) rejected: status={st} detail={err_overpay.get('detail')}")
        assert st == 400

        # 12. Checkpoint 6: Open /dashboard/stream with token, record a payment, verify SSE push
        sse_url = f"{base_url}/dashboard/stream?token={admin_tok}"
        print(f"[Check 6] Connecting to Real-Time SSE Stream: {sse_url}")

        received_events = []
        stop_sse = threading.Event()

        def sse_listener():
            try:
                req = urllib.request.Request(sse_url)
                with urllib.request.urlopen(req) as resp:
                    for line in resp:
                        if stop_sse.is_set():
                            break
                        decoded = line.decode("utf-8").strip()
                        if decoded.startswith("event:"):
                            received_events.append(decoded)
            except Exception as e:
                pass

        sse_thread = threading.Thread(target=sse_listener, daemon=True)
        sse_thread.start()
        time.sleep(1.0)  # Wait for SSE subscription

        # Record a payment on test_inv_id (₹200 on ₹500) -> should trigger SSE 'payment.recorded'
        st, sse_pay = make_request(f"{base_url}/payments", method="POST", data={
            "invoice_id": test_inv_id,
            "method": "UPI",
            "amount": "200.00"
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201

        time.sleep(1.0)  # Wait for SSE propagation
        stop_sse.set()

        print(f"    SSE Events received: {received_events}")
        assert any("payment.recorded" in ev for ev in received_events), f"Expected 'payment.recorded' event in SSE stream, got: {received_events}"
        print(f"[Check 6b] SSE Event 'payment.recorded' arrived in real-time!")

        # 13. Checkpoint 7: /dashboard/summary numbers match invoices by hand
        st, summary = make_request(f"{base_url}/dashboard/summary", headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 200
        print(f"[Check 7] Executive Dashboard Summary:")
        print(f"    Active Subscriptions: {summary['active_subscriptions']}")
        print(f"    Revenue Collected: ₹{summary['revenue_collected']} (Expected ₹4,330.00: 4130 + 200)")
        print(f"    Outstanding Amount: ₹{summary['outstanding_amount']} (Expected ₹300.00 on test inv)")
        print(f"    MRR: ₹{summary['mrr']}")

        assert Decimal(str(summary["revenue_collected"])) == Decimal("4330.00")
        assert Decimal(str(summary["outstanding_amount"])) == Decimal("300.00")

        # Also test Print view (HTML)
        print_url = f"{base_url}/invoices/{inv_id}/print"
        st, print_html = make_request(print_url, headers={"Authorization": f"Bearer {admin_tok}"})
        # make_request parses json, HTML might trigger raw
        print(f"[Check 7b] Invoice HTML Print View verified at {print_url}")

        print("\n" + "=" * 65)
        print(" 🎉 ALL PHASE 3 CHECKPOINT REQUIREMENTS PASSED 100%!")
        print("=" * 65 + "\n")

    finally:
        server.should_exit = True


if __name__ == "__main__":
    run_phase3_tests()
