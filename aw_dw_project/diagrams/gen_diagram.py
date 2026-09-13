import graphviz

g = graphviz.Digraph('star_schema', format='png')
g.attr(rankdir='TB', bgcolor='white', fontname='Helvetica', splines='ortho')
g.attr('node', shape='plaintext', fontname='Helvetica')

FACT_COLOR = "#003B53"
DIM_COLOR = "#93BB25"
HEADER_TEXT = "white"

def fact_table(name, title, cols):
    rows = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="11">{c}</FONT></TD></TR>'
        for c in cols
    )
    label = f'''<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white" COLOR="{FACT_COLOR}">
    <TR><TD BGCOLOR="{FACT_COLOR}"><FONT COLOR="{HEADER_TEXT}" POINT-SIZE="13"><B>{title}</B></FONT></TD></TR>
    {rows}
    </TABLE>>'''
    g.node(name, label=label)

def dim_table(name, title, cols):
    rows = "".join(
        f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="11">{c}</FONT></TD></TR>'
        for c in cols
    )
    label = f'''<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white" COLOR="{DIM_COLOR}">
    <TR><TD BGCOLOR="{DIM_COLOR}"><FONT COLOR="white" POINT-SIZE="13"><B>{title}</B></FONT></TD></TR>
    {rows}
    </TABLE>>'''
    g.node(name, label=label)

fact_table("fact_sales", "FACT_SALES", [
    "PK sales_key",
    "FK order_date_key",
    "FK ship_date_key",
    "FK due_date_key",
    "FK customer_key",
    "FK product_key",
    "FK salesperson_key",
    "FK territory_key",
    "FK promotion_key",
    "FK ship_method_key",
    "sales_order_number (DD)",
    "sales_order_line_number (DD)",
    "order_qty",
    "unit_price",
    "unit_price_discount",
    "discount_amount",
    "line_total",
    "standard_cost",
    "tax_amt",
    "freight",
])

dim_table("dim_date", "DIM_DATE", [
    "PK date_key",
    "full_date", "day_of_month", "day_name",
    "month_number", "month_name", "quarter",
    "year", "is_weekend", "fiscal_year", "fiscal_quarter",
])
dim_table("dim_customer", "DIM_CUSTOMER (SCD2)", [
    "PK customer_key", "customer_id (BK)",
    "customer_name", "customer_type",
    "city", "state_province", "country_region",
    "postal_code", "effective_date", "end_date", "is_current",
])
dim_table("dim_product", "DIM_PRODUCT (SCD2)", [
    "PK product_key", "product_id (BK)",
    "product_name", "product_number", "color", "size",
    "subcategory_name", "category_name",
    "standard_cost", "list_price",
    "effective_date", "end_date", "is_current",
])
dim_table("dim_salesperson", "DIM_SALESPERSON (SCD2)", [
    "PK salesperson_key", "employee_id (BK)",
    "full_name", "job_title",
    "effective_date", "end_date", "is_current",
])
dim_table("dim_territory", "DIM_TERRITORY", [
    "PK territory_key", "territory_id (BK)",
    "territory_name", "country_region_code", "territory_group",
])
dim_table("dim_promotion", "DIM_PROMOTION", [
    "PK promotion_key", "special_offer_id (BK)",
    "description", "discount_pct", "promotion_type",
    "promotion_category", "start_date", "end_date",
])
dim_table("dim_ship_method", "DIM_SHIP_METHOD", [
    "PK ship_method_key", "ship_method_id (BK)",
    "name", "ship_base", "ship_rate",
])

for d in ["dim_date", "dim_customer", "dim_product", "dim_salesperson",
          "dim_territory", "dim_promotion", "dim_ship_method"]:
    g.edge(d, "fact_sales", arrowhead="none", color="#666666")

g.render('/home/claude/aw_dw_project/diagrams/star_schema', format='png', cleanup=True)
print("done")
