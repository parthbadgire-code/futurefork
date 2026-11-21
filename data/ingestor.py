"""
FutureFork: Financial Data Ingestion & Baseline Compiler
Member 1: Data Ingestion & Baseline Compiler

Fast, defensive Pandas-based compiler that converts raw financial CSV bytes +
a ColumnMapping into a validated FinancialProblemInstance:
- 12 months x 8 canonical expense categories outflow matrix
- 12-element monthly inflow vector
- Deterministic auto-tagging (fixed vs. flexible)
- Node 0 statistical parameters (mean mu, historical std sigma)
- Vectorized execution target: < 200ms per CSV
"""

from __future__ import annotations

import io
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Check if engine.model provides schema definitions; otherwise fallback to internal classes
try:
    from engine.model import ColumnMapping as _EngineColumnMapping
    from engine.model import FinancialProblemInstance as _EngineFinancialProblemInstance
except (ImportError, AttributeError):
    _EngineColumnMapping = None
    _EngineFinancialProblemInstance = None


# Canonical 8 fallback categories if fewer than 8 categories exist
DEFAULT_CANONICAL_CATEGORIES = [
    "Salaries & Payroll",
    "Rent & Infrastructure",
    "Utilities & Bills",
    "Consumables & Supplies",
    "Travel & Transport",
    "Software & Subscriptions",
    "Marketing & Growth",
    "Miscellaneous & Other",
]

# Rule-based auto-tagging keyword sets
FIXED_KEYWORDS = {
    "rent", "lease", "salary", "salaries", "payroll", "stipend", "honorarium",
    "emi", "loan", "utilities", "utility", "electricity", "broadband", "internet",
    "water", "insurance", "tuition", "compliance", "legal", "audit", "cloud",
    "aws", "gcp", "azure", "server", "license", "licenses", "subscription",
    "subscriptions", "software", "maintenance", "fixed", "amc", "retainer",
}

FLEXIBLE_KEYWORDS = {
    "travel", "food", "dining", "restaurant", "swiggy", "zomato", "cab", "uber",
    "ola", "event", "events", "fest", "fests", "marketing", "ads", "advertising",
    "campaign", "shopping", "entertainment", "discretionary", "misc",
    "miscellaneous", "consumables", "other", "flexible", "freelance", "perks",
    "bonus", "conference", "hospitality", "supplies", "hardware", "refreshment",
}


