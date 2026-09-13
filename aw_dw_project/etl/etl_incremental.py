"""
ETL Incremental - AdventureWorks (OLTP/SQL Server) -> Data Warehouse (PostgreSQL)
==================================================================================

Estratégia de carga incremental:
    - Cada tabela de origem possui uma coluna `ModifiedDate` (padrão AdventureWorks).
    - A cada execução, a ETL consulta `ctrl.etl_watermark` para saber a partir de
      qual timestamp deve extrair (extração incremental baseada em watermark/CDC leve).
    - Os registros extraídos (ModifiedDate > watermark) são gravados em STAGING.
    - As dimensões são carregadas com SCD Tipo 2 (customer, product, salesperson)
      via comparação de hash de atributos, e SCD Tipo 1 (territory, promotion,
      ship_method) via UPSERT simples.
    - O fato é carregado por UPSERT idempotente usando a chave natural
      `sales_order_detail_id`, o que garante que reprocessamentos não dupliquem linhas.
    - Ao final de cada etapa bem-sucedida, o watermark é avançado para o maior
      ModifiedDate processado naquela execução.

Uso:
    python etl_incremental.py --full-load        # força carga completa (ignora watermark)
    python etl_incremental.py                    # carga incremental normal (agendável via cron)

Dependências:
    pip install sqlalchemy pyodbc psycopg2-binary pandas python-dotenv
"""
import argparse
import hashlib
import logging
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("etl_adventureworks")

# ---------------------------------------------------------------------------
# Conexões
# ---------------------------------------------------------------------------
SRC_CONN_STR = os.getenv(
    "SRC_CONN_STR",
    "mssql+pyodbc://usuario:senha@servidor/AdventureWorks2016"
    "?driver=ODBC+Driver+17+for+SQL+Server",
)
DW_CONN_STR = os.getenv(
    "DW_CONN_STR",
    "postgresql+psycopg2://dw_user:dw_pass@localhost:5432/adventureworks_dw",
)

src_engine = create_engine(SRC_CONN_STR)
dw_engine = create_engine(DW_CONN_STR)


# ---------------------------------------------------------------------------
# Utilidades de controle (watermark / log)
# ---------------------------------------------------------------------------
def get_watermark(table_name: str, full_load: bool) -> datetime:
    if full_load:
        return datetime(1900, 1, 1)
    with dw_engine.connect() as conn:
        row = conn.execute(
            text("SELECT ultima_extracao_em FROM ctrl.marca_agua_etl WHERE tabela_origem = :t"),
            {"t": table_name},
        ).fetchone()
        if row:
            return row[0]
        conn.execute(
            text(
                "INSERT INTO ctrl.marca_agua_etl (tabela_origem, ultima_extracao_em) "
                "VALUES (:t, '1900-01-01') ON CONFLICT (tabela_origem) DO NOTHING"
            ),
            {"t": table_name},
        )
        conn.commit()
        return datetime(1900, 1, 1)


def set_watermark(table_name: str, new_ts: datetime, status: str, rows: int):
    with dw_engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ctrl.marca_agua_etl
                    (tabela_origem, ultima_extracao_em, ultima_exec_iniciada,
                     ultima_exec_finalizada, status_ultima_exec, linhas_processadas)
                VALUES (:t, :ts, :ts, now(), :status, :rows)
                ON CONFLICT (tabela_origem) DO UPDATE SET
                    ultima_extracao_em = EXCLUDED.ultima_extracao_em,
                    ultima_exec_finalizada = now(),
                    status_ultima_exec = EXCLUDED.status_ultima_exec,
                    linhas_processadas = EXCLUDED.linhas_processadas
                """
            ),
            {"t": table_name, "ts": new_ts, "status": status, "rows": rows},
        )
        conn.commit()


def log_step(process: str, step: str, status: str, rows: int, message: str = ""):
    with dw_engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ctrl.log_etl (nome_processo, nome_etapa, finalizado_em, status, linhas_afetadas, mensagem)
                VALUES (:p, :s, now(), :st, :r, :m)
                """
            ),
            {"p": process, "s": step, "st": status, "r": rows, "m": message},
        )
        conn.commit()


