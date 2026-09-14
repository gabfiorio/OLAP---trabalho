from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv()

SRC_CONN_STR = os.getenv("SRC_CONN_STR")
DW_CONN_STR = os.getenv("DW_CONN_STR")

print("Testando SQL Server...")

try:
    engine_sql = create_engine(SRC_CONN_STR)

    with engine_sql.connect() as conn:
        resultado = conn.execute(
            text("SELECT DB_NAME() AS banco, @@VERSION AS versao")
        ).fetchone()

        print("SQL Server conectado!")
        print("Banco:", resultado[0])

except Exception as e:
    print("ERRO no SQL Server:")
    print(e)


print("\nTestando PostgreSQL...")

try:
    engine_pg = create_engine(DW_CONN_STR)

    with engine_pg.connect() as conn:
        resultado = conn.execute(
            text("SELECT current_database(), current_schema()")
        ).fetchone()

        print("PostgreSQL conectado!")
        print("Banco:", resultado[0])
        print("Schema:", resultado[1])

except Exception as e:
    print("ERRO no PostgreSQL:")
    print(e)