@dataclass
class ColumnMapping:
    """Specifies the column header mappings for parsing financial CSV files."""
    date_col: str = "Date"
    amount_col: Optional[str] = None
    debit_col: Optional[str] = None
    credit_col: Optional[str] = None
    category_col: Optional[str] = None
    description_col: Optional[str] = None
    type_col: Optional[str] = None
    date_format: Optional[str] = None
    starting_balance: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColumnMapping":
        """Instantiate ColumnMapping from dictionary with flexible aliases."""
        if not data:
            return cls()

        date_col = (
            data.get("date_col") or data.get("date") or data.get("Date") or "Date"
        )
        amount_col = data.get("amount_col") or data.get("amount") or data.get("Amount")
        debit_col = (
            data.get("debit_col") or data.get("debit") or data.get("Debit") or
            data.get("withdrawal") or data.get("Withdrawal") or data.get("expense")
        )
        credit_col = (
            data.get("credit_col") or data.get("credit") or data.get("Credit") or
            data.get("deposit") or data.get("Deposit") or data.get("inflow")
        )
        category_col = (
            data.get("category_col") or data.get("category") or data.get("Category") or
            data.get("head") or data.get("Account_Head") or data.get("account_head")
        )
        description_col = (
            data.get("description_col") or data.get("description") or data.get("Description") or
            data.get("narration") or data.get("Narration") or data.get("particulars")
        )
        type_col = (
            data.get("type_col") or data.get("type") or data.get("Type") or
            data.get("transaction_type") or data.get("Txn Type")
        )
        date_format = data.get("date_format") or data.get("format")
        starting_balance = float(data.get("starting_balance") or 0.0)

        return cls(
            date_col=str(date_col).strip(),
            amount_col=str(amount_col).strip() if amount_col else None,
            debit_col=str(debit_col).strip() if debit_col else None,
            credit_col=str(credit_col).strip() if credit_col else None,
            category_col=str(category_col).strip() if category_col else None,
            description_col=str(description_col).strip() if description_col else None,
            type_col=str(type_col).strip() if type_col else None,
            date_format=str(date_format).strip() if date_format else None,
            starting_balance=starting_balance,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinancialProblemInstance:
    """
    Standardized Node 0 Baseline Financial Model consumed by optimization (Member 2),
    Monte Carlo simulation (Member 3), and AI explainer (Member 4).
    """
    dataset_id: str
    name: str
    months: List[str]                            # 12 monthly periods e.g. ["2024-04", ...]
    categories: List[str]                        # Exactly 8 canonical expense categories
    category_types: Dict[str, str]               # category_name -> "fixed" | "flexible"
    outflows: List[List[float]]                  # 12 x 8 matrix of monthly outflows (>= 0.0)
    inflows: List[float]                         # 12-element vector of monthly inflows (>= 0.0)
    starting_balance: float                      # Starting treasury / bank balance
    category_means: Dict[str, float]             # mean (mu) per category (len 8)
    category_stds: Dict[str, float]              # standard deviation (sigma) per category (len 8)
    total_outflows: List[float]                  # monthly sum of outflows across categories (len 12)
    net_cash_flows: List[float]                  # monthly inflow - total_outflow (len 12)
    cash_balances: List[float]                   # cumulative cash balance at end of each month (len 12)
    summary: Dict[str, Any]                      # High-level aggregate statistics
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def outflow_matrix(self) -> np.ndarray:
        """Returns the (12, 8) outflow matrix as a float64 numpy array."""
        return np.array(self.outflows, dtype=np.float64)

    @property
    def inflow_vector(self) -> np.ndarray:
        """Returns the (12,) inflow vector as a float64 numpy array."""
        return np.array(self.inflows, dtype=np.float64)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize instance to a pure Python dictionary (JSON serializable)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FinancialProblemInstance":
        """Reconstruct instance from serialized dictionary."""
        return cls(
            dataset_id=str(data["dataset_id"]),
            name=str(data["name"]),
            months=list(data["months"]),
            categories=list(data["categories"]),
            category_types=dict(data["category_types"]),
            outflows=[[float(x) for x in row] for row in data["outflows"]],
            inflows=[float(x) for x in data["inflows"]],
            starting_balance=float(data["starting_balance"]),
            category_means={k: float(v) for k, v in data["category_means"].items()},
            category_stds={k: float(v) for k, v in data["category_stds"].items()},
            total_outflows=[float(x) for x in data["total_outflows"]],
            net_cash_flows=[float(x) for x in data["net_cash_flows"]],
            cash_balances=[float(x) for x in data["cash_balances"]],
            summary=dict(data["summary"]),
            raw_metadata=dict(data.get("raw_metadata", {})),
        )


# Alias to canonical engine.model definitions when available
if _EngineColumnMapping is not None:
    ColumnMapping = _EngineColumnMapping
if _EngineFinancialProblemInstance is not None:
    FinancialProblemInstance = _EngineFinancialProblemInstance


def clean_currency_series(series: pd.Series) -> pd.Series:
    """
    Vectorized currency cleaner.
    Strips '₹', 'INR', 'Rs.', '$', commas, handles accounting parentheses (e.g. '(1,250.00)' -> '-1250.00'),
    and converts to float64 with NaN filled to 0.0.
    """
    if series is None or series.empty:
        return pd.Series(dtype=np.float64)

    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0.0).astype(np.float64)

    s = series.astype(str).str.strip()
    # Replace blanks, 'nan', 'None', '-'
    s = s.replace(r"^(nan|NaN|None|-|\s*)$", "0", regex=True)
    # Accounting parentheses negative format: (1,234.50) -> -1234.50
    s = s.str.replace(r"^\s*\((.*)\)\s*$", r"-\1", regex=True)
    # Strip word currency prefixes: Rs., Rs, INR, inr
    s = s.str.replace(r"(?i)\b(inr|rs)\.?\s*", "", regex=True)
    # Strip currency symbols, commas, and remaining spaces: ₹, $, commas, spaces
    s = s.str.replace(r"[₹$,\s]", "", regex=True)
    # Convert to numeric, errors to NaN, fillna with 0.0
    return pd.to_numeric(s, errors="coerce").fillna(0.0).astype(np.float64)


