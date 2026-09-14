import argparse
import hashlib
import logging
import os
from datetime import datetime, date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("etl_adventureworks")


SRC_CONN_STR = os.getenv(
    "SRC_CONN_STR",
    "mssql+pyodbc://usuario:senha@servidor/AdventureWorks2016"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&TrustServerCertificate=yes",
)

DW_CONN_STR = os.getenv(
    "DW_CONN_STR",
    "postgresql+psycopg2://postgres@localhost:5439/adventureworks_dw",
)


src_engine = create_engine(SRC_CONN_STR)
dw_engine = create_engine(DW_CONN_STR)


# ============================================================
# WATERMARK
# ============================================================

def get_watermark(table_name: str, full_load: bool) -> datetime:
    """
    Recupera o último ModifiedDate processado.

    Se --full-load estiver ativo, começa em 1900-01-01.
    """

    if full_load:
        return datetime(1900, 1, 1)

    with dw_engine.begin() as conn:

        row = conn.execute(
            text(
                """
                SELECT ultima_extracao_em
                FROM ctrl.marca_agua_etl
                WHERE tabela_origem = :t
                """
            ),
            {"t": table_name},
        ).fetchone()

        if row:
            return row[0]

        conn.execute(
            text(
                """
                INSERT INTO ctrl.marca_agua_etl
                    (tabela_origem, ultima_extracao_em)
                VALUES
                    (:t, '1900-01-01')
                ON CONFLICT (tabela_origem)
                DO NOTHING
                """
            ),
            {"t": table_name},
        )

        return datetime(1900, 1, 1)


def set_watermark(
    table_name: str,
    new_ts: datetime,
    status: str,
    rows: int,
):
    """
    Atualiza o watermark somente depois que a carga foi concluída.
    """

    with dw_engine.begin() as conn:

        conn.execute(
            text(
                """
                INSERT INTO ctrl.marca_agua_etl
                    (
                        tabela_origem,
                        ultima_extracao_em,
                        ultima_exec_iniciada,
                        ultima_exec_finalizada,
                        status_ultima_exec,
                        linhas_processadas
                    )
                VALUES
                    (
                        :t,
                        :ts,
                        now(),
                        now(),
                        :status,
                        :rows
                    )
                ON CONFLICT (tabela_origem)
                DO UPDATE SET
                    ultima_extracao_em = EXCLUDED.ultima_extracao_em,
                    ultima_exec_finalizada = now(),
                    status_ultima_exec = EXCLUDED.status_ultima_exec,
                    linhas_processadas = EXCLUDED.linhas_processadas
                """
            ),
            {
                "t": table_name,
                "ts": new_ts,
                "status": status,
                "rows": rows,
            },
        )


# ============================================================
# LOG
# ============================================================

def log_step(
    process: str,
    step: str,
    status: str,
    rows: int = 0,
    message: str = "",
):
    """
    Registra cada etapa no controle do ETL.
    """

    with dw_engine.begin() as conn:

        conn.execute(
            text(
                """
                INSERT INTO ctrl.log_etl
                    (
                        nome_processo,
                        nome_etapa,
                        finalizado_em,
                        status,
                        linhas_afetadas,
                        mensagem
                    )
                VALUES
                    (
                        :p,
                        :s,
                        now(),
                        :st,
                        :r,
                        :m
                    )
                """
            ),
            {
                "p": process,
                "s": step,
                "st": status,
                "r": rows,
                "m": message,
            },
        )


# ============================================================
# HASH PARA SCD2
# ============================================================

