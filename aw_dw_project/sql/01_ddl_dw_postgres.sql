CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS ctrl;

CREATE TABLE IF NOT EXISTS ctrl.marca_agua_etl (
    tabela_origem        VARCHAR(100) PRIMARY KEY,
    ultima_extracao_em   TIMESTAMP    NOT NULL DEFAULT '1900-01-01',
    ultima_exec_iniciada TIMESTAMP,
    ultima_exec_finalizada TIMESTAMP,
    status_ultima_exec    VARCHAR(20),
    linhas_processadas    INTEGER
);

CREATE TABLE IF NOT EXISTS ctrl.log_etl (
    id_log        SERIAL PRIMARY KEY,
    nome_processo  VARCHAR(100) NOT NULL,
    nome_etapa     VARCHAR(100) NOT NULL,
    iniciado_em    TIMESTAMP NOT NULL DEFAULT now(),
    finalizado_em  TIMESTAMP,
    status         VARCHAR(20),
    linhas_afetadas INTEGER,
    mensagem       TEXT
);

CREATE TABLE IF NOT EXISTS dw.dim_data (
    chave_data        INTEGER PRIMARY KEY,          
    data_completa     DATE NOT NULL,
    dia_mes           SMALLINT NOT NULL,
    nome_dia          VARCHAR(15) NOT NULL,
    dia_semana        SMALLINT NOT NULL,
    numero_mes        SMALLINT NOT NULL,
    nome_mes          VARCHAR(15) NOT NULL,
    trimestre         SMALLINT NOT NULL,
    ano               SMALLINT NOT NULL,
    eh_fim_de_semana  BOOLEAN NOT NULL,
    ano_fiscal        SMALLINT NOT NULL,           
    trimestre_fiscal  SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_cliente (
    chave_cliente      SERIAL PRIMARY KEY,
    id_cliente         INTEGER NOT NULL,          
    nome_cliente       VARCHAR(150),
    tipo_cliente       VARCHAR(20),                
    cidade             VARCHAR(100),
    estado_provincia   VARCHAR(100),
    pais_regiao        VARCHAR(100),
    codigo_postal      VARCHAR(20),
    data_efetiva       DATE NOT NULL DEFAULT '1900-01-01',
    data_fim           DATE NOT NULL DEFAULT '9999-12-31',
    eh_vigente         BOOLEAN NOT NULL DEFAULT TRUE,
    hash_linha         VARCHAR(64),             
    UNIQUE (id_cliente, data_efetiva)
);
CREATE INDEX IF NOT EXISTS ix_dim_cliente_bk_vigente
    ON dw.dim_cliente (id_cliente) WHERE eh_vigente;

CREATE TABLE IF NOT EXISTS dw.dim_produto (
    chave_produto      SERIAL PRIMARY KEY,
    id_produto         INTEGER NOT NULL,        
    nome_produto       VARCHAR(150),
    numero_produto     VARCHAR(30),
    cor                VARCHAR(30),
    tamanho            VARCHAR(10),
    nome_subcategoria  VARCHAR(100),
    nome_categoria     VARCHAR(100),
    custo_padrao       NUMERIC(12,4),
    preco_tabela       NUMERIC(12,4),
    data_efetiva       DATE NOT NULL DEFAULT '1900-01-01',
    data_fim           DATE NOT NULL DEFAULT '9999-12-31',
    eh_vigente         BOOLEAN NOT NULL DEFAULT TRUE,
    hash_linha         VARCHAR(64),
    UNIQUE (id_produto, data_efetiva)
);
CREATE INDEX IF NOT EXISTS ix_dim_produto_bk_vigente
    ON dw.dim_produto (id_produto) WHERE eh_vigente;

CREATE TABLE IF NOT EXISTS dw.dim_vendedor (
    chave_vendedor   SERIAL PRIMARY KEY,
    id_funcionario   INTEGER NOT NULL,          
    nome_completo    VARCHAR(150),
    cargo            VARCHAR(100),
    data_efetiva     DATE NOT NULL DEFAULT '1900-01-01',
    data_fim         DATE NOT NULL DEFAULT '9999-12-31',
    eh_vigente       BOOLEAN NOT NULL DEFAULT TRUE,
    hash_linha       VARCHAR(64),
    UNIQUE (id_funcionario, data_efetiva)
);
CREATE INDEX IF NOT EXISTS ix_dim_vendedor_bk_vigente
    ON dw.dim_vendedor (id_funcionario) WHERE eh_vigente;

CREATE TABLE IF NOT EXISTS dw.dim_territorio (
    chave_territorio       SERIAL PRIMARY KEY,
    id_territorio          INTEGER NOT NULL UNIQUE,
    nome_territorio        VARCHAR(100),
    codigo_pais_regiao     VARCHAR(10),
    grupo_territorio       VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dw.dim_promocao (
    chave_promocao      SERIAL PRIMARY KEY,
    id_oferta_especial  INTEGER NOT NULL UNIQUE, 
    descricao           VARCHAR(255),
    percentual_desconto NUMERIC(5,4),
    tipo_promocao       VARCHAR(50),
    categoria_promocao  VARCHAR(50),
    data_inicio         DATE,
    data_fim            DATE
);

CREATE TABLE IF NOT EXISTS dw.dim_metodo_envio (
    chave_metodo_envio   SERIAL PRIMARY KEY,
    id_metodo_envio      INTEGER NOT NULL UNIQUE, 
    nome                 VARCHAR(100),
    base_envio           NUMERIC(10,2),
    taxa_envio           NUMERIC(10,2)
);

INSERT INTO dw.dim_cliente (chave_cliente, id_cliente, nome_cliente, tipo_cliente, eh_vigente)
VALUES (-1, -1, 'Desconhecido', 'N/A', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO dw.dim_produto (chave_produto, id_produto, nome_produto, eh_vigente)
VALUES (-1, -1, 'Desconhecido', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO dw.dim_vendedor (chave_vendedor, id_funcionario, nome_completo, eh_vigente)
VALUES (-1, -1, 'Desconhecido', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO dw.dim_territorio (chave_territorio, id_territorio, nome_territorio)
VALUES (-1, -1, 'Desconhecido') ON CONFLICT DO NOTHING;
INSERT INTO dw.dim_promocao (chave_promocao, id_oferta_especial, descricao)
VALUES (-1, -1, 'Sem promoção') ON CONFLICT DO NOTHING;
INSERT INTO dw.dim_metodo_envio (chave_metodo_envio, id_metodo_envio, nome)
VALUES (-1, -1, 'Desconhecido') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS dw.fato_vendas (
    chave_venda                BIGSERIAL PRIMARY KEY,
    chave_data_pedido          INTEGER NOT NULL REFERENCES dw.dim_data(chave_data),
    chave_data_envio           INTEGER REFERENCES dw.dim_data(chave_data),
    chave_data_vencimento      INTEGER REFERENCES dw.dim_data(chave_data),
    chave_cliente              INTEGER NOT NULL REFERENCES dw.dim_cliente(chave_cliente),
    chave_produto              INTEGER NOT NULL REFERENCES dw.dim_produto(chave_produto),
    chave_vendedor             INTEGER NOT NULL REFERENCES dw.dim_vendedor(chave_vendedor),
    chave_territorio           INTEGER NOT NULL REFERENCES dw.dim_territorio(chave_territorio),
    chave_promocao             INTEGER NOT NULL REFERENCES dw.dim_promocao(chave_promocao),
    chave_metodo_envio         INTEGER NOT NULL REFERENCES dw.dim_metodo_envio(chave_metodo_envio),

    numero_pedido_venda        VARCHAR(20) NOT NULL,
    numero_linha_pedido        SMALLINT NOT NULL,
    id_detalhe_pedido          INTEGER NOT NULL,    

    quantidade_pedido          INTEGER NOT NULL,
    preco_unitario             NUMERIC(12,4) NOT NULL,
    desconto_preco_unitario    NUMERIC(6,4) NOT NULL DEFAULT 0,
    valor_desconto             NUMERIC(14,4) NOT NULL DEFAULT 0,
    total_linha                NUMERIC(14,4) NOT NULL,
    custo_padrao               NUMERIC(14,4) NOT NULL,
    valor_imposto              NUMERIC(14,4) NOT NULL DEFAULT 0,
    frete                      NUMERIC(14,4) NOT NULL DEFAULT 0,

    data_modificacao_origem    TIMESTAMP NOT NULL,
    marca_tempo_carregamento   TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (id_detalhe_pedido)
);

CREATE INDEX IF NOT EXISTS ix_fato_vendas_data_pedido ON dw.fato_vendas (chave_data_pedido);
CREATE INDEX IF NOT EXISTS ix_fato_vendas_cliente   ON dw.fato_vendas (chave_cliente);
CREATE INDEX IF NOT EXISTS ix_fato_vendas_produto    ON dw.fato_vendas (chave_produto);
CREATE INDEX IF NOT EXISTS ix_fato_vendas_vendedor   ON dw.fato_vendas (chave_vendedor);
CREATE INDEX IF NOT EXISTS ix_fato_vendas_territorio ON dw.fato_vendas (chave_territorio);

CREATE TABLE IF NOT EXISTS stg.cliente (
    id_cliente INTEGER, nome_pessoa VARCHAR(150), nome_loja VARCHAR(150),
    tipo_cliente VARCHAR(20), cidade VARCHAR(100), estado_provincia VARCHAR(100),
    pais_regiao VARCHAR(100), codigo_postal VARCHAR(20), data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.produto (
    id_produto INTEGER, nome_produto VARCHAR(150), numero_produto VARCHAR(30),
    cor VARCHAR(30), tamanho VARCHAR(10), nome_subcategoria VARCHAR(100),
    nome_categoria VARCHAR(100), custo_padrao NUMERIC(12,4), preco_tabela NUMERIC(12,4),
    data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.vendedor (
    id_funcionario INTEGER, nome_completo VARCHAR(150), cargo VARCHAR(100),
    data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.territorio (
    id_territorio INTEGER, nome_territorio VARCHAR(100),
    codigo_pais_regiao VARCHAR(10), grupo_territorio VARCHAR(50), data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.oferta_especial (
    id_oferta_especial INTEGER, descricao VARCHAR(255), percentual_desconto NUMERIC(5,4),
    tipo_promocao VARCHAR(50), categoria_promocao VARCHAR(50),
    data_inicio DATE, data_fim DATE, data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.metodo_envio (
    id_metodo_envio INTEGER, nome VARCHAR(100), base_envio NUMERIC(10,2),
    taxa_envio NUMERIC(10,2), data_modificacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg.detalhe_pedido_venda (
    id_detalhe_pedido INTEGER, numero_pedido_venda VARCHAR(20),
    numero_linha_pedido SMALLINT, data_pedido DATE, data_envio DATE, data_vencimento DATE,
    id_cliente INTEGER, id_produto INTEGER, id_funcionario INTEGER,
    id_territorio INTEGER, id_oferta_especial INTEGER, id_metodo_envio INTEGER,
    quantidade_pedido INTEGER, preco_unitario NUMERIC(12,4), desconto_preco_unitario NUMERIC(6,4),
    total_linha NUMERIC(14,4), valor_imposto NUMERIC(14,4), frete NUMERIC(14,4),
    data_modificacao TIMESTAMP
);

COMMENT ON SCHEMA dw IS 'Data Warehouse dimensional - modelo estrela de Vendas AdventureWorks';
COMMENT ON SCHEMA stg IS 'Área de staging da ETL - dados extraídos incrementalmente da origem OLTP';
COMMENT ON SCHEMA ctrl IS 'Metadados de controle de execução da ETL (watermarks e logs)';