def parse_date_series(series: pd.Series, date_format: Optional[str] = None) -> pd.Series:
    """
    Robust date parser with fallback heuristics for DD/MM/YYYY vs YYYY-MM-DD.
    """
    s = series.astype(str).str.strip()
    if date_format:
        try:
            parsed = pd.to_datetime(s, format=date_format, errors="coerce")
            if parsed.notna().sum() > 0:
                return parsed
        except Exception:
            pass

    # Normalise DD-MM-YYYY / DD.MM.YYYY to DD/MM/YYYY. pandas infers ONE format from the first
    # value, so a column mixing "28/04/2024" and "18-07-2024" would otherwise silently drop rows.
    s = s.str.replace(r"^(\d{1,2})[-.](\d{1,2})[-.](\d{2,4})$", r"\1/\2/\3", regex=True)

    # Try dayfirst=True first (predominant standard in India: DD/MM/YYYY or DD-MM-YYYY)
    parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")
    # If more than 35% failed to parse, attempt standard ISO / dayfirst=False
    if parsed.isna().mean() > 0.35:
        parsed_iso = pd.to_datetime(s, dayfirst=False, errors="coerce")
        if parsed_iso.isna().sum() < parsed.isna().sum():
            parsed = parsed_iso

    return parsed


def auto_detect_columns(df: pd.DataFrame) -> ColumnMapping:
    """
    Inspects DataFrame headers and sample values to produce an auto-detected ColumnMapping.
    Used when ColumnMapping is missing or incomplete.
    """
    cols = list(df.columns)
    cols_lower = {c: str(c).strip().lower() for c in cols}

    date_col = "Date"
    debit_col = None
    credit_col = None
    amount_col = None
    category_col = None
    description_col = None
    type_col = None

    for col, cl in cols_lower.items():
        if not date_col or date_col == "Date":
            if any(k in cl for k in ["date", "txn_date", "timestamp", "posting"]):
                date_col = col

        if not debit_col:
            if any(k in cl for k in ["debit", "withdrawal", "expense", "dr", "paid_out", "outflow"]):
                debit_col = col

        if not credit_col:
            if any(k in cl for k in ["credit", "deposit", "inflow", "cr", "received"]):
                credit_col = col

        if not amount_col:
            if any(k in cl for k in ["amount", "net_amount", "txn_amount", "total"]):
                amount_col = col

        if not category_col:
            if any(k in cl for k in ["category", "head", "expense_type", "account_head", "classification"]):
                category_col = col

        if not description_col:
            if any(k in cl for k in ["description", "narration", "particulars", "details", "remark", "memo"]):
                description_col = col

        if not type_col:
            if cl in ["type", "txn_type", "transaction_type", "cr/dr"]:
                type_col = col

    # Fallbacks if still not found
    if not date_col and len(cols) > 0:
        date_col = cols[0]
    if not debit_col and not amount_col:
        # Search for first numeric column
        for col in cols:
            if col != date_col:
                amount_col = col
                break

    return ColumnMapping(
        date_col=date_col,
        debit_col=debit_col,
        credit_col=credit_col,
        amount_col=amount_col,
        category_col=category_col,
        description_col=description_col,
        type_col=type_col,
    )


def tag_category(category_name: str, monthly_values: Optional[np.ndarray] = None) -> str:
    """
    Deterministically tag an expense category as 'fixed' or 'flexible'.
    Uses rule-based keyword matching first, followed by variance heuristic (CV < 0.20 -> fixed).
    """
    cat_lower = str(category_name).lower().strip()
    words = re.findall(r"[a-z]+", cat_lower)

    # 1. Check fixed keywords
    if any(w in FIXED_KEYWORDS for w in words):
        return "fixed"

    # 2. Check flexible keywords
    if any(w in FLEXIBLE_KEYWORDS for w in words):
        return "flexible"

    # 3. Variance heuristic: if coefficient of variation (sigma / mu) < 0.20, classify as fixed
    if monthly_values is not None and len(monthly_values) > 0:
        mu = float(np.mean(monthly_values))
        sigma = float(np.std(monthly_values, ddof=1)) if len(monthly_values) > 1 else 0.0
        if mu > 0 and (sigma / mu) < 0.20:
            return "fixed"

    return "flexible"


