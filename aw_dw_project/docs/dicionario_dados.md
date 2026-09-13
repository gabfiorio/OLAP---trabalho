# Dicionário de Dados — Data Warehouse AdventureWorks (schema `dw`)

## Tabela fato: `dw.fato_vendas`

Grão: uma linha por item de pedido de venda (`Sales.SalesOrderDetail`).

| Coluna | Tipo | Descrição |
|---|---|---|
| chave_venda | bigserial (PK) | Chave substituta do fato |
| chave_data_pedido | int (FK dim_data) | Data do pedido |
| chave_data_envio | int (FK dim_data) | Data de envio |
| chave_data_vencimento | int (FK dim_data) | Data prevista de entrega |
| chave_cliente | int (FK dim_cliente) | Cliente vigente na venda |
| chave_produto | int (FK dim_produto) | Produto vigente na venda |
| chave_vendedor | int (FK dim_vendedor) | Vendedor responsável |
| chave_territorio | int (FK dim_territorio) | Território de venda |
| chave_promocao | int (FK dim_promocao) | Promoção/oferta especial aplicada |
| chave_metodo_envio | int (FK dim_metodo_envio) | Modal de envio |
| numero_pedido_venda | varchar | Dimensão degenerada — número do pedido |
| numero_linha_pedido | smallint | Dimensão degenerada — linha do pedido |
| id_detalhe_pedido | int | Chave natural da origem, usada para garantir idempotência no upsert |
| quantidade_pedido | int | Quantidade vendida |
| preco_unitario | numeric | Preço unitário |
| desconto_preco_unitario | numeric | Percentual de desconto unitário |
| valor_desconto | numeric | Valor de desconto calculado |
| total_linha | numeric | Valor total da linha |
| custo_padrao | numeric | Custo padrão do produto na data da venda |
| valor_imposto | numeric | Imposto rateado da linha |
| frete | numeric | Frete rateado da linha |
| data_modificacao_origem | timestamp | Data de modificação na origem |
| marca_tempo_carregamento | timestamp | Data e hora da carga no DW |

## Dimensões

### `dw.dim_data` — SCD Tipo 0 (estática, pré-carregada)

`chave_data` (PK, AAAAMMDD), `data_completa`, `dia_mes`, `nome_dia`,
`dia_semana`, `numero_mes`, `nome_mes`, `trimestre`, `ano`,
`eh_fim_de_semana`, `ano_fiscal`, `trimestre_fiscal`.

### `dw.dim_cliente` — SCD Tipo 2

`chave_cliente` (PK), `id_cliente` (chave natural), `nome_cliente`,
`tipo_cliente`, `cidade`, `estado_provincia`, `pais_regiao`, `codigo_postal`,
`data_efetiva`, `data_fim`, `eh_vigente`, `hash_linha`.

### `dw.dim_produto` — SCD Tipo 2

`chave_produto` (PK), `id_produto` (chave natural), `nome_produto`,
`numero_produto`, `cor`, `tamanho`, `nome_subcategoria`, `nome_categoria`,
`custo_padrao`, `preco_tabela`, `data_efetiva`, `data_fim`, `eh_vigente`,
`hash_linha`.

### `dw.dim_vendedor` — SCD Tipo 2

`chave_vendedor` (PK), `id_funcionario` (chave natural), `nome_completo`,
`cargo`, `data_efetiva`, `data_fim`, `eh_vigente`, `hash_linha`.

### `dw.dim_territorio` — SCD Tipo 1

`chave_territorio` (PK), `id_territorio` (chave natural), `nome_territorio`,
`codigo_pais_regiao`, `grupo_territorio`.

### `dw.dim_promocao` — SCD Tipo 1

`chave_promocao` (PK), `id_oferta_especial` (chave natural), `descricao`,
`percentual_desconto`, `tipo_promocao`, `categoria_promocao`, `data_inicio`,
`data_fim`.

### `dw.dim_metodo_envio` — SCD Tipo 1

`chave_metodo_envio` (PK), `id_metodo_envio` (chave natural), `nome`,
`base_envio`, `taxa_envio`.

## Tabelas de controle (`ctrl`)

- **ctrl.marca_agua_etl**: guarda, por tabela de origem, a última data de
  modificação processada, usada para determinar o corte da próxima extração incremental.
- **ctrl.log_etl**: registra cada etapa da ETL, incluindo linhas afetadas,
  status, timestamps e mensagens para auditoria e monitoramento.
