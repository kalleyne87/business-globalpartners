import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from dotenv import load_dotenv
import os

load_dotenv()

SERVER = os.getenv("SERVER")
DATABASE = os.getenv("DATABASE")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

def get_engine():
    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

def clean_order_items(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    df["creation_time_utc"] = pd.to_datetime(df["creation_time_utc"], errors="coerce")   
    return df

def clean_order_item_options(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def clean_date_dim(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    df["date_key"] = pd.to_datetime(df["date_key"], errors="coerce").dt.date
    return df

def load_csv_to_sql(engine, csv_path: str, table_name: str, cleaner):
    df = pd.read_csv(csv_path)
    df = cleaner(df)

    print(f"\nLoading {table_name}...")
    print("Columns:", df.columns.tolist())
    print("Shape:", df.shape)
    print(df.head())
    print(df.dtypes)

    try:
        df.to_sql(
            table_name,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=200
        )
        print(f"Finished loading {table_name}")
    except Exception as e:
        print("\nFAILED LOAD")
        print(type(e))
        print(e)
        raise

def validate_counts(engine):
    with engine.connect() as conn:
        for table in ["order_items", "order_item_options", "date_dim"]:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"{table}: {count}")

def test_connection(engine):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Connection test:", result.scalar())
if __name__ == "__main__":
    engine = get_engine()
    test_connection(engine)
    #load_csv_to_sql(engine, "order_items.csv", "order_items", clean_order_items)
    #load_csv_to_sql(engine, "order_item_options.csv", "order_item_options", clean_order_item_options)
    #load_csv_to_sql(engine, "date_dim.csv", "date_dim", clean_date_dim)
