# file_handler.py

import pandas as pd
import os


def read_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.csv':
        try:
            return pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding='latin1')
    elif ext in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format.")
