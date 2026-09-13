import os
import graphviz

g = graphviz.Digraph("esquema_estrela", format="png")
g.attr(rankdir="TB", bgcolor="white", fontname="Helvetica", splines="ortho")
g.attr("node", shape="plaintext", fontname="Helvetica")

COR_FATO = "#003B53"
COR_DIMENSAO = "#93BB25"
TEXTO_CABECALHO = "white"


def tabela_fato(nome, titulo, colunas):
    linhas = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="10">{coluna}</FONT></TD></TR>'
        for coluna in colunas
    )
    label = f"""<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="white" COLOR="{COR_FATO}">
    <TR><TD BGCOLOR="{COR_FATO}"><FONT COLOR="{TEXTO_CABECALHO}" POINT-SIZE="13"><B>{titulo}</B></FONT></TD></TR>
    {linhas}
    </TABLE>>"""
    g.node(nome, label=label)


def tabela_dimensao(nome, titulo, colunas):
    linhas = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="10">{coluna}</FONT></TD></TR>'
        for coluna in colunas
    )
    label = f"""<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="white" COLOR="{COR_DIMENSAO}">
    <TR><TD BGCOLOR="{COR_DIMENSAO}"><FONT COLOR="white" POINT-SIZE="13"><B>{titulo}</B></FONT></TD></TR>
    {linhas}
    </TABLE>>"""
    g.node(nome, label=label)


tabela_fato("fato_vendas", "FATO_VENDAS", [
    "PK chave_venda", "FK chave_data_pedido", "FK chave_data_envio",
    "FK chave_data_vencimento", "FK chave_cliente", "FK chave_produto",
    "FK chave_vendedor", "FK chave_territorio", "FK chave_promocao",
    "FK chave_metodo_envio", "numero_pedido_venda", "numero_linha_pedido",
    "id_detalhe_pedido", "quantidade_pedido", "preco_unitario",
    "desconto_preco_unitario", "valor_desconto", "total_linha", "custo_padrao",
    "valor_imposto", "frete", "data_modificacao_origem", "marca_tempo_carregamento",
])

tabela_dimensao("dim_data", "DIM_DATA (SCD0)", [
    "PK chave_data", "data_completa", "dia_mes", "nome_dia", "dia_semana",
    "numero_mes", "nome_mes", "trimestre", "ano", "eh_fim_de_semana",
    "ano_fiscal", "trimestre_fiscal",
])

tabela_dimensao("dim_cliente", "DIM_CLIENTE (SCD2)", [
    "PK chave_cliente", "id_cliente (BK)", "nome_cliente", "tipo_cliente",
    "cidade", "estado_provincia", "pais_regiao", "codigo_postal",
    "data_efetiva", "data_fim", "eh_vigente", "hash_linha",
])

tabela_dimensao("dim_produto", "DIM_PRODUTO (SCD2)", [
    "PK chave_produto", "id_produto (BK)", "nome_produto", "numero_produto",
    "cor", "tamanho", "nome_subcategoria", "nome_categoria", "custo_padrao",
    "preco_tabela", "data_efetiva", "data_fim", "eh_vigente", "hash_linha",
])

tabela_dimensao("dim_vendedor", "DIM_VENDEDOR (SCD2)", [
    "PK chave_vendedor", "id_funcionario (BK)", "nome_completo", "cargo",
    "data_efetiva", "data_fim", "eh_vigente", "hash_linha",
])

tabela_dimensao("dim_territorio", "DIM_TERRITORIO (SCD1)", [
    "PK chave_territorio", "id_territorio (BK)", "nome_territorio",
    "codigo_pais_regiao", "grupo_territorio",
])

tabela_dimensao("dim_promocao", "DIM_PROMOCAO (SCD1)", [
    "PK chave_promocao", "id_oferta_especial (BK)", "descricao",
    "percentual_desconto", "tipo_promocao", "categoria_promocao",
    "data_inicio", "data_fim",
])

tabela_dimensao("dim_metodo_envio", "DIM_METODO_ENVIO (SCD1)", [
    "PK chave_metodo_envio", "id_metodo_envio (BK)", "nome", "base_envio",
    "taxa_envio",
])

for d in [
    "dim_data", "dim_cliente", "dim_produto", "dim_vendedor",
    "dim_territorio", "dim_promocao", "dim_metodo_envio"
]:
    g.edge(d, "fato_vendas", arrowhead="none", color="#666666")

caminho_saida = os.path.join(os.path.dirname(__file__), "star_schema")
g.render(caminho_saida, format="png", cleanup=True)
print(f"Diagrama gerado em {caminho_saida}.png")