def row_hash(*values) -> str:
    """Gera hash MD5 dos atributos rastreados para detectar mudanças (SCD2)."""
    raw = "|".join("" if v is None else str(v) for v in values)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1) EXTRAÇÃO -> STAGING (incremental por ModifiedDate)
# ---------------------------------------------------------------------------
EXTRACT_QUERIES = {
    "cliente": """
        SELECT c.CustomerID AS id_cliente,
               p.FirstName + ' ' + p.LastName AS nome_pessoa,
               s.Name AS nome_loja,
               CASE WHEN c.StoreID IS NOT NULL THEN 'Store' ELSE 'Individual' END AS tipo_cliente,
               a.City AS cidade, sp.Name AS estado_provincia, cr.Name AS pais_regiao,
               a.PostalCode AS codigo_postal, c.ModifiedDate AS data_modificacao
        FROM Sales.Customer c
        LEFT JOIN Person.Person p ON p.BusinessEntityID = c.PersonID
        LEFT JOIN Sales.Store s ON s.BusinessEntityID = c.StoreID
        LEFT JOIN Person.BusinessEntityAddress bea ON bea.BusinessEntityID = c.PersonID
        LEFT JOIN Person.Address a ON a.AddressID = bea.AddressID
        LEFT JOIN Person.StateProvince sp ON sp.StateProvinceID = a.StateProvinceID
        LEFT JOIN Person.CountryRegion cr ON cr.CountryRegionCode = sp.CountryRegionCode
        WHERE c.ModifiedDate > :watermark
    """,
    "produto": """
        SELECT p.ProductID AS id_produto, p.Name AS nome_produto, p.ProductNumber AS numero_produto,
               p.Color AS cor, p.Size AS tamanho, psc.Name AS nome_subcategoria, pc.Name AS nome_categoria,
               p.StandardCost AS custo_padrao, p.ListPrice AS preco_tabela, p.ModifiedDate AS data_modificacao
        FROM Production.Product p
        LEFT JOIN Production.ProductSubcategory psc ON psc.ProductSubcategoryID = p.ProductSubcategoryID
        LEFT JOIN Production.ProductCategory pc ON pc.ProductCategoryID = psc.ProductCategoryID
        WHERE p.ModifiedDate > :watermark
    """,
    "vendedor": """
        SELECT sp.BusinessEntityID AS id_funcionario, per.FirstName + ' ' + per.LastName AS nome_completo,
               e.JobTitle AS cargo, sp.ModifiedDate AS data_modificacao
        FROM Sales.SalesPerson sp
        JOIN HumanResources.Employee e ON e.BusinessEntityID = sp.BusinessEntityID
        JOIN Person.Person per ON per.BusinessEntityID = sp.BusinessEntityID
        WHERE sp.ModifiedDate > :watermark
    """,
    "territorio": """
        SELECT TerritoryID AS id_territorio, Name AS nome_territorio,
               CountryRegionCode AS codigo_pais_regiao, [Group] AS grupo_territorio, ModifiedDate AS data_modificacao
        FROM Sales.SalesTerritory
        WHERE ModifiedDate > :watermark
    """,
    "oferta_especial": """
        SELECT SpecialOfferID AS id_oferta_especial, Description AS descricao,
               DiscountPct AS percentual_desconto, Type AS tipo_promocao, Category AS categoria_promocao,
               StartDate AS data_inicio, EndDate AS data_fim, ModifiedDate AS data_modificacao
        FROM Sales.SpecialOffer
        WHERE ModifiedDate > :watermark
    """,
    "metodo_envio": """
        SELECT ShipMethodID AS id_metodo_envio, Name AS nome, ShipBase AS base_envio,
               ShipRate AS taxa_envio, ModifiedDate AS data_modificacao
        FROM Purchasing.ShipMethod
        WHERE ModifiedDate > :watermark
    """,
    "detalhe_pedido_venda": """
        SELECT sod.SalesOrderDetailID AS id_detalhe_pedido, soh.SalesOrderNumber AS numero_pedido_venda,
               sod.SalesOrderDetailID AS numero_linha_pedido,
               soh.OrderDate AS data_pedido, soh.ShipDate AS data_envio, soh.DueDate AS data_vencimento,
               soh.CustomerID AS id_cliente, sod.ProductID AS id_produto, soh.SalesPersonID AS id_funcionario,
               soh.TerritoryID AS id_territorio, sod.SpecialOfferID AS id_oferta_especial,
               soh.ShipMethodID AS id_metodo_envio, sod.OrderQty AS quantidade_pedido, sod.UnitPrice AS preco_unitario,
               sod.UnitPriceDiscount AS desconto_preco_unitario, sod.LineTotal AS total_linha,
               soh.TaxAmt * (sod.LineTotal / NULLIF(soh.SubTotal, 0)) AS valor_imposto,
               soh.Freight * (sod.LineTotal / NULLIF(soh.SubTotal, 0)) AS frete,
               sod.ModifiedDate AS data_modificacao
        FROM Sales.SalesOrderDetail sod
        JOIN Sales.SalesOrderHeader soh ON soh.SalesOrderID = sod.SalesOrderID
        WHERE sod.ModifiedDate > :watermark
    """,
}


