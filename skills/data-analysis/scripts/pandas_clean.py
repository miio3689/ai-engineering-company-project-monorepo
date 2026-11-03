"""
Safe snippet for basic pandas cleaning. Copy and adapt for your dataset.
Run: python pandas_clean.py  (ensure pandas is installed)
"""
import sys

try:
    import pandas as pd
except ImportError:
    print("Error: pandas no está instalado.", file=sys.stderr)
    sys.exit(1)

# Load (adjust path and kwargs as needed)
try:
    df = pd.read_csv("data.csv")  # or read_json, read_excel
except FileNotFoundError:
    print("Error: no se encontró el archivo de datos.", file=sys.stderr)
    sys.exit(1)
except PermissionError:
    print("Error: no hay permisos para leer el archivo de datos.", file=sys.stderr)
    sys.exit(1)
except UnicodeDecodeError:
    print("Error: el archivo de datos no tiene una codificación válida.", file=sys.stderr)
    sys.exit(1)
except pd.errors.EmptyDataError:
    print("Error: el archivo de datos está vacío.", file=sys.stderr)
    sys.exit(1)
except pd.errors.ParserError:
    print("Error: el archivo de datos tiene un formato no válido.", file=sys.stderr)
    sys.exit(1)
except OSError:
    print("Error: no se pudo leer el archivo de datos.", file=sys.stderr)
    sys.exit(1)
print("df_shape", df.shape)
print("df_dtypes", df.dtypes)

# Drop fully null columns
df = df.dropna(axis=1, how="all")
print("df_shape_after_drop_all_null_cols", df.shape)

# Fill or drop nulls in key columns (customise columns)
# df = df.dropna(subset=["required_col"])
# df["optional_col"] = df["optional_col"].fillna(0)

# Normalise column names (optional)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
print("df_columns", list(df.columns))

# Deduplicate (optional)
before = len(df)
df = df.drop_duplicates()
print("rows_dropped_duplicates", before - len(df))

# Sample output
print("df_head", df.head())
