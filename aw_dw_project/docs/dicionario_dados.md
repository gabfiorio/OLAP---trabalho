# Dicionário de Dados — Data Warehouse AdventureWorks (schema `dw`)

## Tabela fato: `dw.fact_sales`
Grão: uma linha por item de linha de pedido de venda (`Sales.SalesOrderDetail`).

| Coluna | Tipo | Descrição |
|---|---|---|
| sales_key | bigserial (PK) | Chave substituta do fato |
| order_date_key | int (FK dim_date) | Data do pedido |
| ship_date_key | int (FK dim_date) | Data de envio |
| due_date_key | int (FK dim_date) | Data prevista de entrega |
| customer_key | int (FK dim_customer) | Cliente (versão vigente na venda) |
| product_key | int (FK dim_product) | Produto (versão vigente na venda) |
| salesperson_key | int (FK dim_salesperson) | Vendedor responsável |
| territory_key | int (FK dim_territory) | Território de venda |
| promotion_key | int (FK dim_promotion) | Promoção/oferta especial aplicada |
| ship_method_key | int (FK dim_ship_method) | Modal de envio |
| sales_order_number | varchar | Dimensão degenerada — número do pedido |
| sales_order_line_number | smallint | Dimensão degenerada — linha do pedido |
| sales_order_detail_id | int | Chave natural da origem (garante idempotência no upsert) |
| order_qty | int | Quantidade vendida |
| unit_price | numeric | Preço unitário |
| unit_price_discount | numeric | Percentual de desconto unitário |
| discount_amount | numeric | Valor de desconto (medida aditiva calculada) |
| line_total | numeric | Valor total da linha (medida aditiva principal) |
| standard_cost | numeric | Custo padrão do produto na data da venda |
| tax_amt | numeric | Imposto rateado da linha |
| freight | numeric | Frete rateado da linha |
| source_modified_date | timestamp | Timestamp de origem (auditoria/rastreabilidade) |
| dw_load_timestamp | timestamp | Timestamp de carga no DW |

## Dimensões

### `dw.dim_date` — SCD Tipo 0 (estática, pré-carregada)
date_key (PK, AAAAMMDD), full_date, day_of_month, day_name, day_of_week,
month_number, month_name, quarter, year, is_weekend, fiscal_year, fiscal_quarter.

### `dw.dim_customer` — SCD Tipo 2
customer_key (PK), customer_id (chave natural), customer_name, customer_type
(Individual/Store), city, state_province, country_region, postal_code,
effective_date, end_date, is_current, row_hash.

### `dw.dim_product` — SCD Tipo 2
product_key (PK), product_id (BK), product_name, product_number, color, size,
subcategory_name, category_name, standard_cost, list_price, effective_date,
end_date, is_current, row_hash.

### `dw.dim_salesperson` — SCD Tipo 2
salesperson_key (PK), employee_id (BK), full_name, job_title, effective_date,
end_date, is_current, row_hash.

### `dw.dim_territory` — SCD Tipo 1
territory_key (PK), territory_id (BK), territory_name, country_region_code,
territory_group.

### `dw.dim_promotion` — SCD Tipo 1
promotion_key (PK), special_offer_id (BK), description, discount_pct,
promotion_type, promotion_category, start_date, end_date.

### `dw.dim_ship_method` — SCD Tipo 1
ship_method_key (PK), ship_method_id (BK), name, ship_base, ship_rate.

## Tabelas de controle (`ctrl`)

- **ctrl.etl_watermark**: guarda, por tabela de origem, o último `ModifiedDate`
  processado — usado para determinar o corte da próxima extração incremental.
- **ctrl.etl_log**: log de execução de cada etapa da ETL (linhas afetadas, status,
  timestamps), usado para auditoria e monitoramento.