def extract_to_staging(table_name: str, full_load: bool) -> tuple[int, datetime | None]:
    watermark = get_watermark(table_name, full_load)
    log.info(f"[EXTRACT] {table_name}: extraindo registros com ModifiedDate > {watermark}")

    df = pd.read_sql(text(EXTRACT_QUERIES[table_name]), src_engine, params={"watermark": watermark})
    if df.empty:
        log.info(f"[EXTRACT] {table_name}: nenhum registro novo/alterado.")
        return 0, None

    with dw_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE stg.{table_name}"))
        df.to_sql(table_name, conn, schema="stg", if_exists="append", index=False)

    new_watermark = df["data_modificacao"].max()
    log.info(f"[EXTRACT] {table_name}: {len(df)} linhas -> stg.{table_name} (novo watermark {new_watermark})")
    return len(df), new_watermark


# ---------------------------------------------------------------------------
# 2) CARGA DE DIMENSÕES
# ---------------------------------------------------------------------------
def load_dim_scd2(table: str, bk_col: str, attr_cols: list[str], stg_table: str):
    """Aplica SCD Tipo 2: expira a versão vigente e insere uma nova quando há mudança."""
    with dw_engine.begin() as conn:
        staged = pd.read_sql(text(f"SELECT * FROM stg.{stg_table}"), conn)
        if staged.empty:
            return 0
        today = datetime.now().date()
        n_changed = 0
        for _, r in staged.iterrows():
            new_hash = row_hash(*[r[c] for c in attr_cols])
            current = conn.execute(
                text(
                    f"SELECT {table.split('.')[-1]}_key, hash_linha FROM {table} "
                    f"WHERE {bk_col} = :bk AND eh_vigente = TRUE"
                ),
                {"bk": r[bk_col]},
            ).fetchone()

            if current is None:
                cols = ", ".join([bk_col] + attr_cols + ["hash_linha", "data_efetiva"])
                placeholders = ", ".join([f":{c}" for c in attr_cols] + [":bk", ":h", ":eff"])
                conn.execute(
                    text(
                        f"INSERT INTO {table} ({bk_col}, {', '.join(attr_cols)}, hash_linha, data_efetiva) "
                        f"VALUES (:bk, {', '.join(f':{c}' for c in attr_cols)}, :h, :eff)"
                    ),
                    {**{c: r[c] for c in attr_cols}, "bk": r[bk_col], "h": new_hash, "eff": today},
                )
                n_changed += 1
            elif current.hash_linha != new_hash:
                conn.execute(
                    text(f"UPDATE {table} SET data_fim = :d, eh_vigente = FALSE WHERE {bk_col.split('_')[0]}_key = :k"),
                    {"d": today, "k": current[0]},
                )
                conn.execute(
                    text(
                        f"INSERT INTO {table} ({bk_col}, {', '.join(attr_cols)}, hash_linha, data_efetiva) "
                        f"VALUES (:bk, {', '.join(f':{c}' for c in attr_cols)}, :h, :eff)"
                    ),
                    {**{c: r[c] for c in attr_cols}, "bk": r[bk_col], "h": new_hash, "eff": today},
                )
                n_changed += 1
        return n_changed


