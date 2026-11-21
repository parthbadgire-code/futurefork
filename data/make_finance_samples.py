"""
FutureFork: Financial Sample Datasets Generator
Member 1: Data Ingestion & Baseline Compiler

Generates 3 realistic 12-month Indian financial CSVs + 1 pre-parsed JSON fixture:
1. data/samples/personal_upi.csv (Individual - Bank / UPI Statement)
2. data/samples/institute_erp_1.8cr.csv (Institute - College ERP Expense Ledger, ~1.8 Cr budget)
3. data/samples/startup_pnl.csv (Startup - Company P&L / Burn CSV)
4. data/samples/fixture_institute_node0.json (Pre-parsed Node 0 baseline fixture)
"""

from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure data/samples directory exists
DATA_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = DATA_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def format_inr(amount: float, symbol: bool = False, commas: bool = True) -> str:
    """Format float into Indian Rupee representation (e.g. ₹ 1,50,000.00)."""
    if commas:
        s = f"{amount:.2f}"
        parts = s.split(".")
        integer_part = parts[0]
        decimal_part = parts[1]

        if len(integer_part) > 3:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            # Group by 2 digits from the right
            grouped = []
            while len(remaining) > 2:
                grouped.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                grouped.insert(0, remaining)
            formatted_int = ",".join(grouped) + "," + last_three
        else:
            formatted_int = integer_part
        res = f"{formatted_int}.{decimal_part}"
    else:
        res = f"{amount:.2f}"

    if symbol:
        return f"₹ {res}"
    return res


