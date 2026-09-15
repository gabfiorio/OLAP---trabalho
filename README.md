# Data Warehouse AdventureWorks — Star Schema + ETL Incremental

Projeto acadêmico de construção de um Data Warehouse dimensional
para o domínio de **Vendas** da base OLTP **AdventureWorks2016**, com processo de
ETL incremental em Python e implementação do DW em **PostgreSQL**.

## Estrutura do repositório

```text
.
├── sql/
│   ├── 01_ddl_dw_postgres.sql     # DDL completo do Data Warehouse
│   └── 02_kpis_queries.sql        # Consultas SQL dos 10 KPIs
│
├── etl/
│   ├── etl_incremental.py          # ETL incremental
│   ├── load_dim_date.py            # Carga da dimensão calendário
│   ├── requirements.txt            # Dependências Python
│   └── .env.example                # Exemplo de configuração
│
├── diagrams/
│   ├── star_schema.png             # Diagrama do modelo estrela
│   └── star_schema.puml            # Código PlantUML do diagrama
│
├── docs/
│   └── dicionario_dados.md         # Dicionário de dados
├── README.md                      # Documentação do projeto
└── .gitignore                     # Arquivos ignorados pelo Git
```

---

## 1. Pré-requisitos

Antes de executar o projeto, é necessário possuir:

- Docker Desktop;
- Python 3.10 ou superior;
- PostgreSQL;
- DBeaver ou outra ferramenta de gerenciamento de banco;
- Git;
- Driver ODBC 18 para SQL Server;
- arquivo de backup AdventureWorks2016.bak.

---

## 2. Banco de origem — AdventureWorks2016

A AdventureWorks2016 é utilizada como banco de origem OLTP.

O banco OLTP representa o ambiente transacional, no qual os dados de vendas, clientes, produtos, vendedores, territórios, promoções e métodos de envio estão organizados de forma normalizada.

O backup disponibilizado para o projeto possui extensão `.bak`:

`AdventureWorks2016.bak`

Esse arquivo precisa ser restaurado em uma instância do SQL Server antes da execução do ETL.

Neste projeto, o SQL Server é executado em um contêiner Docker.

---

## 3. Executar o SQL Server no Docker

Baixe a imagem do SQL Server:

```bash
docker pull mcr.microsoft.com/mssql/server:2022-latest
```

Crie o contêiner:

### Windows — PowerShell

```powershell
docker run -e "ACCEPT_EULA=Y" `
-e "MSSQL_SA_PASSWORD=SqlServer@2026" `
-p 1433:1433 `
--name sqlserver-aw `
-d mcr.microsoft.com/mssql/server:2022-latest
```

Verifique se o contêiner está executando:

```bash
docker ps
```

O contêiner deverá aparecer com o nome:

```text
sqlserver-aw
```

---

## 4. Copiar o backup para o SQL Server

Crie a pasta de backup dentro do contêiner:

```bash
docker exec sqlserver-aw mkdir -p /var/opt/mssql/backup
```

Copie o arquivo `.bak` para o contêiner:

```bash
docker cp "C:\caminho\AdventureWorks2016.bak" sqlserver-aw:/var/opt/mssql/backup/AdventureWorks2016.bak
```

Substitua:

```text
C:\caminho\AdventureWorks2016.bak
```

pelo caminho real do arquivo no computador.

Verifique se o backup foi copiado:

```bash
docker exec sqlserver-aw ls -lh /var/opt/mssql/backup
```

---

## 5. Restaurar a AdventureWorks2016

Primeiro, consulte os arquivos lógicos existentes no backup:

```bash
docker exec sqlserver-aw /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "SqlServer@2026" -C -Q "RESTORE FILELISTONLY FROM DISK = '/var/opt/mssql/backup/AdventureWorks2016.bak'"
```

No backup utilizado neste projeto, os arquivos lógicos são:

```text
AdventureWorks2016_Data
AdventureWorks2016_Log
```

Execute a restauração:

```bash
docker exec sqlserver-aw /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "SqlServer@2026" -C -Q "RESTORE DATABASE AdventureWorks2016 FROM DISK = '/var/opt/mssql/backup/AdventureWorks2016.bak' WITH MOVE 'AdventureWorks2016_Data' TO '/var/opt/mssql/data/AdventureWorks2016_Data.mdf', MOVE 'AdventureWorks2016_Log' TO '/var/opt/mssql/data/AdventureWorks2016_Log.ldf', REPLACE, STATS = 10"
```

Após a restauração, valide a existência da base:

```bash
docker exec sqlserver-aw /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "SqlServer@2026" -C -Q "SELECT name FROM sys.databases"
```

A saída deverá apresentar:

```text
AdventureWorks2016
```

---

## 6. Banco de destino — PostgreSQL

O PostgreSQL é utilizado como Data Warehouse.

Crie um banco chamado:

```sql
CREATE DATABASE adventureworks_dw;
```

Neste projeto, a configuração utilizada é:

- Host: localhost
- Port: 5439
- Database: adventureworks_dw
- User: postgres

Caso sejam utilizadas outras configurações, elas devem ser alteradas no arquivo `.env`.

---

## 7. Criar a estrutura do Data Warehouse

Após criar o banco `adventureworks_dw`, execute:

```text
sql/01_ddl_dw_postgres.sql
```

O script cria os seguintes schemas:

- `dw`
- `stg`
- `ctrl`

### `dw`

Contém as tabelas do Data Warehouse:

- `dw.dim_data`
- `dw.dim_cliente`
- `dw.dim_produto`
- `dw.dim_vendedor`
- `dw.dim_territorio`
- `dw.dim_promocao`
- `dw.dim_metodo_envio`
- `dw.fato_vendas`

### `stg`

Contém as tabelas de staging utilizadas durante o processo de ETL.

### `ctrl`

Contém as tabelas de controle e acompanhamento das execuções do ETL:

- `ctrl.marca_agua_etl`
- `ctrl.log_etl`

---

## 8. Modelo dimensional

O Data Warehouse utiliza o modelo Star Schema.

A tabela central é:

```text
dw.fato_vendas
```

O grão da tabela fato é:

```text
1 registro = 1 item de um pedido de venda
```

A tabela fato possui relacionamento com sete dimensões:

```text
                    dim_data
                       │
                       │
               ┌───────┴───────┐
               │               │
       dim_cliente        dim_produto
               │               │
               └───────┬───────┘
                       │
                 fato_vendas
                       │
              ┌────────┼────────┐
              │        │        │
       dim_vendedor  dim_territorio
                       │
              ┌────────┴────────┐
              │                 │
       dim_promocao      dim_metodo_envio
```

As dimensões utilizadas são:

| Dimensão | Tipo |
| --- | --- |
| dim_data | Dimensão calendário |
| dim_cliente | SCD Tipo 2 |
| dim_produto | SCD Tipo 2 |
| dim_vendedor | SCD Tipo 2 |
| dim_territorio | SCD Tipo 1 |
| dim_promocao | SCD Tipo 1 |
| dim_metodo_envio | SCD Tipo 1 |

O diagrama completo está disponível em:

- `diagrams/star_schema.png`

O código-fonte do diagrama está disponível em:

- `diagrams/star_schema.puml`

---

## 9. Configurar o ambiente Python

Entre na pasta da ETL:

```bash
cd etl
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

### No Windows

```powershell
.venv\Scripts\activate
```

### No Linux/macOS

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## 10. Configurar o arquivo `.env`

Copie o arquivo de exemplo:

### Windows

```powershell
copy .env.example .env
```

### Linux/macOS

```bash
cp .env.example .env
```

Configure as conexões no arquivo `.env`.

Exemplo:

```env
SRC_CONN_STR=mssql+pyodbc://sa:SqlServer%402026@localhost:1433/AdventureWorks2016?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
DW_CONN_STR=postgresql+psycopg2://postgres@localhost:5439/adventureworks_dw
```

A variável:

- `SRC_CONN_STR` representa a conexão com o SQL Server, onde está a AdventureWorks2016.
- `DW_CONN_STR` representa a conexão com o PostgreSQL, onde está o Data Warehouse.

O arquivo `.env` não deve ser versionado no GitHub quando contiver credenciais reais. Utilize o `.env.example` para disponibilizar apenas o modelo de configuração.

---

## 11. Carga da dimensão calendário

Antes de carregar a tabela fato, é necessário popular a dimensão calendário.

Execute:

```bash
python load_dim_date.py --start 2005-01-01 --end 2030-12-31
```

Essa etapa cria os registros de datas necessários para as análises temporais do Data Warehouse.

---

## 12. Executar o ETL

O processo principal está no arquivo:

```text
etl/etl_incremental.py
```

### 12.1 Carga inicial

Na primeira execução, utilize:

```bash
python etl_incremental.py --full-load
```

A carga completa realiza a extração dos dados da AdventureWorks2016 e a carga inicial das dimensões e da tabela fato.

### 12.2 Carga incremental

Depois da carga inicial, execute:

```bash
python etl_incremental.py
```

O ETL utiliza o mecanismo de watermark para identificar a última extração realizada e buscar registros novos ou modificados.

O controle é armazenado em:

- `ctrl.marca_agua_etl`

Dessa forma, as execuções seguintes não precisam processar novamente todos os dados da base de origem.

---

## 13. Funcionamento do ETL

O processo de ETL é dividido em três etapas principais:

```text
┌─────────────────────┐
│      EXTRACT        │
│                     │
│ SQL Server          │
│ AdventureWorks2016  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       STAGING       │
│                     │
│ PostgreSQL          │
│ schema stg          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      TRANSFORM      │
│                     │
│ • Tratamento        │
│ • SCD Tipo 1        │
│ • SCD Tipo 2        │
│ • Chaves substitutas│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│        LOAD         │
│                     │
│ PostgreSQL          │
│ schema dw           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      CONTROLE       │
│                     │
│ ctrl.marca_agua_etl │
│ ctrl.log_etl        │
└─────────────────────┘
```

A extração incremental utiliza a coluna `ModifiedDate` da base de origem para identificar registros novos ou modificados.

---

## 14. Slowly Changing Dimensions — SCD

O projeto utiliza dois tipos de tratamento para alterações nas dimensões.

### SCD Tipo 1

No SCD Tipo 1, a informação anterior é substituída pela nova informação.

É utilizado nas dimensões:

- `dim_territorio`
- `dim_promocao`
- `dim_metodo_envio`

### SCD Tipo 2

No SCD Tipo 2, as alterações são preservadas criando novas versões do registro.

É utilizado nas dimensões:

- `dim_cliente`
- `dim_produto`
- `dim_vendedor`

As dimensões SCD Tipo 2 possuem informações de vigência para identificar qual versão do registro está ativa.

---

## 15. Validação da carga

Após executar o ETL, é possível verificar se os dados foram carregados corretamente.

### Quantidade de registros da tabela fato

```sql
SELECT COUNT(*)
FROM dw.fato_vendas;
```

### Quantidade de clientes

```sql
SELECT COUNT(*)
FROM dw.dim_cliente;
```

### Quantidade de produtos

```sql
SELECT COUNT(*)
FROM dw.dim_produto;
```

### Quantidade de vendedores

```sql
SELECT COUNT(*)
FROM dw.dim_vendedor;
```

### Verificar o log do ETL

```sql
SELECT *
FROM ctrl.log_etl
ORDER BY id_log DESC;
```

### Verificar o watermark

```sql
SELECT *
FROM ctrl.marca_agua_etl;
```

---

## 16. KPIs

O projeto possui 10 indicadores de desempenho para análise das vendas:

| Nº | KPI |
| --- | --- |
| 1 | Receita Total de Vendas |
| 2 | Ticket Médio por Pedido |
| 3 | Quantidade Total de Itens Vendidos |
| 4 | Margem de Lucro Bruta (%) |
| 5 | Taxa de Desconto Média (%) |
| 6 | Vendas por Território |
| 7 | Top 10 Produtos por Receita |
| 8 | Desempenho por Vendedor |
| 9 | Crescimento de Vendas Mês a Mês (%) |
| 10 | Lead Time Médio de Envio |

As consultas SQL dos indicadores estão disponíveis em:

- `sql/02_kpis_queries.sql`

Para executar pelo `psql`:

```bash
psql -d adventureworks_dw -f sql/02_kpis_queries.sql
```

As consultas também podem ser executadas diretamente pelo DBeaver.

---

## 17. Dicionário de dados

O dicionário de dados apresenta as tabelas, colunas, tipos e finalidades dos principais elementos do Data Warehouse.

Arquivo:

- `docs/dicionario_dados.md`

---

## 18. Tecnologias utilizadas

| Tecnologia | Utilização |
| --- | --- |
| SQL Server | Banco OLTP de origem |
| AdventureWorks2016 | Base transacional de origem |
| Docker | Execução do SQL Server |
| Python | Desenvolvimento do ETL |
| SQLAlchemy | Integração e conexão com os bancos |
| pyodbc | Conexão Python com SQL Server |
| psycopg2 | Conexão Python com PostgreSQL |
| PostgreSQL | Data Warehouse |
| DBeaver | Administração e consultas aos bancos |
| PlantUML | Diagrama do modelo dimensional |
| Git/GitHub | Versionamento do projeto |

---

## 19. Fluxo completo de execução

Para executar o projeto do início ao fim:

1. Instalar os pré-requisitos
2. Iniciar o SQL Server no Docker
3. Copiar o `AdventureWorks2016.bak`
4. Restaurar o backup no SQL Server
5. Criar o banco `adventureworks_dw` no PostgreSQL
6. Executar `sql/01_ddl_dw_postgres.sql`
7. Criar e ativar o ambiente virtual Python
8. Instalar `requirements.txt`
9. Configurar o arquivo `.env`
10. Executar `load_dim_date.py`
11. Executar `etl_incremental.py --full-load`
12. Executar `etl_incremental.py`
13. Validar as tabelas do Data Warehouse
14. Executar as consultas dos 10 KPIs

```text
1. Instalar os pré-requisitos
        │
        ▼