def load_dim_scd1(table: str, bk_col: str, attr_cols: list[str], stg_table: str):
    """Aplica SCD Tipo 1 (UPSERT) para dimensões de baixa volatilidade."""
    with dw_engine.begin() as conn:
        staged = pd.read_sql(text(f"SELECT * FROM stg.{stg_table}"), conn)
        if staged.empty:
            return 0
        set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in attr_cols])
        cols = ", ".join([bk_col] + attr_cols)
        vals_placeholder = ", ".join([f":{c}" for c in [bk_col] + attr_cols])
        for _, r in staged.iterrows():
            conn.execute(
                text(
                    f"INSERT INTO {table} ({cols}) VALUES ({vals_placeholder}) "
                    f"ON CONFLICT ({bk_col}) DO UPDATE SET {set_clause}"
                ),
                {c: r[c] for c in [bk_col] + attr_cols},
            )
        return len(staged)


# ---------------------------------------------------------------------------
# 3) CARGA DO FATO (UPSERT idempotente pela chave natural)
# ---------------------------------------------------------------------------
def load_fact_sales():
    with dw_engine.begin() as conn:
        staged = pd.read_sql(text("SELECT * FROM stg.detalhe_pedido_venda"), conn)
        if staged.empty:
            return 0

        insert_sql = text(
            """
            INSERT INTO dw.fato_vendas (
                chave_data_pedido, chave_data_envio, chave_data_vencimento, chave_cliente, chave_produto,
                chave_vendedor, chave_territorio, chave_promocao, chave_metodo_envio,
                numero_pedido_venda, numero_linha_pedido, id_detalhe_pedido,
                quantidade_pedido, preco_unitario, desconto_preco_unitario, valor_desconto, total_linha,
                custo_padrao, valor_imposto, frete, data_modificacao_origem
            )
            SELECT
                TO_CHAR(:data_pedido::date, 'YYYYMMDD')::int,
                CASE WHEN :data_envio IS NULL THEN NULL ELSE TO_CHAR(:data_envio::date, 'YYYYMMDD')::int END,
                CASE WHEN :data_vencimento IS NULL THEN NULL ELSE TO_CHAR(:data_vencimento::date, 'YYYYMMDD')::int END,
                COALESCE((SELECT chave_cliente FROM dw.dim_cliente
                          WHERE id_cliente = :id_cliente AND eh_vigente), -1),
                COALESCE((SELECT chave_produto FROM dw.dim_produto
                          WHERE id_produto = :id_produto AND eh_vigente), -1),
                COALESCE((SELECT chave_vendedor FROM dw.dim_vendedor
                          WHERE id_funcionario = :id_funcionario AND eh_vigente), -1),
                COALESCE((SELECT chave_territorio FROM dw.dim_territorio
                          WHERE id_territorio = :id_territorio), -1),
                COALESCE((SELECT chave_promocao FROM dw.dim_promocao
                          WHERE id_oferta_especial = :id_oferta_especial), -1),
                COALESCE((SELECT chave_metodo_envio FROM dw.dim_metodo_envio
                          WHERE id_metodo_envio = :id_metodo_envio), -1),
                :numero_pedido_venda, :numero_linha_pedido, :id_detalhe_pedido,
                :quantidade_pedido, :preco_unitario, :desconto_preco_unitario,
                (:preco_unitario * :quantidade_pedido * :desconto_preco_unitario),
                :total_linha, (SELECT custo_padrao FROM dw.dim_produto
                              WHERE id_produto = :id_produto AND eh_vigente),
                :valor_imposto, :frete, :data_modificacao
            ON CONFLICT (id_detalhe_pedido) DO UPDATE SET
                quantidade_pedido = EXCLUDED.quantidade_pedido,
                preco_unitario = EXCLUDED.preco_unitario,
                desconto_preco_unitario = EXCLUDED.desconto_preco_unitario,
                valor_desconto = EXCLUDED.valor_desconto,
                total_linha = EXCLUDED.total_linha,
                valor_imposto = EXCLUDED.valor_imposto,
                frete = EXCLUDED.frete,
                data_modificacao_origem = EXCLUDED.data_modificacao_origem,
                marca_tempo_carregamento = now()
            """
        )
        for _, r in staged.iterrows():
            conn.execute(insert_sql, r.to_dict())
        return len(staged)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
