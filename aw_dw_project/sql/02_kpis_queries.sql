-- =====================================================================
-- Projeto: Data Warehouse AdventureWorks - Indicadores (KPIs)
-- Arquivo: 02_kpis_queries.sql
-- Descrição: Consultas SQL que implementam os 10 indicadores definidos
--            no artigo, executadas sobre o schema dimensional dw.*
-- =====================================================================

-- ---------------------------------------------------------------------
-- KPI 01 - Receita Total de Vendas (Total Sales Revenue)
-- ---------------------------------------------------------------------
SELECT
    d.ano,
    d.numero_mes,
    d.nome_mes,
    ROUND(SUM(f.total_linha), 2) AS receita_total
FROM dw.fato_vendas f
JOIN dw.dim_data d ON d.chave_data = f.chave_data_pedido
GROUP BY d.ano, d.numero_mes, d.nome_mes
ORDER BY d.ano, d.numero_mes;

-- ---------------------------------------------------------------------
-- KPI 02 - Ticket Médio por Pedido (Average Order Value)
-- ---------------------------------------------------------------------
SELECT
    d.ano,
    ROUND(SUM(f.total_linha) / COUNT(DISTINCT f.numero_pedido_venda), 2) AS ticket_medio
FROM dw.fato_vendas f
JOIN dw.dim_data d ON d.chave_data = f.chave_data_pedido
GROUP BY d.ano
ORDER BY d.ano;

-- ---------------------------------------------------------------------
-- KPI 03 - Quantidade Total de Itens Vendidos
-- ---------------------------------------------------------------------
SELECT
    d.ano,
    d.trimestre,
    SUM(f.quantidade_pedido) AS itens_vendidos
FROM dw.fato_vendas f
JOIN dw.dim_data d ON d.chave_data = f.chave_data_pedido
GROUP BY d.ano, d.trimestre
ORDER BY d.ano, d.trimestre;

-- ---------------------------------------------------------------------
-- KPI 04 - Margem de Lucro Bruta (Gross Profit Margin %)
-- ---------------------------------------------------------------------
SELECT
    p.nome_categoria,
    ROUND(SUM(f.total_linha), 2)                                    AS receita,
    ROUND(SUM(f.custo_padrao * f.quantidade_pedido), 2)             AS custo,
    ROUND(SUM(f.total_linha - f.custo_padrao * f.quantidade_pedido), 2)    AS lucro_bruto,
    ROUND(100.0 * SUM(f.total_linha - f.custo_padrao * f.quantidade_pedido)
          / NULLIF(SUM(f.total_linha), 0), 2)                       AS margem_pct
FROM dw.fato_vendas f
JOIN dw.dim_produto p ON p.chave_produto = f.chave_produto
GROUP BY p.nome_categoria
ORDER BY margem_pct DESC;

-- ---------------------------------------------------------------------
-- KPI 05 - Taxa de Desconto Média Aplicada (Average Discount Rate)
-- ---------------------------------------------------------------------
SELECT
    d.ano,
    ROUND(100.0 * SUM(f.valor_desconto) / NULLIF(SUM(f.preco_unitario * f.quantidade_pedido), 0), 2)
        AS taxa_desconto_media_pct
FROM dw.fato_vendas f
JOIN dw.dim_data d ON d.chave_data = f.chave_data_pedido
GROUP BY d.ano
ORDER BY d.ano;

-- ---------------------------------------------------------------------
-- KPI 06 - Vendas por Território (Sales by Territory)
-- ---------------------------------------------------------------------
SELECT
    t.grupo_territorio,
    t.nome_territorio,
    ROUND(SUM(f.total_linha), 2) AS receita_total,
    COUNT(DISTINCT f.numero_pedido_venda) AS qtd_pedidos
FROM dw.fato_vendas f
JOIN dw.dim_territorio t ON t.chave_territorio = f.chave_territorio
GROUP BY t.grupo_territorio, t.nome_territorio
ORDER BY receita_total DESC;

-- ---------------------------------------------------------------------
-- KPI 07 - Top 10 Produtos Mais Vendidos (por receita)
-- ---------------------------------------------------------------------
SELECT
    p.nome_produto,
    p.nome_categoria,
    SUM(f.quantidade_pedido)            AS qtd_vendida,
    ROUND(SUM(f.total_linha), 2) AS receita_total
FROM dw.fato_vendas f
JOIN dw.dim_produto p ON p.chave_produto = f.chave_produto
GROUP BY p.nome_produto, p.nome_categoria
ORDER BY receita_total DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- KPI 08 - Desempenho de Vendedores (Sales by Salesperson)
-- ---------------------------------------------------------------------
SELECT
    v.nome_completo,
    v.cargo,
    ROUND(SUM(f.total_linha), 2)               AS receita_total,
    COUNT(DISTINCT f.numero_pedido_venda)     AS qtd_pedidos,
    ROUND(SUM(f.total_linha) / COUNT(DISTINCT f.numero_pedido_venda), 2) AS ticket_medio
FROM dw.fato_vendas f
JOIN dw.dim_vendedor v ON v.chave_vendedor = f.chave_vendedor
WHERE v.chave_vendedor <> -1
GROUP BY v.nome_completo, v.cargo
ORDER BY receita_total DESC;

-- ---------------------------------------------------------------------
-- KPI 09 - Taxa de Crescimento de Vendas Mês a Mês (MoM Growth %)
-- ---------------------------------------------------------------------
WITH vendas_mes AS (
    SELECT d.ano, d.numero_mes,
           SUM(f.total_linha) AS receita_mes
    FROM dw.fato_vendas f
    JOIN dw.dim_data d ON d.chave_data = f.chave_data_pedido
    GROUP BY d.ano, d.numero_mes
)
SELECT
    ano, numero_mes, ROUND(receita_mes, 2) AS receita_mes,
    ROUND(100.0 * (receita_mes - LAG(receita_mes) OVER (ORDER BY ano, numero_mes))
          / NULLIF(LAG(receita_mes) OVER (ORDER BY ano, numero_mes), 0), 2) AS crescimento_mom_pct
FROM vendas_mes
ORDER BY ano, numero_mes;

-- ---------------------------------------------------------------------
-- KPI 10 - Tempo Médio de Envio / Lead Time de Atendimento (dias)
-- ---------------------------------------------------------------------
SELECT
    t.nome_territorio,
    ROUND(AVG(env.data_completa - ped.data_completa), 2) AS lead_time_medio_dias
FROM dw.fato_vendas f
JOIN dw.dim_data ped  ON ped.chave_data  = f.chave_data_pedido
JOIN dw.dim_data env ON env.chave_data = f.chave_data_envio
JOIN dw.dim_territorio t ON t.chave_territorio = f.chave_territorio
WHERE f.chave_data_envio IS NOT NULL
GROUP BY t.nome_territorio
ORDER BY lead_time_medio_dias;