# ==============================================================================
# 1. PERSONAL UPI / BANK STATEMENT GENERATOR
# ==============================================================================
def generate_personal_upi_csv(output_path: Path, seed: int = 42) -> Path:
    """
    Generates 12 months of realistic Indian personal UPI / Bank transactions.
    Features salary inflow, rent, EMIs, utilities, food/Swiggy, cabs, shopping.
    Includes mixed messy formatting (DD/MM/YYYY vs DD-MM-YYYY, ₹ symbols, empty fields).
    """
    random.seed(seed)
    np.random.seed(seed)

    rows: List[Dict[str, str]] = []
    current_balance = 150000.0  # Starting balance ₹1,50,000

    for month_idx in range(12):
        # Month anchor
        # Calculate year and month
        y = 2024 + (4 + month_idx - 1) // 12
        m = (4 + month_idx - 1) % 12 + 1

        # 1. Monthly Salary (Last day of month or 30th)
        salary_date = datetime(y, m, 28)
        salary_amt = 145000.0 + random.choice([0.0, 2500.0, -1500.0])
        current_balance += salary_amt
        rows.append({
            "Date": salary_date.strftime("%d/%m/%Y"),
            "Narration": f"SALARY/INFOSYS LTD/NEFT/SAL-{m:02d}{y}",
            "Category": "Income / Salary",
            "Debit": "",
            "Credit": f"₹ {format_inr(salary_amt)}",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

        # 2. Occasional Inflow (Freelance / IT Refund / Bonus)
        if month_idx == 3:  # July: Tax Refund
            ref_amt = 24500.0
            current_balance += ref_amt
            rows.append({
                "Date": datetime(y, m, 18).strftime("%d-%m-%Y"),
                "Narration": "REFUND/INCOME TAX DEPT/AY2024-25",
                "Category": "Income / Refund",
                "Debit": "",
                "Credit": f"{format_inr(ref_amt)}",
                "Balance": f"₹ {format_inr(current_balance)}",
            })
        elif month_idx == 6:  # October: Festival Bonus
            bon_amt = 50000.0
            current_balance += bon_amt
            rows.append({
                "Date": datetime(y, m, 22).strftime("%d/%m/%Y"),
                "Narration": "BONUS/INFOSYS LTD/DIWALI SPECIAL",
                "Category": "Income / Bonus",
                "Debit": "",
                "Credit": f"₹ {format_inr(bon_amt)}",
                "Balance": f"₹ {format_inr(current_balance)}",
            })
        elif month_idx == 9:  # January: Freelance UI Consultation
            fl_amt = 35000.0
            current_balance += fl_amt
            rows.append({
                "Date": datetime(y, m, 15).strftime("%d-%m-%Y"),
                "Narration": "UPI/9845012345/Upwork Consulting Payout",
                "Category": "Income / Freelance",
                "Debit": "",
                "Credit": f"₹ {format_inr(fl_amt)}",
                "Balance": f"₹ {format_inr(current_balance)}",
            })

        # 3. Rent Outflow (Fixed: 5th of every month)
        rent_date = datetime(y, m, 5)
        rent_amt = 35000.0
        current_balance -= rent_amt
        rows.append({
            "Date": rent_date.strftime("%d/%m/%Y" if month_idx % 2 == 0 else "%d-%m-%Y"),
            "Narration": "UPI/Transfer/Rent to Mr. Ramesh Sharma",
            "Category": "Rent & Housing",
            "Debit": f"₹ {format_inr(rent_amt)}",
            "Credit": "",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

        # 4. Home / Car Loan EMI (Fixed: 10th of every month)
        emi_date = datetime(y, m, 10)
        emi_amt = 22500.0
        current_balance -= emi_amt
        rows.append({
            "Date": emi_date.strftime("%d/%m/%Y"),
            "Narration": "ACH/HDFC BANK/LOAN-EMI-409128",
            "Category": "Loan & EMI",
            "Debit": f"{format_inr(emi_amt)}",
            "Credit": "",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

        # 5. Utilities & Electricity & Broadband
        util_date_1 = datetime(y, m, 7)
        elec_amt = random.uniform(3200.0, 5800.0)
        current_balance -= elec_amt
        rows.append({
            "Date": util_date_1.strftime("%d-%m-%Y"),
            "Narration": "UPI/BESCOM/Electricity Bill Bangalore",
            "Category": "Utilities & Bills",
            "Debit": f"₹ {format_inr(elec_amt)}",
            "Credit": "",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

        util_date_2 = datetime(y, m, 12)
        bb_amt = 1415.0  # ACT Broadband Fibernet
        current_balance -= bb_amt
        rows.append({
            "Date": util_date_2.strftime("%d/%m/%Y"),
            "Narration": "UPI/ACT Broadband/Monthly Plan 150Mbps",
            "Category": "Utilities & Bills",
            "Debit": f"{format_inr(bb_amt)}",
            "Credit": "",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

        # 6. Groceries & Quick Commerce (Blinkit, Zepto, Supermarket)
        num_groceries = random.randint(3, 5)
        for g_i in range(num_groceries):
            day = min(27, 2 + g_i * 6 + random.randint(0, 2))
            g_amt = random.uniform(2200.0, 4800.0)
            current_balance -= g_amt
            vendor = random.choice(["Blinkit Bengaluru", "Zepto Quick", "Nature Basket Indiranagar", "DMart Ready"])
            rows.append({
                "Date": datetime(y, m, day).strftime("%d/%m/%Y"),
                "Narration": f"UPI/Payment to {vendor}",
                "Category": "Groceries & Supermarket",
                "Debit": f"₹ {format_inr(g_amt)}",
                "Credit": "",
                "Balance": f"₹ {format_inr(current_balance)}",
            })

        # 7. Food & Dining (Swiggy / Zomato / Cafes)
        num_food = random.randint(4, 7)
        for f_i in range(num_food):
            day = min(27, 1 + f_i * 4 + random.randint(0, 2))
            f_amt = random.uniform(450.0, 1850.0)
            current_balance -= f_amt
            vendor = random.choice(["Swiggy Bangalore", "Zomato Online", "Third Wave Coffee Koramangala", "Toit Brewpub"])
            rows.append({
                "Date": datetime(y, m, day).strftime("%d-%m-%Y" if f_i % 2 == 0 else "%d/%m/%Y"),
                "Narration": f"UPI/{vendor}/Order Ref #{random.randint(10000, 99999)}",
                "Category": "Food & Dining",
                "Debit": f"{format_inr(f_amt)}",
                "Credit": "",
                "Balance": f"₹ {format_inr(current_balance)}",
            })

        # 8. Cab & Commute (Uber, Ola, Metro, Fuel)
        num_cabs = random.randint(3, 6)
        for c_i in range(num_cabs):
            day = min(27, 3 + c_i * 5)
            c_amt = random.uniform(320.0, 1250.0)
            current_balance -= c_amt
            vendor = random.choice(["Uber India Systems", "Ola Cabs Mobility", "Shell Petrol Pump Whitefield"])
            rows.append({
                "Date": datetime(y, m, day).strftime("%d/%m/%Y"),
                "Narration": f"UPI/{vendor}/Trip Payment",
                "Category": "Travel & Commute",
                "Debit": f"₹ {format_inr(c_amt)}",
                "Credit": "",
                "Balance": f"₹ {format_inr(current_balance)}",
            })

        # 9. Shopping & Entertainment (Amazon, Flipkart, BookMyShow)
        num_shop = random.randint(1, 3)
        for s_i in range(num_shop):
            day = min(27, 4 + s_i * 8)
            # Spikes during festive month (October)
            if month_idx == 6:
                s_amt = random.uniform(8000.0, 22000.0)
            else:
                s_amt = random.uniform(1200.0, 6500.0)
            current_balance -= s_amt
            vendor = random.choice(["Amazon Pay India", "Flipkart Internet", "BookMyShow Movies", "Zara Phoenix Mall"])
            rows.append({
                "Date": datetime(y, m, day).strftime("%d-%m-%Y"),
                "Narration": f"UPI/{vendor}/E-Commerce Order",
                "Category": "Shopping & Lifestyle",
                "Debit": f"₹ {format_inr(s_amt)}",
                "Credit": "",
                "Balance": f"₹ {format_inr(current_balance)}",
            })

        # 10. Healthcare & Miscellaneous
        med_amt = random.uniform(850.0, 3400.0)
        current_balance -= med_amt
        rows.append({
            "Date": datetime(y, m, min(27, 14)).strftime("%d/%m/%Y"),
            "Narration": "UPI/Apollo Pharmacy/Medicines",
            "Category": "Healthcare & Wellness",
            "Debit": f"{format_inr(med_amt)}",
            "Credit": "",
            "Balance": f"₹ {format_inr(current_balance)}",
        })

    # Sort chronologically by parsed date
    def get_sort_key(r: Dict[str, str]) -> datetime:
        d_str = r["Date"]
        fmt = "%d/%m/%Y" if "/" in d_str else "%d-%m-%Y"
        return datetime.strptime(d_str, fmt)

    rows.sort(key=get_sort_key)

    # Write CSV with utf-8-sig encoding
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["Date", "Narration", "Category", "Debit", "Credit", "Balance"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# ==============================================================================
# 2. INSTITUTE ERP LEDGER GENERATOR (~₹1.8 Cr Annual Budget)
# ==============================================================================
def generate_institute_erp_csv(output_path: Path, seed: int = 108) -> Path:
    """
    Generates 12 months of college ERP financial ledger vouchers for an engineering institute.
    Budget: ~₹1.80 Crore annually (~₹15 Lakhs/month average spend).
    Inflows: Semester tuition fees, research grants, alumni endowment.
    Outflows: 8 distinct expense heads (Salaries, Utilities, Lab Consumables, Fests, Travel, etc.).
    """
    random.seed(seed)
    np.random.seed(seed)

    rows: List[Dict[str, str]] = []
    voucher_counter = 1001

    # Inflow calendar (Tuition cycles & grants)
    # Months 0..11 corresponding to Apr 2024 .. Mar 2025
    inflows_calendar = {
        2: [("DST SERB Research Grant Phase-1", "Dean R&D", 1800000.0)],                  # June
        3: [("Odd Semester Tuition Fees (Batch 2021-25)", "Finance Office", 5200000.0)],   # July
        4: [("Freshers Admission & Laboratory Fees", "Admissions Cell", 3800000.0)],       # August
        6: [("Apex Alumni Endowment Fund Contribution", "Alumni Cell", 1500000.0)],        # October
        7: [("AICTE Modernization Grant (Lab Upgradation)", "Dean Academics", 1200000.0)], # November
        8: [("Even Semester Tuition Fees Collection", "Finance Office", 4800000.0)],       # December
        9: [("Late Fee & Semester Registration Installments", "Accounts Cell", 3200000.0)],# January
    }

    departments = ["Computer Science", "Electronics & Comm", "Mechanical Engg", "Administration", "Dean Academics", "Library & Information"]

    for month_idx in range(12):
        y = 2024 + (4 + month_idx - 1) // 12
        m = (4 + month_idx - 1) % 12 + 1

        # 1. Post Inflows for this month
        if month_idx in inflows_calendar:
            for desc, dept, amt in inflows_calendar[month_idx]:
                v_no = f"VCHR-{y}-{voucher_counter}"
                voucher_counter += 1
                rows.append({
                    "Voucher_No": v_no,
                    "Date": datetime(y, m, random.randint(10, 20)).strftime("%d/%m/%Y"),
                    "Account_Head": "Tuition & Grant Inflow",
                    "Department": dept,
                    "Narration": desc,
                    "Debit": "",
                    "Credit": f"₹ {format_inr(amt)}",
                })

        # 2. Outflow Head 1: Faculty & Staff Salaries (Fixed ~₹8.8L to ₹9.4L/mo)
        # Split into Teaching Faculty and Non-Teaching Staff
        fac_sal = random.uniform(620000.0, 660000.0)
        staff_sal = random.uniform(240000.0, 260000.0)

        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 28).strftime("%d/%m/%Y"),
            "Account_Head": "Faculty & Staff Payroll",
            "Department": "Human Resources",
            "Narration": f"Monthly Faculty Salary Disbursement - Month {m:02d}/{y}",
            "Debit": f"₹ {format_inr(fac_sal)}",
            "Credit": "",
        })

        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 28).strftime("%d/%m/%Y"),
            "Account_Head": "Faculty & Staff Payroll",
            "Department": "Human Resources",
            "Narration": f"Technical & Non-Teaching Staff Payroll - {m:02d}/{y}",
            "Debit": f"₹ {format_inr(staff_sal)}",
            "Credit": "",
        })

        # 3. Outflow Head 2: Campus Utilities & Electricity (Fixed ~₹1.6L to ₹2.2L/mo)
        elec_bill = random.uniform(130000.0, 185000.0)
        water_net = random.uniform(28000.0, 42000.0)

        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 8).strftime("%d/%m/%Y"),
            "Account_Head": "Campus Utilities & Electricity",
            "Department": "Estate & Maintenance",
            "Narration": "State Electricity Board HT Commercial Tariff Bill",
            "Debit": f"₹ {format_inr(elec_bill)}",
            "Credit": "",
        })

        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 12).strftime("%d/%m/%Y"),
            "Account_Head": "Campus Utilities & Electricity",
            "Department": "Estate & Maintenance",
            "Narration": "Campus Water Supply & Dedicated Leased Line Internet",
            "Debit": f"₹ {format_inr(water_net)}",
            "Credit": "",
        })

        # 4. Outflow Head 3: Lab Equipment & Consumables (Flexible ~₹90K to ₹1.8L/mo)
        num_lab_bills = random.randint(1, 3)
        for _ in range(num_lab_bills):
            lab_amt = random.uniform(35000.0, 75000.0)
            d = random.choice(departments[:3])
            v_no = f"VCHR-{y}-{voucher_counter}"
            voucher_counter += 1
            rows.append({
                "Voucher_No": v_no,
                "Date": datetime(y, m, random.randint(5, 25)).strftime("%d/%m/%Y"),
                "Account_Head": "Lab Equipment & Consumables",
                "Department": d,
                "Narration": f"Purchase of VLSI/IoT test kits, sensors, and electronic components for {d} Lab",
                "Debit": f"₹ {format_inr(lab_amt)}",
                "Credit": "",
            })

        # 5. Outflow Head 4: Student Cultural & Tech Fests (Flexible, highly seasonal)
        # Spikes in October (TechFest) and February (Annual Cultural Fest)
        if month_idx == 6:  # October
            fest_amt = 850000.0
            v_no = f"VCHR-{y}-{voucher_counter}"
            voucher_counter += 1
            rows.append({
                "Voucher_No": v_no,
                "Date": datetime(y, m, 24).strftime("%d/%m/%Y"),
                "Account_Head": "Student Fests & Cultural Events",
                "Department": "Student Affairs Council",
                "Narration": "Annual National Tech Fest 'TechnoVision 2024' Hackathon & Celebrity Keynote",
                "Debit": f"₹ {format_inr(fest_amt)}",
                "Credit": "",
            })
        elif month_idx == 10:  # February
            fest_amt = 620000.0
            v_no = f"VCHR-{y}-{voucher_counter}"
            voucher_counter += 1
            rows.append({
                "Voucher_No": v_no,
                "Date": datetime(y, m, 20).strftime("%d/%m/%Y"),
                "Account_Head": "Student Fests & Cultural Events",
                "Department": "Student Affairs Council",
                "Narration": "Inter-Collegiate Cultural Festival 'Pinnacle 2025' Staging & Audio Production",
                "Debit": f"₹ {format_inr(fest_amt)}",
                "Credit": "",
            })
        else:
            # Minor student club activities
            club_amt = random.uniform(15000.0, 45000.0)
            v_no = f"VCHR-{y}-{voucher_counter}"
            voucher_counter += 1
            rows.append({
                "Voucher_No": v_no,
                "Date": datetime(y, m, random.randint(10, 22)).strftime("%d/%m/%Y"),
                "Account_Head": "Student Fests & Cultural Events",
                "Department": "Student Affairs Council",
                "Narration": "IEEE / ACM Student Chapter Workshops & Robotics Club Demo",
                "Debit": f"₹ {format_inr(club_amt)}",
                "Credit": "",
            })

        # 6. Outflow Head 5: Academic Travel & Conferences (Flexible ~₹40K to ₹1.2L/mo)
        travel_amt = random.uniform(38000.0, 115000.0)
        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, random.randint(7, 23)).strftime("%d/%m/%Y"),
            "Account_Head": "Academic Travel & Conferences",
            "Department": random.choice(departments),
            "Narration": "Faculty Registration and Travel Grant for IEEE Scopus Indexed International Conference",
            "Debit": f"₹ {format_inr(travel_amt)}",
            "Credit": "",
        })

        # 7. Outflow Head 6: Software Licenses & IT Infrastructure (Fixed ~₹1.2L to ₹2.4L/mo)
        soft_amt = random.uniform(115000.0, 235000.0)
        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 16).strftime("%d/%m/%Y"),
            "Account_Head": "Software Licenses & IT Infrastructure",
            "Department": "IT Services Cell",
            "Narration": "MATLAB Campus-Wide License, Microsoft 365 Academic & Cloud Server Retainer",
            "Debit": f"₹ {format_inr(soft_amt)}",
            "Credit": "",
        })

        # 8. Outflow Head 7: Library & Academic Subscriptions (Fixed ~₹60K to ₹1.4L/mo)
        lib_amt = random.uniform(58000.0, 138000.0)
        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 19).strftime("%d/%m/%Y"),
            "Account_Head": "Library & Academic Subscriptions",
            "Department": "Library & Information",
            "Narration": "IEEE Xplore Digital Library Subscription and ScienceDirect E-Journal Renewals",
            "Debit": f"₹ {format_inr(lib_amt)}",
            "Credit": "",
        })

        # 9. Outflow Head 8: Administrative & Campus Maintenance (Fixed ~₹95K to ₹1.7L/mo)
        admin_amt = random.uniform(92000.0, 168000.0)
        v_no = f"VCHR-{y}-{voucher_counter}"
        voucher_counter += 1
        rows.append({
            "Voucher_No": v_no,
            "Date": datetime(y, m, 25).strftime("%d/%m/%Y"),
            "Account_Head": "Administrative & Campus Maintenance",
            "Department": "Administration",
            "Narration": "Campus Facility Housekeeping, Security Services AMC & Diesel Generator Maintenance",
            "Debit": f"₹ {format_inr(admin_amt)}",
            "Credit": "",
        })

    # Sort vouchers chronologically
    rows.sort(key=lambda r: datetime.strptime(r["Date"], "%d/%m/%Y"))

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["Voucher_No", "Date", "Account_Head", "Department", "Narration", "Debit", "Credit"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# ==============================================================================
# 3. STARTUP P&L / BURN CSV GENERATOR
# ==============================================================================
def generate_startup_pnl_csv(output_path: Path, seed: int = 2026) -> Path:
    """
    Generates 12 months of company P&L / Burn cash flows for a B2B SaaS startup.
    Features growing MRR inflows, engineering payroll, cloud/AWS burn, office lease,
    performance marketing, legal/compliance, SaaS tools, and team offsites.
    """
    random.seed(seed)
    np.random.seed(seed)

    rows: List[Dict[str, str]] = []

    for month_idx in range(12):
        y = 2024 + (4 + month_idx - 1) // 12
        m = (4 + month_idx - 1) % 12 + 1

        # 1. Inflows: Growing SaaS MRR from ~₹3.5L to ₹13.8L
        mrr_base = 350000.0 + month_idx * 92000.0 + random.uniform(-15000.0, 25000.0)
        rows.append({
            "Date": datetime(y, m, 2).strftime("%Y-%m-%d"),
            "Description": f"Stripe Payout: B2B Enterprise Subscriptions - Month {month_idx + 1}",
            "Category": "Revenue / MRR",
            "Amount": f"{mrr_base:.2f}",
            "Type": "inflow",
        })

        # Occasional Enterprise POC / Client Invoices
        if month_idx in [2, 5, 8, 11]:
            enterprise_deal = random.uniform(450000.0, 1100000.0)
            rows.append({
                "Date": datetime(y, m, 18).strftime("%Y-%m-%d"),
                "Description": f"Enterprise Custom Deployment Milestone Payment #{month_idx}",
                "Category": "Revenue / Invoicing",
                "Amount": f"{enterprise_deal:.2f}",
                "Type": "inflow",
            })

        # Follow-on Seed Capital Inflow in Month 5 (September)
        if month_idx == 5:
            seed_tranche = 2500000.0
            rows.append({
                "Date": datetime(y, m, 10).strftime("%Y-%m-%d"),
                "Description": "Angel Syndicate Follow-on SAFE Investment Tranche",
                "Category": "Capital Inflow",
                "Amount": f"{seed_tranche:.2f}",
                "Type": "inflow",
            })

        # 2. Outflow 1: Engineering & Core Payroll (Fixed: ₹7.8L -> ₹11.2L growing with team)
        payroll_amt = 780000.0 + month_idx * 30000.0 + random.uniform(-10000.0, 15000.0)
        rows.append({
            "Date": datetime(y, m, 28).strftime("%Y-%m-%d"),
            "Description": "RazorpayX Payroll: Full-Time Engineering, Product & AI Team",
            "Category": "Engineering & Core Payroll",
            "Amount": f"{payroll_amt:.2f}",
            "Type": "outflow",
        })

        # 3. Outflow 2: Cloud & AI API Infrastructure (Fixed: AWS, GCP, OpenAI)
        cloud_amt = 135000.0 + month_idx * 16000.0 + random.uniform(-8000.0, 14000.0)
        rows.append({
            "Date": datetime(y, m, 6).strftime("%Y-%m-%d"),
            "Description": "AWS Cloud Hosting, Anthropic & OpenAI LLM Token Ingestion",
            "Category": "Cloud & AI Infrastructure",
            "Amount": f"{cloud_amt:.2f}",
            "Type": "outflow",
        })

        # 4. Outflow 3: Office Co-working Lease (Fixed: WeWork Bangalore)
        lease_amt = 125000.0
        rows.append({
            "Date": datetime(y, m, 4).strftime("%Y-%m-%d"),
            "Description": "WeWork Galaxy Residency Road: 14 Desks Dedicated Office Suite",
            "Category": "Office Co-working Lease",
            "Amount": f"{lease_amt:.2f}",
            "Type": "outflow",
        })

        # 5. Outflow 4: Growth & Performance Marketing (Flexible: Ads & Content)
        marketing_amt = random.uniform(85000.0, 240000.0)
        rows.append({
            "Date": datetime(y, m, 12).strftime("%Y-%m-%d"),
            "Description": "LinkedIn Ads Sponsored Updates & Google Search SEM Campaigns",
            "Category": "Growth & Performance Marketing",
            "Amount": f"{marketing_amt:.2f}",
            "Type": "outflow",
        })

        # 6. Outflow 5: SaaS & Tooling Subscriptions (Fixed: GitHub, Slack, Notion)
        saas_amt = random.uniform(62000.0, 88000.0)
        rows.append({
            "Date": datetime(y, m, 14).strftime("%Y-%m-%d"),
            "Description": "GitHub Enterprise, Slack Pro, Linear, Notion, and Datadog Monitoring",
            "Category": "SaaS & Developer Tools",
            "Amount": f"{saas_amt:.2f}",
            "Type": "outflow",
        })

        # 7. Outflow 6: Legal, Compliance & Audit Fees (Fixed: Retainer + spikes)
        legal_amt = 125000.0 if month_idx in [5, 11] else 35000.0
        rows.append({
            "Date": datetime(y, m, 20).strftime("%Y-%m-%d"),
            "Description": "Corporate Legal Counsel Retainer, GST Filings & Annual Statutory Audit",
            "Category": "Legal & Compliance",
            "Amount": f"{legal_amt:.2f}",
            "Type": "outflow",
        })

        # 8. Outflow 7: Team Offsites & Client Travel (Flexible)
        travel_amt = random.uniform(42000.0, 195000.0)
        rows.append({
            "Date": datetime(y, m, 22).strftime("%Y-%m-%d"),
            "Description": "Client On-Site Discovery Workshops (Mumbai & Delhi) & Quarterly Team Dinner",
            "Category": "Team Travel & Offsites",
            "Amount": f"{travel_amt:.2f}",
            "Type": "outflow",
        })

        # 9. Outflow 8: Hardware & Operations (Flexible)
        ops_amt = random.uniform(45000.0, 160000.0)
        rows.append({
            "Date": datetime(y, m, 16).strftime("%Y-%m-%d"),
            "Description": "Apple MacBook M3 Pro Developer Upgrades & Pantry Provisions",
            "Category": "Hardware & Office Operations",
            "Amount": f"{ops_amt:.2f}",
            "Type": "outflow",
        })

    # Sort rows chronologically
    rows.sort(key=lambda r: r["Date"])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["Date", "Description", "Category", "Amount", "Type"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# ==============================================================================
# 4. PRE-PARSED JSON FIXTURE GENERATOR
# ==============================================================================
def generate_institute_fixture_json(
    csv_path: Path, output_fixture_path: Path
) -> Path:
    """
    Compiles institute_erp_1.8cr.csv through FinancialIngestor into a
    serialized FinancialProblemInstance JSON fixture (Node 0 baseline).
    """
    from data.ingestor import ColumnMapping, FinancialIngestor

    mapping = ColumnMapping(
        date_col="Date",
        debit_col="Debit",
        credit_col="Credit",
        category_col="Account_Head",
        description_col="Narration",
        date_format="%d/%m/%Y",
        starting_balance=2500000.0,  # ₹25 Lakh starting treasury
    )

    instance = FinancialIngestor.compile(
        csv_source=csv_path,
        mapping=mapping,
        dataset_id="institute_erp_1.8cr",
        name="Apex Institute of Technology - Annual Operating Ledger (₹1.8 Cr)",
    )

    data_dict = instance.to_dict()

    with open(output_fixture_path, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)

    return output_fixture_path


def main() -> None:
    """Generates all 3 CSV datasets and the pre-parsed JSON fixture."""
    print("=" * 65)
    print("FutureFork: Generating Realistic Indian Financial Datasets (12M)")
    print("=" * 65)

    p1 = SAMPLES_DIR / "personal_upi.csv"
    p2 = SAMPLES_DIR / "institute_erp_1.8cr.csv"
    p3 = SAMPLES_DIR / "startup_pnl.csv"
    fix_path = SAMPLES_DIR / "fixture_institute_node0.json"

    print(f"1. Generating Personal UPI Statement: {p1.name} ...")
    generate_personal_upi_csv(p1, seed=42)
    print(f"   [DONE] Generated {p1.name} ({p1.stat().st_size:,} bytes)")

    print(f"2. Generating Institute ERP Ledger: {p2.name} ...")
    generate_institute_erp_csv(p2, seed=108)
    print(f"   [DONE] Generated {p2.name} ({p2.stat().st_size:,} bytes)")

    print(f"3. Generating Startup P&L Statement: {p3.name} ...")
    generate_startup_pnl_csv(p3, seed=2026)
    print(f"   [DONE] Generated {p3.name} ({p3.stat().st_size:,} bytes)")

    print(f"4. Compiling Pre-parsed JSON Fixture: {fix_path.name} ...")
    generate_institute_fixture_json(p2, fix_path)
    print(f"   [DONE] Compiled {fix_path.name} ({fix_path.stat().st_size:,} bytes)")

    print("=" * 65)
    print("All financial datasets generated successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