DIM_JOBS = [
    dict(name="cliente", table="dw.dim_cliente", bk="id_cliente",
         attrs=["nome_cliente", "tipo_cliente", "cidade", "estado_provincia", "pais_regiao", "codigo_postal"],
         scd_type=2),
    dict(name="produto", table="dw.dim_produto", bk="id_produto",
         attrs=["nome_produto", "numero_produto", "cor", "tamanho", "nome_subcategoria",
                "nome_categoria", "custo_padrao", "preco_tabela"], scd_type=2),
    dict(name="vendedor", table="dw.dim_vendedor", bk="id_funcionario",
         attrs=["nome_completo", "cargo"], scd_type=2),
    dict(name="territorio", table="dw.dim_territorio", bk="id_territorio",
         attrs=["nome_territorio", "codigo_pais_regiao", "grupo_territorio"], scd_type=1),
    dict(name="oferta_especial", table="dw.dim_promocao", bk="id_oferta_especial",
         attrs=["descricao", "percentual_desconto", "tipo_promocao", "categoria_promocao",
                "data_inicio", "data_fim"], scd_type=1),
    dict(name="metodo_envio", table="dw.dim_metodo_envio", bk="id_metodo_envio",
         attrs=["nome", "base_envio", "taxa_envio"], scd_type=1),
]


def run(full_load: bool = False):
    log.info("========== INÍCIO DA ETL INCREMENTAL - AdventureWorks DW ==========")

    # 1. Extração das dimensões + fato para staging
    watermarks = {}
    for job in DIM_JOBS:
        rows, wm = extract_to_staging(job["name"], full_load)
        watermarks[job["name"]] = (rows, wm)

    fact_rows, fact_wm = extract_to_staging("detalhe_pedido_venda", full_load)
    watermarks["detalhe_pedido_venda"] = (fact_rows, fact_wm)

    # 2. Carga das dimensões (deve ocorrer ANTES do fato, para resolver as FKs)
    for job in DIM_JOBS:
        rows, wm = watermarks[job["name"]]
        if rows == 0:
            continue
        if job["scd_type"] == 2:
            n = load_dim_scd2(job["table"], job["bk"], job["attrs"], job["name"])
        else:
            n = load_dim_scd1(job["table"], job["bk"], job["attrs"], job["name"])
        log.info(f"[LOAD DIM] {job['table']}: {n} linhas aplicadas (SCD{job['scd_type']})")
        set_watermark(job["name"], wm, "SUCCESS", rows)
        log_step("etl_incremental", f"load_dim_{job['name']}", "SUCCESS", n)

    # 3. Carga do fato
    rows, wm = watermarks["detalhe_pedido_venda"]
    if rows > 0:
        n = load_fact_sales()
        log.info(f"[LOAD FACT] dw.fato_vendas: {n} linhas processadas (upsert)")
        set_watermark("detalhe_pedido_venda", wm, "SUCCESS", rows)
        log_step("etl_incremental", "load_fato_vendas", "SUCCESS", n)

    log.info("========== FIM DA ETL INCREMENTAL ==========")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL incremental AdventureWorks -> DW PostgreSQL")
    parser.add_argument("--full-load", action="store_true", help="Ignora watermark e recarrega tudo")
    args = parser.parse_args()
    run(full_load=args.full_load)
