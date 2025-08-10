# single_compare.py
import os
import uuid
import logging
import pandas as pd
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO)

GRAPH_FOLDER = os.path.join('static', 'graphs')
os.makedirs(GRAPH_FOLDER, exist_ok=True)


def detect_valid_data(file_path):
    """
    Read uploaded file (csv/xls/xlsx), detect header row (first row with >=2 non-empty),
    assign headers, return (df, numeric_df).
    - df: original data with headers (strings preserved)
    - numeric_df: numeric-only (coerced), rows/cols entirely NaN dropped
    """
    ext = os.path.splitext(file_path)[-1].lower()

    if ext == '.csv':
        raw_df = pd.read_csv(file_path, header=None, dtype=object)
    elif ext == '.xls':
        raw_df = pd.read_excel(file_path, header=None, engine='xlrd', dtype=object)
    elif ext == '.xlsx':
        raw_df = pd.read_excel(file_path, header=None, engine='openpyxl', dtype=object)
    else:
        raise ValueError("Unsupported file format.")

    for idx, row in raw_df.iterrows():
        if row.dropna().shape[0] >= 2:
            headers = raw_df.iloc[idx].tolist()
            df = raw_df.iloc[idx + 1:].copy().reset_index(drop=True)

            # assign headers (truncate if header row longer; pad if shorter)
            if len(headers) >= df.shape[1]:
                df.columns = headers[:df.shape[1]]
            else:
                extra = [f"col_{i}" for i in range(len(headers), df.shape[1])]
                df.columns = headers + extra

            # drop completely empty rows/columns
            df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')

            # numeric copy
            numeric_df = df.copy().apply(pd.to_numeric, errors='coerce')
            numeric_df = numeric_df.dropna(axis=1, how='all').dropna(axis=0, how='all')

            return df.reset_index(drop=True), numeric_df.reset_index(drop=True)

    # nothing valid found
    return pd.DataFrame(), pd.DataFrame()


def extract_numeric_headers(file_path):
    """Return list of numeric column headers for dropdown."""
    df, numeric_df = detect_valid_data(file_path)
    if numeric_df.empty:
        return []
    return numeric_df.columns.tolist()


def _detect_label_column(df, numeric_cols):
    """Heuristic to choose label/name column."""
    keywords = ['name', 'company', 'seller', 'brand', 'product']
    for col in df.columns:
        if isinstance(col, str) and any(k in col.lower() for k in keywords):
            return col
    # first non-numeric
    for col in df.columns:
        if col not in numeric_cols:
            return col
    # fallback
    return df.columns[0] if len(df.columns) > 0 else None


def generate_single_compare_chart(file_path, parameter, top_n=10, preference='lower'):
    """
    Generate chart image from uploaded file and return the image filename (basename).
    - file_path: path to uploaded file
    - parameter: numeric column name to compare
    - top_n: how many rows to show
    - preference: 'lower' or 'higher' (lower => ascending)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid data found in file.")

    if parameter not in numeric_df.columns:
        raise ValueError(f"Parameter '{parameter}' not found in numeric columns.")

    # detect label column
    label_col = _detect_label_column(df, numeric_df.columns.tolist())
    if label_col is None:
        raise ValueError("No label/identifier column found to label chart.")

    # Coerce parameter to numeric, drop rows with NaN for this parameter
    working = df.copy()
    working[parameter] = pd.to_numeric(working[parameter], errors='coerce')
    working = working.dropna(subset=[parameter]).copy()
    if working.empty:
        raise ValueError("No rows with valid numeric values for the selected parameter.")

    # Sort based on preference
    ascending = True if preference == 'lower' else False
    working = working.sort_values(by=parameter, ascending=ascending)

    # Limit to top_n
    top_n = int(top_n) if int(top_n) > 0 else 10
    top_n = min(top_n, len(working))
    top = working.head(top_n)

    # Determine if log scale is needed for readability
    vals = top[parameter].astype(float)
    use_log = False
    try:
        if vals.max() / max(vals.min(), 1e-9) > 1000:
            use_log = True
    except Exception:
        use_log = False

    # Plot horizontal bar chart
    plt.figure(figsize=(10, 6))
    if use_log:
        plt.barh(top[label_col].astype(str), vals)
        plt.xscale('log')
        xlabel = f"{parameter} (log scale)"
    else:
        plt.barh(top[label_col].astype(str), vals)
        xlabel = parameter

    plt.xlabel(xlabel)
    plt.ylabel(label_col)
    plt.title(f"{parameter} comparison (top {top_n}) — preference: {preference}")
    plt.gca().invert_yaxis()
    plt.tight_layout()

    # Save unique filename
    filename = f"{uuid.uuid4().hex[:10]}_{parameter}_{preference}.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path)
    plt.close()

    logging.info(f"Saved chart to {full_path}")

    return filename

