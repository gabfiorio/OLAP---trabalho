# Data Warehouse AdventureWorks — Star Schema + ETL Incremental

Projeto acadêmico de construção de um Data Warehouse dimensional
para o domínio de **Vendas** da base OLTP **AdventureWorks2016**, com processo de
ETL incremental em Python e implementação do DW em **PostgreSQL**.

## Estrutura do repositório

```
├── sql/
│   ├── 01_ddl_dw_postgres.sql   # DDL completo do DW (schemas dw/stg/ctrl)
│   └── 02_kpis_queries.sql      # Scripts SQL dos 10 indicadores (KPIs)
├── etl/
│   ├── etl_incremental.py       # ETL incremental (extração/transformação/carga)
│   ├── load_dim_date.py         # Carga única da dimensão calendário
│   ├── requirements.txt
│   └── .env.example
├── diagrams/
│   ├── star_schema.png          # Diagrama do modelo estrela (renderizado)
│   └── star_schema.puml         # Fonte PlantUML do diagrama
└── docs/
    └── dicionario_dados.md      # Dicionário de dados do DW
```

## Como executar

```bash
# 1. Criar o banco e aplicar o DDL
createdb adventureworks_dw
psql -d adventureworks_dw -f sql/01_ddl_dw_postgres.sql

# 2. Instalar dependências da ETL
cd etl
pip install -r requirements.txt
cp .env.example .env   # ajustar credenciais de origem/destino

# 3. Popular a dimensão calendário (carga única)
python load_dim_date.py --start 2005-01-01 --end 2030-12-31

# 4. Executar a ETL incremental
python etl_incremental.py              # incremental (usa watermark)
python etl_incremental.py --full-load  # carga completa inicial

# 5. Validar os indicadores
psql -d adventureworks_dw -f ../sql/02_kpis_queries.sql
```

## Modelo dimensional

Fato `dw.fact_sales` (grão: item de pedido de venda) cercado por sete dimensões:
`dim_date`, `dim_customer` (SCD2), `dim_product` (SCD2), `dim_salesperson` (SCD2),
`dim_territory`, `dim_promotion` e `dim_ship_method`. Ver `diagrams/star_schema.png`
e `docs/dicionario_dados.md` para detalhes.

## Autoria

Trabalho acadêmico desenvolvido para a disciplina de Modelagem Multidimensional /
Business Intelligence — Centro Universitário Salesiano (Unisales).