class FinancialIngestor:
    """
    High-performance, defensive Pandas compiler that parses financial CSV bytes
    into a validated FinancialProblemInstance.
    """

    @staticmethod
    def read_csv(csv_source: Union[bytes, str, Path, io.BytesIO, io.StringIO]) -> pd.DataFrame:
        """
        Loads CSV content into a pandas DataFrame supporting bytes, file paths, or streams.
        Tries encoding fallbacks: utf-8-sig, utf-8, latin-1, cp1252.
        """
        raw_bytes: bytes

        if isinstance(csv_source, (str, Path)) and Path(str(csv_source)).is_file():
            raw_bytes = Path(str(csv_source)).read_bytes()
        elif isinstance(csv_source, bytes):
            raw_bytes = csv_source
        elif isinstance(csv_source, (io.BytesIO, io.BufferedReader)):
            raw_bytes = csv_source.read()
        elif isinstance(csv_source, io.StringIO):
            raw_bytes = csv_source.getvalue().encode("utf-8")
        elif isinstance(csv_source, str):
            raw_bytes = csv_source.encode("utf-8")
        else:
            raise ValueError(f"Unsupported csv_source type: {type(csv_source)}")

        # Encoding fallback pipeline
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        decoded_text: Optional[str] = None
        for enc in encodings:
            try:
                decoded_text = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if decoded_text is None:
            decoded_text = raw_bytes.decode("utf-8", errors="replace")

        if not decoded_text.strip():
            return pd.DataFrame()

        # Read CSV with defensive parsing
        try:
            df = pd.read_csv(
                io.StringIO(decoded_text),
                skipinitialspace=True,
                low_memory=False,
            )
        except (pd.errors.EmptyDataError, ValueError):
            return pd.DataFrame()

        # Clean column headers
        df.columns = [str(c).strip() for c in df.columns]
        # Drop completely blank rows
        df = df.dropna(how="all").reset_index(drop=True)
        return df

    @classmethod
    def compile(
        cls,
        csv_source: Union[bytes, str, Path, io.BytesIO, io.StringIO],
        mapping: Optional[Union[ColumnMapping, Dict[str, Any]]] = None,
        dataset_id: str = "dataset_node0",
        name: str = "Financial Dataset",
        starting_balance: Optional[float] = None,
    ) -> FinancialProblemInstance:
        """
        Compile raw CSV into FinancialProblemInstance.
        Execution benchmark: < 200ms per CSV.
        """
        df = cls.read_csv(csv_source)

        if df.empty:
            raise ValueError("CSV dataset is empty; cannot compile FinancialProblemInstance.")

        # Normalize column mapping
        if mapping is None:
            col_map = auto_detect_columns(df)
        elif isinstance(mapping, dict):
            col_map = ColumnMapping.from_dict(mapping)
        elif isinstance(mapping, ColumnMapping):
            col_map = mapping
        else:
            col_map = auto_detect_columns(df)

        if starting_balance is not None:
            col_map.starting_balance = float(starting_balance)

        # 1. Parse Dates and build monthly periods
        date_col = col_map.date_col
        if date_col not in df.columns:
            # Fallback search for date column
            detected = auto_detect_columns(df)
            date_col = detected.date_col

        df["_parsed_date"] = parse_date_series(df[date_col], date_format=col_map.date_format)

        # Drop rows where date could not be parsed
        valid_date_mask = df["_parsed_date"].notna()
        if not valid_date_mask.any():
            # If all dates failed, synthesize 12 sequential monthly buckets across rows
            n_rows = len(df)
            rows_per_month = max(1, n_rows // 12)
            month_indices = [min(11, i // rows_per_month) for i in range(n_rows)]
            df["_month_idx"] = month_indices
            all_12_months = [f"Month {m}" for m in range(12)]
        else:
            df = df[valid_date_mask].copy()
            df["_ym"] = df["_parsed_date"].dt.to_period("M")

            unique_periods = sorted(df["_ym"].unique())
            if len(unique_periods) >= 12:
                # Use the 12 most recent consecutive months
                start_p = unique_periods[-12]
                selected_periods = pd.period_range(start=start_p, periods=12, freq="M")
            elif len(unique_periods) > 0:
                # Pad to 12 consecutive months starting from min period
                start_p = unique_periods[0]
                selected_periods = pd.period_range(start=start_p, periods=12, freq="M")
            else:
                selected_periods = pd.period_range(start="2024-04", periods=12, freq="M")

            all_12_months = [str(p) for p in selected_periods]
            period_to_idx = {p: i for i, p in enumerate(selected_periods)}

            df["_month_idx"] = df["_ym"].map(period_to_idx)
            # Filter out records outside the 12-month window
            df = df[df["_month_idx"].notna()].copy()
            df["_month_idx"] = df["_month_idx"].astype(int)

        # 2. Extract Inflow and Outflow amounts
        if col_map.debit_col and col_map.debit_col in df.columns and col_map.credit_col and col_map.credit_col in df.columns:
            df["_outflow"] = clean_currency_series(df[col_map.debit_col]).abs()
            df["_inflow"] = clean_currency_series(df[col_map.credit_col]).abs()
        elif col_map.amount_col and col_map.amount_col in df.columns:
            raw_amt = clean_currency_series(df[col_map.amount_col])
            # Check if there is an explicit type column
            type_col = col_map.type_col or (auto_detect_columns(df).type_col)
            if type_col and type_col in df.columns:
                t_str = df[type_col].astype(str).str.lower()
                is_credit = t_str.str.contains(r"credit|deposit|inflow|cr|income", regex=True)
                df["_inflow"] = np.where(is_credit, raw_amt.abs(), 0.0)
                df["_outflow"] = np.where(~is_credit, raw_amt.abs(), 0.0)
            else:
                # Check sign: if negatives exist, treat negative as outflow, positive as inflow
                if (raw_amt < 0).any():
                    df["_outflow"] = np.where(raw_amt < 0, raw_amt.abs(), 0.0)
                    df["_inflow"] = np.where(raw_amt > 0, raw_amt, 0.0)
                else:
                    # All positive amounts: if category has salary/grant/inflow keywords, assign to inflow
                    cat_col = col_map.category_col
                    if cat_col and cat_col in df.columns:
                        c_str = df[cat_col].astype(str).str.lower()
                        is_inflow_cat = c_str.str.contains(r"salary|fee|grant|revenue|invoice|income|deposit", regex=True)
                        df["_inflow"] = np.where(is_inflow_cat, raw_amt, 0.0)
                        df["_outflow"] = np.where(~is_inflow_cat, raw_amt, 0.0)
                    else:
                        # Default all positive to outflow
                        df["_outflow"] = raw_amt
                        df["_inflow"] = 0.0
        else:
            # Fallback: find any numeric column
            numeric_cols = [c for c in df.columns if c not in [date_col, "_parsed_date", "_ym", "_month_idx"]]
            if numeric_cols:
                raw_amt = clean_currency_series(df[numeric_cols[0]])
                df["_outflow"] = raw_amt.abs()
                df["_inflow"] = 0.0
            else:
                df["_outflow"] = 0.0
                df["_inflow"] = 0.0

        # 3. Extract and Clean Categories
        cat_col = col_map.category_col
        if cat_col and cat_col in df.columns:
            raw_cats = df[cat_col].astype(str).str.strip()
        else:
            # Infer category from description if available
            desc_col = col_map.description_col
            if desc_col and desc_col in df.columns:
                raw_cats = df[desc_col].astype(str).apply(cls._infer_category_from_desc)
            else:
                raw_cats = pd.Series(["General Expense"] * len(df))

        df["_category"] = raw_cats.replace(r"^(nan|None|\s*)$", "Uncategorized", regex=True)

        # 4. Consolidate into Exactly 8 Canonical Categories
        # Consider only outflow records for category sizing
        outflow_df = df[df["_outflow"] > 0].copy()

        if outflow_df.empty:
            chosen_categories = DEFAULT_CANONICAL_CATEGORIES.copy()
        else:
            cat_totals = outflow_df.groupby("_category")["_outflow"].sum().sort_values(ascending=False)
            unique_cats = list(cat_totals.index)

            if len(unique_cats) > 8:
                # Top 7 categories preserved; long tail grouped into "Other / Discretionary"
                top_7 = unique_cats[:7]
                df["_category_consolidated"] = df["_category"].apply(
                    lambda c: c if c in top_7 else "Other / Discretionary"
                )
                chosen_categories = top_7 + ["Other / Discretionary"]
            elif len(unique_cats) == 8:
                df["_category_consolidated"] = df["_category"]
                chosen_categories = unique_cats
            else:
                # Fewer than 8 categories: pad with default canonical categories
                df["_category_consolidated"] = df["_category"]
                chosen_categories = list(unique_cats)
                for def_cat in DEFAULT_CANONICAL_CATEGORIES:
                    if def_cat not in chosen_categories:
                        chosen_categories.append(def_cat)
                    if len(chosen_categories) == 8:
                        break

        # Ensure chosen_categories is strictly length 8
        chosen_categories = chosen_categories[:8]
        while len(chosen_categories) < 8:
            chosen_categories.append(f"Category {len(chosen_categories) + 1}")

        # 5. Build 12 x 8 Outflow Matrix
        # Pivot by month index (0..11) and category
        if not outflow_df.empty:
            outflow_records = df[df["_outflow"] > 0]
            pivot = outflow_records.pivot_table(
                index="_month_idx",
                columns="_category_consolidated",
                values="_outflow",
                aggfunc="sum",
                fill_value=0.0,
            )
            pivot = pivot.reindex(index=range(12), columns=chosen_categories, fill_value=0.0)
            outflow_matrix = pivot.values.astype(np.float64)
        else:
            outflow_matrix = np.zeros((12, 8), dtype=np.float64)

        # Round and ensure non-negative
        outflow_matrix = np.maximum(0.0, np.round(outflow_matrix, 2))

        # 6. Build 12-element Inflow Vector
        inflow_series = df.groupby("_month_idx")["_inflow"].sum()
        inflow_vector = np.zeros(12, dtype=np.float64)
        for m_idx in range(12):
            inflow_vector[m_idx] = round(float(inflow_series.get(m_idx, 0.0)), 2)

        # 7. Auto-Tagging: Fixed vs Flexible
        category_types: Dict[str, str] = {}
        category_means: Dict[str, float] = {}
        category_stds: Dict[str, float] = {}

        for j, cat in enumerate(chosen_categories):
            col_vals = outflow_matrix[:, j]
            tag = tag_category(cat, col_vals)
            category_types[cat] = tag

            mu = float(np.mean(col_vals))
            sigma = float(np.std(col_vals, ddof=1)) if len(col_vals) > 1 else 0.0
            # Clean up zero-variance or NaN edge cases
            category_means[cat] = round(0.0 if np.isnan(mu) or np.isinf(mu) else mu, 2)
            category_stds[cat] = round(0.0 if np.isnan(sigma) or np.isinf(sigma) else max(0.0, sigma), 2)

        # 8. Monthly Aggregates, Balances, and Summary
        total_outflows = [round(float(x), 2) for x in np.sum(outflow_matrix, axis=1)]
        net_cash_flows = [
            round(float(inflow_vector[i] - total_outflows[i]), 2) for i in range(12)
        ]

        curr_bal = col_map.starting_balance
        cash_balances: List[float] = []
        for net in net_cash_flows:
            curr_bal += net
            cash_balances.append(round(float(curr_bal), 2))

        total_inflow = round(float(np.sum(inflow_vector)), 2)
        total_outflow = round(float(np.sum(outflow_matrix)), 2)
        net_cash_flow = round(total_inflow - total_outflow, 2)
        ending_balance = cash_balances[-1] if cash_balances else col_map.starting_balance

        monthly_outflow_mean = round(float(np.mean(total_outflows)), 2)
        monthly_outflow_std = round(float(np.std(total_outflows, ddof=1)), 2) if len(total_outflows) > 1 else 0.0
        monthly_inflow_mean = round(float(np.mean(inflow_vector)), 2)
        monthly_inflow_std = round(float(np.std(inflow_vector, ddof=1)), 2) if len(inflow_vector) > 1 else 0.0

        # Fixed expense ratio
        fixed_cats = [cat for cat, t in category_types.items() if t == "fixed"]
        fixed_annual_sum = sum(category_means[c] * 12 for c in fixed_cats)
        fixed_ratio = round(fixed_annual_sum / total_outflow, 4) if total_outflow > 0 else 0.0

        # Runway calculation: if burn rate > 0 and net deficit
        burn_rate = monthly_outflow_mean
        runway_months = None
        if ending_balance > 0 and monthly_outflow_mean > monthly_inflow_mean:
            net_monthly_burn = monthly_outflow_mean - monthly_inflow_mean
            if net_monthly_burn > 0:
                runway_months = round(ending_balance / net_monthly_burn, 1)

        summary = {
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "net_cash_flow": net_cash_flow,
            "starting_balance": col_map.starting_balance,
            "ending_balance": ending_balance,
            "monthly_outflow_mean": monthly_outflow_mean,
            "monthly_outflow_std": monthly_outflow_std,
            "monthly_inflow_mean": monthly_inflow_mean,
            "monthly_inflow_std": monthly_inflow_std,
            "burn_rate": burn_rate,
            "runway_months": runway_months,
            "fixed_expense_ratio": fixed_ratio,
            "num_fixed_categories": len(fixed_cats),
            "num_flexible_categories": 8 - len(fixed_cats),
        }

        raw_metadata = {
            "dataset_id": dataset_id,
            "name": name,
            "source_rows": len(df),
            "date_range": [all_12_months[0], all_12_months[-1]],
            "detected_mapping": col_map.to_dict(),
        }

        return FinancialProblemInstance(
            dataset_id=dataset_id,
            name=name,
            months=all_12_months,
            categories=chosen_categories,
            category_types=category_types,
            outflows=outflow_matrix.tolist(),
            inflows=inflow_vector.tolist(),
            starting_balance=col_map.starting_balance,
            category_means=category_means,
            category_stds=category_stds,
            total_outflows=total_outflows,
            net_cash_flows=net_cash_flows,
            cash_balances=cash_balances,
            summary=summary,
            raw_metadata=raw_metadata,
        )

    @staticmethod
    def _infer_category_from_desc(desc: str) -> str:
        """Heuristic category inferrer from transaction narration string."""
        d = str(desc).lower()
        if any(k in d for k in ["salary", "payroll", "stipend"]):
            return "Salaries & Payroll"
        if any(k in d for k in ["rent", "lease", "wework", "office"]):
            return "Rent & Infrastructure"
        if any(k in d for k in ["bescom", "power", "electric", "broadband", "act", "airtel", "water", "utility"]):
            return "Utilities & Bills"
        if any(k in d for k in ["emi", "loan", "hdfc", "icici", "sbi"]):
            return "Loan & EMI"
        if any(k in d for k in ["swiggy", "zomato", "blinkit", "zepto", "food", "grocery", "groceries", "restaurant"]):
            return "Food & Consumables"
        if any(k in d for k in ["uber", "ola", "travel", "flight", "indigo", "irctc", "fuel", "petrol"]):
            return "Travel & Transport"
        if any(k in d for k in ["aws", "amazon web", "cloud", "openai", "github", "slack", "notion", "google"]):
            return "Cloud & Software"
        if any(k in d for k in ["fest", "event", "techfest", "conference", "symposium"]):
            return "Events & Fests"
        if any(k in d for k in ["ads", "google ads", "meta", "marketing", "campaign"]):
            return "Marketing & Growth"
        if any(k in d for k in ["legal", "audit", "tax", "gst", "compliance"]):
            return "Legal & Compliance"
        if any(k in d for k in ["lab", "equipment", "consumables", "chemicals"]):
            return "Lab Consumables"
        return "Miscellaneous"


def compile_financial_instance(
    csv_source: Union[bytes, str, Path, io.BytesIO, io.StringIO],
    mapping: Optional[Union[ColumnMapping, Dict[str, Any]]] = None,
    dataset_id: str = "dataset_node0",
    name: str = "Financial Dataset",
    starting_balance: Optional[float] = None,
) -> FinancialProblemInstance:
    """Convenience functional wrapper around FinancialIngestor.compile."""
    return FinancialIngestor.compile(
        csv_source=csv_source,
        mapping=mapping,
        dataset_id=dataset_id,
        name=name,
        starting_balance=starting_balance,
    )


if __name__ == "__main__":
    import time

    print("=" * 70)
    print("FutureFork Financial Ingestor & Compiler Benchmark (Member 1)")
    print("=" * 70)

    data_dir = Path(__file__).resolve().parent
    samples_dir = data_dir / "samples"

    # CSV sample test targets
    test_csvs = [
        ("personal_upi.csv", "Personal UPI Statement (12M)", None),
        ("institute_erp_1.8cr.csv", "Institute ERP Ledger (~1.8 Cr)", {
            "date_col": "Date", "debit_col": "Debit", "credit_col": "Credit",
            "category_col": "Account_Head", "description_col": "Narration", "date_format": "%d/%m/%Y"
        }),
        ("startup_pnl.csv", "Startup Company P&L / Burn (12M)", {
            "date_col": "Date", "amount_col": "Amount", "category_col": "Category",
            "type_col": "Type", "date_format": "%Y-%m-%d"
        }),
    ]

    all_passed = True

    for filename, display_name, explicit_map in test_csvs:
        p = samples_dir / filename

        if not p.exists():
            print(f"[WARN] {filename} not found, generating sample datasets first...")
            from data.make_finance_samples import main as gen_samples
            gen_samples()
            p = samples_dir / filename

        csv_bytes = p.read_bytes()

        # Benchmark execution
        t0 = time.perf_counter()
        instance = compile_financial_instance(
            csv_source=csv_bytes,
            mapping=explicit_map,
            dataset_id=p.stem,
            name=display_name,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Assertions
        matrix = instance.outflow_matrix
        inflows = instance.inflow_vector

        # 1. Shape asserts
        assert matrix.shape == (12, 8), f"Expected matrix shape (12, 8), got {matrix.shape}"
        assert len(inflows) == 12, f"Expected 12 inflows, got {len(inflows)}"
        assert len(instance.categories) == 8, f"Expected 8 categories, got {len(instance.categories)}"

        # 2. Tag assertions: each category must be 'fixed' or 'flexible'
        for cat, tag in instance.category_types.items():
            assert tag in ("fixed", "flexible"), f"Invalid tag '{tag}' for category '{cat}'"

        # 3. No NaN or Inf assertions
        assert not np.isnan(matrix).any(), "NaN found in outflow matrix"
        assert not np.isinf(matrix).any(), "Inf found in outflow matrix"
        assert not np.isnan(inflows).any(), "NaN found in inflow vector"
        assert not np.isinf(inflows).any(), "Inf found in inflow vector"

        for cat, mu in instance.category_means.items():
            assert not np.isnan(mu) and not np.isinf(mu), f"NaN/Inf in mu for {cat}"
        for cat, sigma in instance.category_stds.items():
            assert not np.isnan(sigma) and not np.isinf(sigma), f"NaN/Inf in sigma for {cat}"

        # 4. Latency SLA assertion (< 200ms)
        assert elapsed_ms < 200.0, f"Latency violation: {elapsed_ms:.2f}ms >= 200ms"

        fixed_count = sum(1 for t in instance.category_types.values() if t == "fixed")
        flex_count = 8 - fixed_count

        print(f" [PASS] {filename:<26} | Shape: {matrix.shape} | Tags: {fixed_count} fixed / {flex_count} flex | Latency: {elapsed_ms:6.2f} ms (< 200ms)")

    print("=" * 70)
    print("All 3 datasets compiled with 100% assertions satisfied!")
    print("=" * 70)