def row_hash(*values) -> str:
    """
    Gera hash MD5 dos atributos monitorados.

    O hash é utilizado para descobrir se uma dimensão
    sofreu alteração.
    """

    raw = "|".join(
        "" if pd.isna(v) else str(v)
        for v in values
    )

    return hashlib.md5(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# QUERIES DE EXTRAÇÃO
# ============================================================

EXTRACT_QUERIES = {

    # --------------------------------------------------------
    # CLIENTE
    # --------------------------------------------------------

    "cliente": """
        SELECT
            id_cliente,
            nome_cliente,
            nome_loja,
            tipo_cliente,
            cidade,
            estado_provincia,
            pais_regiao,
            codigo_postal,
            data_modificacao
        FROM
        (
            SELECT
                c.CustomerID AS id_cliente,

                COALESCE(
                    p.FirstName + ' ' + p.LastName,
                    s.Name,
                    'Cliente desconhecido'
                ) AS nome_cliente,

                s.Name AS nome_loja,

                CASE
                    WHEN c.StoreID IS NOT NULL
                        THEN 'Store'
                    ELSE 'Individual'
                END AS tipo_cliente,

                a.City AS cidade,
                sp.Name AS estado_provincia,
                cr.Name AS pais_regiao,
                a.PostalCode AS codigo_postal,

                c.ModifiedDate AS data_modificacao,

                ROW_NUMBER() OVER
                (
                    PARTITION BY c.CustomerID
                    ORDER BY
                        CASE
                            WHEN bea.AddressID IS NULL THEN 1
                            ELSE 0
                        END,
                        bea.AddressID
                ) AS rn

            FROM Sales.Customer c

            LEFT JOIN Person.Person p
                ON p.BusinessEntityID = c.PersonID

            LEFT JOIN Sales.Store s
                ON s.BusinessEntityID = c.StoreID

            LEFT JOIN Person.BusinessEntityAddress bea
                ON bea.BusinessEntityID = c.PersonID

            LEFT JOIN Person.Address a
                ON a.AddressID = bea.AddressID

            LEFT JOIN Person.StateProvince sp
                ON sp.StateProvinceID = a.StateProvinceID

            LEFT JOIN Person.CountryRegion cr
                ON cr.CountryRegionCode = sp.CountryRegionCode

            WHERE
                c.ModifiedDate > :watermark
        ) cliente

        WHERE rn = 1
    """,


    # --------------------------------------------------------
    # PRODUTO
    # --------------------------------------------------------

    "produto": """
        SELECT
            p.ProductID AS id_produto,
            p.Name AS nome_produto,
            p.ProductNumber AS numero_produto,
            p.Color AS cor,
            p.Size AS tamanho,
            psc.Name AS nome_subcategoria,
            pc.Name AS nome_categoria,
            p.StandardCost AS custo_padrao,
            p.ListPrice AS preco_tabela,
            p.ModifiedDate AS data_modificacao

        FROM Production.Product p

        LEFT JOIN Production.ProductSubcategory psc
            ON psc.ProductSubcategoryID =
               p.ProductSubcategoryID

        LEFT JOIN Production.ProductCategory pc
            ON pc.ProductCategoryID =
               psc.ProductCategoryID

        WHERE
            p.ModifiedDate > :watermark
    """,


    # --------------------------------------------------------
    # VENDEDOR
    # --------------------------------------------------------

    "vendedor": """
        SELECT
            sp.BusinessEntityID AS id_funcionario,

            per.FirstName + ' ' + per.LastName
                AS nome_completo,

            e.JobTitle AS cargo,

            CASE
                WHEN sp.ModifiedDate >= e.ModifiedDate
                    THEN sp.ModifiedDate
                ELSE e.ModifiedDate
            END AS data_modificacao

        FROM Sales.SalesPerson sp

        JOIN HumanResources.Employee e
            ON e.BusinessEntityID =
               sp.BusinessEntityID

        JOIN Person.Person per
            ON per.BusinessEntityID =
               sp.BusinessEntityID

        WHERE
            sp.ModifiedDate > :watermark
            OR e.ModifiedDate > :watermark
    """,


    # --------------------------------------------------------
    # TERRITÓRIO
    # --------------------------------------------------------

    "territorio": """
        SELECT
            TerritoryID AS id_territorio,
            Name AS nome_territorio,
            CountryRegionCode AS codigo_pais_regiao,
            [Group] AS grupo_territorio,
            ModifiedDate AS data_modificacao

        FROM Sales.SalesTerritory

        WHERE
            ModifiedDate > :watermark
    """,


    # --------------------------------------------------------
    # PROMOÇÃO
    # --------------------------------------------------------

    "oferta_especial": """
        SELECT
            SpecialOfferID AS id_oferta_especial,
            Description AS descricao,
            DiscountPct AS percentual_desconto,
            Type AS tipo_promocao,
            Category AS categoria_promocao,
            StartDate AS data_inicio,
            EndDate AS data_fim,
            ModifiedDate AS data_modificacao

        FROM Sales.SpecialOffer

        WHERE
            ModifiedDate > :watermark
    """,


    # --------------------------------------------------------
    # MÉTODO DE ENVIO
    # --------------------------------------------------------

    "metodo_envio": """
        SELECT
            ShipMethodID AS id_metodo_envio,
            Name AS nome,
            ShipBase AS base_envio,
            ShipRate AS taxa_envio,
            ModifiedDate AS data_modificacao

        FROM Purchasing.ShipMethod

        WHERE
            ModifiedDate > :watermark
    """,


    # --------------------------------------------------------
    # FATO DE VENDAS
    # --------------------------------------------------------

    "detalhe_pedido_venda": """
        SELECT

            sod.SalesOrderDetailID
                AS id_detalhe_pedido,

            soh.SalesOrderNumber
                AS numero_pedido_venda,

            sod.SalesOrderDetailID
                AS numero_linha_pedido,

            soh.OrderDate
                AS data_pedido,

            soh.ShipDate
                AS data_envio,

            soh.DueDate
                AS data_vencimento,

            soh.CustomerID
                AS id_cliente,

            sod.ProductID
                AS id_produto,

            soh.SalesPersonID
                AS id_funcionario,

            soh.TerritoryID
                AS id_territorio,

            sod.SpecialOfferID
                AS id_oferta_especial,

            soh.ShipMethodID
                AS id_metodo_envio,

            sod.OrderQty
                AS quantidade_pedido,

            sod.UnitPrice
                AS preco_unitario,

            sod.UnitPriceDiscount
                AS desconto_preco_unitario,

            sod.LineTotal
                AS total_linha,

            CASE
                WHEN soh.SubTotal = 0
                    THEN 0
                ELSE
                    soh.TaxAmt *
                    (
                        sod.LineTotal /
                        NULLIF(soh.SubTotal, 0)
                    )
            END AS valor_imposto,

            CASE
                WHEN soh.SubTotal = 0
                    THEN 0
                ELSE
                    soh.Freight *
                    (
                        sod.LineTotal /
                        NULLIF(soh.SubTotal, 0)
                    )
            END AS frete,

            CASE
                WHEN sod.ModifiedDate >= soh.ModifiedDate
                    THEN sod.ModifiedDate
                ELSE soh.ModifiedDate
            END AS data_modificacao

        FROM Sales.SalesOrderDetail sod

        JOIN Sales.SalesOrderHeader soh
            ON soh.SalesOrderID =
               sod.SalesOrderID

        WHERE
            sod.ModifiedDate > :watermark
            OR soh.ModifiedDate > :watermark
    """,
}


# ============================================================
# EXTRAÇÃO → STAGING
# ============================================================

def extract_to_staging(
    table_name: str,
    full_load: bool,
) -> tuple[int, datetime | None]:

    watermark = get_watermark(
        table_name,
        full_load
    )

    log.info(
        f"[EXTRACT] {table_name}: "
        f"extraindo registros com ModifiedDate > {watermark}"
    )

    try:

        df = pd.read_sql(
            text(EXTRACT_QUERIES[table_name]),
            src_engine,
            params={
                "watermark": watermark
            },
        )

        if df.empty:

            log.info(
                f"[EXTRACT] {table_name}: "
                f"nenhum registro novo/alterado."
            )

            return 0, None

        # ----------------------------------------------------
        # Proteção contra duplicidade no staging
        # ----------------------------------------------------

        if table_name == "cliente":

            df = df.drop_duplicates(
                subset=["id_cliente"],
                keep="last",
            )

        elif table_name == "produto":

            df = df.drop_duplicates(
                subset=["id_produto"],
                keep="last",
            )

        elif table_name == "vendedor":

            df = df.drop_duplicates(
                subset=["id_funcionario"],
                keep="last",
            )

        elif table_name == "territorio":

            df = df.drop_duplicates(
                subset=["id_territorio"],
                keep="last",
            )

        elif table_name == "oferta_especial":

            df = df.drop_duplicates(
                subset=["id_oferta_especial"],
                keep="last",
            )

        elif table_name == "metodo_envio":

            df = df.drop_duplicates(
                subset=["id_metodo_envio"],
                keep="last",
            )

        elif table_name == "detalhe_pedido_venda":

            df = df.drop_duplicates(
                subset=["id_detalhe_pedido"],
                keep="last",
            )

        # ----------------------------------------------------
        # STAGING
        # ----------------------------------------------------

        with dw_engine.begin() as conn:

            conn.execute(
                text(
                    f"TRUNCATE TABLE stg.{table_name}"
                )
            )

            df.to_sql(
                table_name,
                conn,
                schema="stg",
                if_exists="append",
                index=False,
            )

        new_watermark = df[
            "data_modificacao"
        ].max()

        log.info(
            f"[EXTRACT] {table_name}: "
            f"{len(df)} linhas -> stg.{table_name} "
            f"(novo watermark {new_watermark})"
        )

        log_step(
            "etl_incremental",
            f"extract_{table_name}",
            "SUCCESS",
            len(df),
        )

        return len(df), new_watermark

    except Exception as e:

        log.exception(
            f"[EXTRACT] Erro em {table_name}"
        )

        log_step(
            "etl_incremental",
            f"extract_{table_name}",
            "ERROR",
            0,
            str(e),
        )

        raise


# ============================================================
# SCD TIPO 2
# ============================================================

def load_dim_scd2(
    table: str,
    pk_col: str,
    bk_col: str,
    attr_cols: list[str],
    stg_table: str,
):
    """
    Carga SCD Tipo 2.

    - Se não existir → INSERT
    - Se hash for igual → não faz nada
    - Se hash mudar → encerra versão anterior e cria nova
    - Se houver alteração no mesmo dia → atualiza a versão atual
    """

    with dw_engine.begin() as conn:

        staged = pd.read_sql(
            text(
                f"SELECT * FROM stg.{stg_table}"
            ),
            conn,
        )

        if staged.empty:
            return 0

        # Proteção adicional contra duplicidade
        staged = staged.drop_duplicates(
            subset=[bk_col],
            keep="last",
        )

        hoje = datetime.now().date()

        n_changed = 0

        for _, r in staged.iterrows():

            novo_hash = row_hash(
                *[
                    r[c]
                    for c in attr_cols
                ]
            )

            current = conn.execute(
                text(
                    f"""
                    SELECT
                        {pk_col},
                        hash_linha,
                        data_efetiva

                    FROM {table}

                    WHERE
                        {bk_col} = :bk
                        AND eh_vigente = TRUE

                    LIMIT 1
                    """
                ),
                {
                    "bk": r[bk_col]
                },
            ).fetchone()

            # ------------------------------------------------
            # REGISTRO NOVO
            # ------------------------------------------------

            if current is None:

                conn.execute(
                    text(
                        f"""
                        INSERT INTO {table}
                        (
                            {bk_col},
                            {', '.join(attr_cols)},
                            hash_linha,
                            data_efetiva,
                            data_fim,
                            eh_vigente
                        )
                        VALUES
                        (
                            :bk,
                            {', '.join(f':{c}' for c in attr_cols)},
                            :h,
                            :eff,
                            NULL,
                            TRUE
                        )
                        """
                    ),
                    {
                        **{
                            c: r[c]
                            for c in attr_cols
                        },
                        "bk": r[bk_col],
                        "h": novo_hash,
                        "eff": hoje,
                    },
                )

                n_changed += 1

                continue

            # ------------------------------------------------
            # REGISTRO EXISTENTE SEM ALTERAÇÃO
            # ------------------------------------------------

            if current.hash_linha == novo_hash:

                continue

            chave_substituta = current[0]
            data_efetiva_atual = current[2]

            # ------------------------------------------------
            # ALTERAÇÃO NO MESMO DIA
            # ------------------------------------------------
            #
            # Evita:
            #
            # UNIQUE(id_cliente, data_efetiva)
            #
            # quando duas versões são processadas no mesmo dia.
            # ------------------------------------------------

            if data_efetiva_atual == hoje:

                conn.execute(
                    text(
                        f"""
                        UPDATE {table}

                        SET
                            {', '.join(
                                f'{c} = :{c}'
                                for c in attr_cols
                            )},
                            hash_linha = :h

                        WHERE
                            {pk_col} = :k
                        """
                    ),
                    {
                        **{
                            c: r[c]
                            for c in attr_cols
                        },
                        "h": novo_hash,
                        "k": chave_substituta,
                    },
                )

                n_changed += 1

                continue

            # ------------------------------------------------
            # NOVA VERSÃO HISTÓRICA
            # ------------------------------------------------

            conn.execute(
                text(
                    f"""
                    UPDATE {table}

                    SET
                        data_fim = :d,
                        eh_vigente = FALSE

                    WHERE
                        {pk_col} = :k
                    """
                ),
                {
                    "d": hoje,
                    "k": chave_substituta,
                },
            )

            conn.execute(
                text(
                    f"""
                    INSERT INTO {table}
                    (
                        {bk_col},
                        {', '.join(attr_cols)},
                        hash_linha,
                        data_efetiva,
                        data_fim,
                        eh_vigente
                    )
                    VALUES
                    (
                        :bk,
                        {', '.join(f':{c}' for c in attr_cols)},
                        :h,
                        :eff,
                        NULL,
                        TRUE
                    )
                    """
                ),
                {
                    **{
                        c: r[c]
                        for c in attr_cols
                    },
                    "bk": r[bk_col],
                    "h": novo_hash,
                    "eff": hoje,
                },
            )

            n_changed += 1

        return n_changed


# ============================================================
# SCD TIPO 1
# ============================================================

def load_dim_scd1(
    table: str,
    bk_col: str,
    attr_cols: list[str],
    stg_table: str,
):
    """
    SCD Tipo 1 utilizando UPSERT.
    """

    with dw_engine.begin() as conn:

        staged = pd.read_sql(
            text(
                f"SELECT * FROM stg.{stg_table}"
            ),
            conn,
        )

        if staged.empty:
            return 0

        staged = staged.drop_duplicates(
            subset=[bk_col],
            keep="last",
        )

        set_clause = ", ".join(
            [
                f"{c} = EXCLUDED.{c}"
                for c in attr_cols
            ]
        )

        cols = ", ".join(
            [bk_col] + attr_cols
        )

        vals_placeholder = ", ".join(
            [
                f":{c}"
                for c in [bk_col] + attr_cols
            ]
        )

        for _, r in staged.iterrows():

            conn.execute(
                text(
                    f"""
                    INSERT INTO {table}
                    (
                        {cols}
                    )
                    VALUES
                    (
                        {vals_placeholder}
                    )

                    ON CONFLICT ({bk_col})
                    DO UPDATE SET
                        {set_clause}
                    """
                ),
                {
                    c: r[c]
                    for c in [bk_col] + attr_cols
                },
            )

        return len(staged)


# ============================================================
# DIMENSÃO DATA
# ============================================================

def load_dim_date(staged: pd.DataFrame):
    """
    Garante que todas as datas utilizadas pela fato
    existam na dimensão calendário.

    A tabela dim_data precisa possuir pelo menos:
        chave_data
        data_completa
    """

    if staged.empty:
        return 0

    datas = []

    for coluna in [
        "data_pedido",
        "data_envio",
        "data_vencimento",
    ]:

        if coluna in staged.columns:

            valores = pd.to_datetime(
                staged[coluna],
                errors="coerce",
            ).dt.date

            datas.extend(
                [
                    d
                    for d in valores
                    if pd.notna(d)
                ]
            )

    if not datas:
        return 0

    data_min = min(datas)
    data_max = max(datas)

    total = 0

    with dw_engine.begin() as conn:

        data_atual = data_min

        while data_atual <= data_max:

            chave = int(
                data_atual.strftime("%Y%m%d")
            )

            conn.execute(
                text(
                    """
                    INSERT INTO dw.dim_data
                    (
                        chave_data,
                        data_completa
                    )
                    VALUES
                    (
                        :chave,
                        :data
                    )

                    ON CONFLICT (chave_data)
                    DO NOTHING
                    """
                ),
                {
                    "chave": chave,
                    "data": data_atual,
                },
            )

            total += 1

            data_atual += timedelta(days=1)

    log.info(
        f"[LOAD DIM] dw.dim_data: "
        f"{total} datas verificadas"
    )

    return total


# ============================================================
# FATO DE VENDAS
# ============================================================

def load_fact_sales():
    """
    Carrega a fato de vendas utilizando UPSERT.

    A chave natural da fato é:
        id_detalhe_pedido
    """

    with dw_engine.begin() as conn:

        staged = pd.read_sql(
            text(
                """
                SELECT *
                FROM stg.detalhe_pedido_venda
                """
            ),
            conn,
        )

        if staged.empty:
            return 0

        staged = staged.drop_duplicates(
            subset=["id_detalhe_pedido"],
            keep="last",
        )

        # ----------------------------------------------------
        # Garante que a dimensão calendário exista
        # ----------------------------------------------------

        load_dim_date(staged)

        insert_sql = text(
            """
            INSERT INTO dw.fato_vendas
            (
                chave_data_pedido,
                chave_data_envio,
                chave_data_vencimento,

                chave_cliente,
                chave_produto,
                chave_vendedor,
                chave_territorio,
                chave_promocao,
                chave_metodo_envio,

                numero_pedido_venda,
                numero_linha_pedido,
                id_detalhe_pedido,

                quantidade_pedido,
                preco_unitario,
                desconto_preco_unitario,
                valor_desconto,
                total_linha,

                custo_padrao,
                valor_imposto,
                frete,

                data_modificacao_origem
            )

            SELECT

                -- DATA DO PEDIDO
                CAST(
                    TO_CHAR(
                        CAST(:data_pedido AS DATE),
                        'YYYYMMDD'
                    )
                    AS INTEGER
                ),

                -- DATA DE ENVIO
                CASE
                    WHEN :data_envio IS NULL
                        THEN NULL
                    ELSE
                        CAST(
                            TO_CHAR(
                                CAST(:data_envio AS DATE),
                                'YYYYMMDD'
                            )
                            AS INTEGER
                        )
                END,

                -- DATA DE VENCIMENTO
                CASE
                    WHEN :data_vencimento IS NULL
                        THEN NULL
                    ELSE
                        CAST(
                            TO_CHAR(
                                CAST(:data_vencimento AS DATE),
                                'YYYYMMDD'
                            )
                            AS INTEGER
                        )
                END,

                -- CLIENTE
                COALESCE(
                    (
                        SELECT chave_cliente
                        FROM dw.dim_cliente
                        WHERE
                            id_cliente = :id_cliente
                            AND eh_vigente = TRUE
                        ORDER BY chave_cliente DESC
                        LIMIT 1
                    ),
                    -1
                ),

                -- PRODUTO
                COALESCE(
                    (
                        SELECT chave_produto
                        FROM dw.dim_produto
                        WHERE
                            id_produto = :id_produto
                            AND eh_vigente = TRUE
                        ORDER BY chave_produto DESC
                        LIMIT 1
                    ),
                    -1
                ),

                -- VENDEDOR
                COALESCE(
                    (
                        SELECT chave_vendedor
                        FROM dw.dim_vendedor
                        WHERE
                            id_funcionario = :id_funcionario
                            AND eh_vigente = TRUE
                        ORDER BY chave_vendedor DESC
                        LIMIT 1
                    ),
                    -1
                ),

                -- TERRITÓRIO
                COALESCE(
                    (
                        SELECT chave_territorio
                        FROM dw.dim_territorio
                        WHERE
                            id_territorio = :id_territorio
                        LIMIT 1
                    ),
                    -1
                ),

                -- PROMOÇÃO
                COALESCE(
                    (
                        SELECT chave_promocao
                        FROM dw.dim_promocao
                        WHERE
                            id_oferta_especial =
                                :id_oferta_especial
                        LIMIT 1
                    ),
                    -1
                ),

                -- MÉTODO DE ENVIO
                COALESCE(
                    (
                        SELECT chave_metodo_envio
                        FROM dw.dim_metodo_envio
                        WHERE
                            id_metodo_envio =
                                :id_metodo_envio
                        LIMIT 1
                    ),
                    -1
                ),

                -- IDENTIFICADORES
                :numero_pedido_venda,
                :numero_linha_pedido,
                :id_detalhe_pedido,

                -- MEDIDAS
                :quantidade_pedido,
                :preco_unitario,
                :desconto_preco_unitario,

                -- VALOR DO DESCONTO
                (
                    :preco_unitario
                    * :quantidade_pedido
                    * :desconto_preco_unitario
                ),

                :total_linha,

                -- CUSTO PADRÃO
                COALESCE(
                    (
                        SELECT custo_padrao
                        FROM dw.dim_produto
                        WHERE
                            id_produto = :id_produto
                            AND eh_vigente = TRUE
                        ORDER BY chave_produto DESC
                        LIMIT 1
                    ),
                    0
                ),

                :valor_imposto,
                :frete,
                :data_modificacao

            ON CONFLICT (id_detalhe_pedido)

            DO UPDATE SET

                chave_data_pedido =
                    EXCLUDED.chave_data_pedido,

                chave_data_envio =
                    EXCLUDED.chave_data_envio,

                chave_data_vencimento =
                    EXCLUDED.chave_data_vencimento,

                chave_cliente =
                    EXCLUDED.chave_cliente,

                chave_produto =
                    EXCLUDED.chave_produto,

                chave_vendedor =
                    EXCLUDED.chave_vendedor,

                chave_territorio =
                    EXCLUDED.chave_territorio,

                chave_promocao =
                    EXCLUDED.chave_promocao,

                chave_metodo_envio =
                    EXCLUDED.chave_metodo_envio,

                numero_pedido_venda =
                    EXCLUDED.numero_pedido_venda,

                numero_linha_pedido =
                    EXCLUDED.numero_linha_pedido,

                quantidade_pedido =
                    EXCLUDED.quantidade_pedido,

                preco_unitario =
                    EXCLUDED.preco_unitario,

                desconto_preco_unitario =
                    EXCLUDED.desconto_preco_unitario,

                valor_desconto =
                    EXCLUDED.valor_desconto,

                total_linha =
                    EXCLUDED.total_linha,

                custo_padrao =
                    EXCLUDED.custo_padrao,

                valor_imposto =
                    EXCLUDED.valor_imposto,

                frete =
                    EXCLUDED.frete,

                data_modificacao_origem =
                    EXCLUDED.data_modificacao_origem,

                marca_tempo_carregamento =
                    now()
            """
        )

        processados = 0

        for _, r in staged.iterrows():

            params = r.to_dict()

            # -----------------------------------------------
            # Tratamento de NaN → None
            # -----------------------------------------------

            params = {
                k: (
                    None
                    if pd.isna(v)
                    else v
                )
                for k, v in params.items()
            }

            conn.execute(
                insert_sql,
                params,
            )

            processados += 1

        return processados


# ============================================================
# CONFIGURAÇÃO DAS DIMENSÕES
# ============================================================

DIM_JOBS = [

    # SCD2
    {
        "name": "cliente",
        "table": "dw.dim_cliente",
        "pk": "chave_cliente",
        "bk": "id_cliente",
        "attrs": [
            "nome_cliente",
            "tipo_cliente",
            "cidade",
            "estado_provincia",
            "pais_regiao",
            "codigo_postal",
        ],
        "scd_type": 2,
    },

    # SCD2
    {
        "name": "produto",
        "table": "dw.dim_produto",
        "pk": "chave_produto",
        "bk": "id_produto",
        "attrs": [
            "nome_produto",
            "numero_produto",
            "cor",
            "tamanho",
            "nome_subcategoria",
            "nome_categoria",
            "custo_padrao",
            "preco_tabela",
        ],
        "scd_type": 2,
    },

    # SCD2
    {
        "name": "vendedor",
        "table": "dw.dim_vendedor",
        "pk": "chave_vendedor",
        "bk": "id_funcionario",
        "attrs": [
            "nome_completo",
            "cargo",
        ],
        "scd_type": 2,
    },

    # SCD1
    {
        "name": "territorio",
        "table": "dw.dim_territorio",
        "bk": "id_territorio",
        "attrs": [
            "nome_territorio",
            "codigo_pais_regiao",
            "grupo_territorio",
        ],
        "scd_type": 1,
    },

    # SCD1
    {
        "name": "oferta_especial",
        "table": "dw.dim_promocao",
        "bk": "id_oferta_especial",
        "attrs": [
            "descricao",
            "percentual_desconto",
            "tipo_promocao",
            "categoria_promocao",
            "data_inicio",
            "data_fim",
        ],
        "scd_type": 1,
    },

    # SCD1
    {
        "name": "metodo_envio",
        "table": "dw.dim_metodo_envio",
        "bk": "id_metodo_envio",
        "attrs": [
            "nome",
            "base_envio",
            "taxa_envio",
        ],
        "scd_type": 1,
    },
]


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def run(full_load: bool = False):

    log.info(
        "============================================================"
    )

    log.info(
        "INÍCIO DA ETL - AdventureWorks → PostgreSQL DW"
    )

    log.info(
        f"Modo full load: {full_load}"
    )

    log.info(
        "============================================================"
    )

    watermarks = {}

    try:

        # ====================================================
        # 1. EXTRAÇÃO DAS DIMENSÕES
        # ====================================================

        for job in DIM_JOBS:

            rows, wm = extract_to_staging(
                job["name"],
                full_load,
            )

            watermarks[
                job["name"]
            ] = (
                rows,
                wm,
            )

        # ====================================================
        # 2. EXTRAÇÃO DA FATO
        # ====================================================

        fact_rows, fact_wm = extract_to_staging(
            "detalhe_pedido_venda",
            full_load,
        )

        watermarks[
            "detalhe_pedido_venda"
        ] = (
            fact_rows,
            fact_wm,
        )

        # ====================================================
        # 3. CARGA DAS DIMENSÕES
        # ====================================================

        for job in DIM_JOBS:

            rows, wm = watermarks[
                job["name"]
            ]

            if rows == 0:

                log.info(
                    f"[LOAD DIM] {job['table']}: "
                    f"nenhum registro para carregar."
                )

                continue

            if job["scd_type"] == 2:

                n = load_dim_scd2(
                    job["table"],
                    job["pk"],
                    job["bk"],
                    job["attrs"],
                    job["name"],
                )

            else:

                n = load_dim_scd1(
                    job["table"],
                    job["bk"],
                    job["attrs"],
                    job["name"],
                )

            log.info(
                f"[LOAD DIM] {job['table']}: "
                f"{n} linhas aplicadas "
                f"(SCD{job['scd_type']})"
            )

            # -----------------------------------------------
            # Só atualiza watermark após sucesso
            # -----------------------------------------------

            if wm is not None:

                set_watermark(
                    job["name"],
                    wm,
                    "SUCCESS",
                    rows,
                )

            log_step(
                "etl_incremental",
                f"load_dim_{job['name']}",
                "SUCCESS",
                n,
            )

        # ====================================================
        # 4. CARGA DA FATO
        # ====================================================

        rows, wm = watermarks[
            "detalhe_pedido_venda"
        ]

        if rows > 0:

            n = load_fact_sales()

            log.info(
                f"[LOAD FACT] dw.fato_vendas: "
                f"{n} linhas processadas (upsert)"
            )

            if wm is not None:

                set_watermark(
                    "detalhe_pedido_venda",
                    wm,
                    "SUCCESS",
                    rows,
                )

            log_step(
                "etl_incremental",
                "load_fato_vendas",
                "SUCCESS",
                n,
            )

        else:

            log.info(
                "[LOAD FACT] Nenhuma venda nova ou alterada."
            )

        # ====================================================
        # FIM
        # ====================================================

        log.info(
            "============================================================"
        )

        log.info(
            "ETL FINALIZADA COM SUCESSO"
        )

        log.info(
            "============================================================"
        )

    except Exception as e:

        log.exception(
            "ETL FINALIZADA COM ERRO"
        )

        log_step(
            "etl_incremental",
            "execucao",
            "ERROR",
            0,
            str(e),
        )

        raise


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "ETL incremental "
            "AdventureWorks → DW PostgreSQL"
        )
    )

    parser.add_argument(
        "--full-load",
        action="store_true",
        help=(
            "Ignora os watermarks "
            "e realiza uma carga completa."
        ),
    )

    args = parser.parse_args()

    run(
        full_load=args.full_load
    )