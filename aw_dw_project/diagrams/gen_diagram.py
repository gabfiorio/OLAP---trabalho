import os
import graphviz

g = graphviz.Digraph('esquema_estrela', format='png')
g.attr(rankdir='TB', bgcolor='white', fontname='Helvetica', splines='ortho')
g.attr('node', shape='plaintext', fontname='Helvetica')

COR_FATO = "#003B53"
COR_DIMENSAO = "#93BB25"
TEXTO_CABECALHO = "white"


def tabela_fato(nome, titulo, colunas):
    linhas = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="11">{coluna}</FONT></TD></TR>'
        for coluna in colunas
    )
    label = f'''<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white" COLOR="{COR_FATO}">
    <TR><TD BGCOLOR="{COR_FATO}"><FONT COLOR="{TEXTO_CABECALHO}" POINT-SIZE="13"><B>{titulo}</B></FONT></TD></TR>
    {linhas}
    </TABLE>>'''
    g.node(nome, label=label)


def tabela_dimensao(nome, titulo, colunas):
    linhas = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="11">{coluna}</FONT></TD></TR>'
        for coluna in colunas
    )
    label = f'''<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white" COLOR="{COR_DIMENSAO}">
    <TR><TD BGCOLOR="{COR_DIMENSAO}"><FONT COLOR="white" POINT-SIZE="13"><B>{titulo}</B></FONT></TD></TR>
    {linhas}
    </TABLE>>'''
    g.node(nome, label=label)


tabela_fato("fato_vendas", "FATO_VENDAS", [
    "PK chave_venda",
    "FK chave_data_pedido",
    "FK chave_data_entrega",
    "FK chave_data_vencimento",
    "FK chave_cliente",
    "FK chave_produto",
    "FK chave_vendedor",
    "FK chave_territorio",
    "FK chave_promocao",
    "FK chave_metodo_envio",
    "numero_pedido_venda (DD)",
    "numero_linha_pedido (DD)",
    "quantidade_pedido",
    "preco_unitario",
    "desconto_unitario",
    "valor_desconto",
    "total_linha",
    "custo_padrao",
    "valor_imposto",
    "frete",
])


tabela_dimensao("dim_data", "DIM_DATA", [
    "PK chave_data",
    "data_completa", "dia_do_mes", "nome_dia",
    "numero_mes", "nome_mes", "trimestre",
    "ano", "eh_fim_de_semana", "ano_fiscal", "trimestre_fiscal",
])

tabela_dimensao("dim_cliente", "DIM_CLIENTE (SCD2)", [
    "PK chave_cliente", "cliente_id (BK)",
    "nome_cliente", "tipo_cliente",
    "cidade", "estado_provincia", "regiao_pais",
    "codigo_postal", "data_efetiva", "data_fim", "eh_atual",
])

tabela_dimensao("dim_produto", "DIM_PRODUTO (SCD2)", [
    "PK chave_produto", "produto_id (BK)",
    "nome_produto", "numero_produto", "cor", "tamanho",
    "nome_subcategoria", "nome_categoria",
    "custo_padrao", "preco_tabela",
    "data_efetiva", "data_fim", "eh_atual",
])

tabela_dimensao("dim_vendedor", "DIM_VENDEDOR (SCD2)", [
    "PK chave_vendedor", "funcionario_id (BK)",
    "nome_completo", "cargo",
    "data_efetiva", "data_fim", "eh_atual",
])

tabela_dimensao("dim_territorio", "DIM_TERRITORIO", [
    "PK chave_territorio", "territorio_id (BK)",
    "nome_territorio", "codigo_regiao_pais", "grupo_territorio",
])

tabela_dimensao("dim_promocao", "DIM_PROMOCAO", [
    "PK chave_promocao", "oferta_especial_id (BK)",
    "descricao", "percentual_desconto", "tipo_promocao",
    "categoria_promocao", "data_inicio", "data_fim",
])

tabela_dimensao("dim_metodo_envio", "DIM_METODO_ENVIO", [
    "PK chave_metodo_envio", "metodo_envio_id (BK)",
    "nome", "custo_base", "tarifa_envio",
])

for d in ["dim_data", "dim_cliente", "dim_produto", "dim_vendedor",
          "dim_territorio", "dim_promocao", "dim_metodo_envio"]:
    g.edge(d, "fato_vendas", arrowhead="none", color="#666666")

caminho_saida = os.path.join(os.path.dirname(__file__), 'esquema_estrela')
g.render(caminho_saida, format='png', cleanup=True)
print("concluído")
