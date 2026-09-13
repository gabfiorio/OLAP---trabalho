"""
Popula dw.dim_data com um intervalo de datas (carga única / não incremental).
A dimensão calendário não sofre atualização incremental: é gerada uma vez
cobrindo todo o horizonte de dados da origem (ex.: 2005-01-01 a 2030-12-31).

Uso:
    python load_dim_date.py --start 2005-01-01 --end 2030-12-31
"""
import argparse
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DW_CONN_STR = os.getenv(
    "DW_CONN_STR", "postgresql+psycopg2://dw_user:dw_pass@localhost:5432/adventureworks_dw"
)
engine = create_engine(DW_CONN_STR)

DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
               "Sexta-feira", "Sábado", "Domingo"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def fiscal_year_quarter(d: date):
    # Ano fiscal AdventureWorks: inicia em 1º de julho
    if d.month >= 7:
        fy = d.year + 1
        fq = ((d.month - 7) // 3) + 1
    else:
        fy = d.year
        fq = ((d.month + 5) // 3) + 1
    return fy, fq


def build_calendar(start: date, end: date) -> pd.DataFrame:
    rows = []
    d = start
    while d <= end:
        fy, fq = fiscal_year_quarter(d)
        rows.append({
            "chave_data": int(d.strftime("%Y%m%d")),
            "data_completa": d,
            "dia_mes": d.day,
            "nome_dia": DIAS_SEMANA[d.weekday()],
            "dia_semana": d.weekday() + 1,
            "numero_mes": d.month,
            "nome_mes": MESES[d.month - 1],
            "trimestre": (d.month - 1) // 3 + 1,
            "ano": d.year,
            "eh_fim_de_semana": d.weekday() >= 5,
            "ano_fiscal": fy,
            "trimestre_fiscal": fq,
        })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2005-01-01")
    parser.add_argument("--end", default="2030-12-31")
    args = parser.parse_args()

    df = build_calendar(date.fromisoformat(args.start), date.fromisoformat(args.end))
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dw.dim_data"))
        df.to_sql("dim_data", conn, schema="dw", if_exists="append", index=False)
    print(f"dw.dim_data populada com {len(df)} datas ({args.start} a {args.end}).")