2. Iniciar o SQL Server no Docker
        │
        ▼
3. Copiar o AdventureWorks2016.bak
        │
        ▼
4. Restaurar o backup no SQL Server
        │
        ▼
5. Criar o banco adventureworks_dw no PostgreSQL
        │
        ▼
6. Executar sql/01_ddl_dw_postgres.sql
        │
        ▼
7. Criar e ativar o ambiente virtual Python
        │
        ▼
8. Instalar requirements.txt
        │
        ▼
9. Configurar o arquivo .env
        │
        ▼
10. Executar load_dim_date.py
        │
        ▼
11. Executar etl_incremental.py --full-load
        │
        ▼
12. Executar etl_incremental.py
        │
        ▼
13. Validar as tabelas do Data Warehouse
        │
        ▼
14. Executar as consultas dos 10 KPIs
```

---

## 20. Organização das responsabilidades

A arquitetura do projeto pode ser entendida da seguinte forma:

| Componente | Responsabilidade |
| --- | --- |
| `.bak` | Backup da AdventureWorks2016 |
| Docker | Executar o SQL Server |
| SQL Server | Disponibilizar a AdventureWorks2016 como OLTP |
| Python | Executar o processo de ETL |
| `stg` | Receber dados durante o processo de ETL |
| `dw` | Armazenar os dados analíticos |
| `ctrl` | Controlar as execuções e o watermark |
| PostgreSQL | Hospedar o Data Warehouse |
| SQL dos KPIs | Realizar as análises sobre o DW |

---

## Resumo

Este projeto implementa um Data Warehouse em PostgreSQL a partir do banco transacional AdventureWorks2016, com uma estrutura dimensional em Star Schema, ETL incremental e controle de execução por watermark e logs de carga. A solução foi organizada para facilitar a análise de indicadores de vendas e a manutenção de históricos por meio de SCD tipo 1 e tipo 2.