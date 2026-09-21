import json
import duckdb
import pandas as pd
from datetime import datetime

DB_PATH = "cafenorte_analytics.duckdb"

def run_pipeline():
    print("=== Iniciando Pipeline de Datos CaféNorte ===")
    con = duckdb.connect(DB_PATH)
    
    # 1. Ingesta y desanidado de inventory.json
    print("[1/5] Procesando inventory.json (metadatos, mapeos, catálogo y snapshots)...")
    with open('data/inventory.json', 'r', encoding='utf-8') as f:
        inv = json.load(f)
        
    df_tiendas = pd.DataFrame(inv['tiendas_info'])
    df_mappings = pd.DataFrame(inv['sku_mappings'])
    df_snapshots = pd.DataFrame(inv['snapshots'])
    
    # Desanidar catálogo y su historial de costos
    cat_records = []
    cost_records = []
    for p in inv['catalogo']['productos']:
        sku_erp = p['sku_erp']
        cat_records.append({
            'sku_erp': sku_erp,
            'nombre': p.get('nombre'),
            'categoria': p.get('categoria')
        })
        for ch in p.get('cost_history', []):
            cost_records.append({
                'sku_erp': sku_erp,
                'fecha_vigencia': ch.get('fecha_vigencia'),
                'costo_mxn': ch.get('costo_mxn'),
                'proveedor': ch.get('proveedor')
            })
            
    df_catalogo = pd.DataFrame(cat_records)
    df_costos = pd.DataFrame(cost_records)
    
    con.register('raw_tiendas', df_tiendas)
    con.register('raw_mappings', df_mappings)
    con.register('raw_snapshots', df_snapshots)
    con.register('raw_catalogo', df_catalogo)
    con.register('raw_costos', df_costos)
    
    con.execute("CREATE OR REPLACE TABLE dim_tiendas AS SELECT * FROM raw_tiendas;")
    con.execute("CREATE OR REPLACE TABLE dim_sku_mappings AS SELECT * FROM raw_mappings;")
    con.execute("CREATE OR REPLACE TABLE dim_catalogo AS SELECT * FROM raw_catalogo;")
    
    # Tabla de costos con rango de fechas [fecha_inicio, fecha_fin) para cruce SCD Tipo 2
    con.execute("""
        CREATE OR REPLACE TABLE dim_costos_historicos AS
        WITH ranked AS (
            SELECT 
                sku_erp,
                CAST(fecha_vigencia AS DATE) AS fecha_inicio,
                LEAD(CAST(fecha_vigencia AS DATE), 1, DATE '2099-12-31') OVER (
                    PARTITION BY sku_erp ORDER BY fecha_vigencia
                ) AS fecha_fin,
                costo_mxn,
                proveedor
            FROM raw_costos
        )
        SELECT * FROM ranked;
    """)
    
    # Limpieza robusta: TRY_CAST convierte 'N/A' y strings inválidos a NULL, luego COALESCE a 0
    con.execute("""
        CREATE OR REPLACE TABLE fct_inventario_diario AS
        SELECT 
            CAST(fecha AS DATE) AS fecha,
            tienda_id,
            sku_erp,
            COALESCE(TRY_CAST(cantidad_en_stock AS INTEGER), 0) AS cantidad_en_stock
        FROM raw_snapshots;
    """)

    # 2. Ingesta de tipos de cambio
    print("[2/5] Ingestando exchange_rates.csv...")
    con.execute("""
        CREATE OR REPLACE TABLE dim_exchange_rates AS
        SELECT 
            CAST(fecha AS DATE) AS fecha,
            currency,
            CAST(rate_to_mxn AS DOUBLE) AS rate_to_mxn
        FROM read_csv_auto('data/exchange_rates.csv');
    """)

    # 3. Ingesta y normalización de Ventas Físicas (POS)
    print("[3/5] Procesando ventas físicas (sales.csv)...")
    con.execute("""
        CREATE OR REPLACE TABLE stg_ventas_fisicas AS
        SELECT 
            s.venta_id,
            CAST(s.fecha_hora AS TIMESTAMP) AS fecha_hora,
            CAST(s.fecha_hora AS DATE) AS fecha,
            'Fisico' AS canal,
            s.tienda_id,
            m.sku_erp,
            s.sku AS sku_origen,
            s.cantidad,
            s.monto AS monto_bruto_origen,
            s.moneda AS moneda_origen,
            s.monto AS monto_neto_mxn,
            c.costo_mxn AS costo_unitario_mxn,
            (c.costo_mxn * s.cantidad) AS costo_total_mxn,
            (s.monto - (c.costo_mxn * s.cantidad)) AS margen_mxn
        FROM read_csv_auto('data/sales.csv') s
        LEFT JOIN dim_sku_mappings m ON s.sku = m.sku_pos
        LEFT JOIN dim_costos_historicos c 
            ON m.sku_erp = c.sku_erp 
           AND CAST(s.fecha_hora AS DATE) >= c.fecha_inicio 
           AND CAST(s.fecha_hora AS DATE) < c.fecha_fin;
    """)

    # 4. Ingesta y normalización de Ventas E-commerce (Shopify)
    print("[4/5] Procesando ecommerce_orders.parquet y convirtiendo divisas...")
    con.execute("""
        CREATE OR REPLACE TABLE stg_ventas_ecommerce AS
        SELECT 
            e.order_id AS venta_id,
            CAST(e.fecha AS TIMESTAMP) AS fecha_hora,
            CAST(e.fecha AS DATE) AS fecha,
            'E-commerce' AS canal,
            'ONLINE' AS tienda_id,
            m.sku_erp,
            e.product_handle AS sku_origen,
            e.cantidad,
            e.amount AS monto_bruto_origen,
            e.currency AS moneda_origen,
            CASE 
                WHEN e.currency = 'MXN' THEN e.amount
                ELSE e.amount * COALESCE(xr.rate_to_mxn, 1.0)
            END AS monto_neto_mxn,
            c.costo_mxn AS costo_unitario_mxn,
            (c.costo_mxn * e.cantidad) AS costo_total_mxn,
            ((CASE 
                WHEN e.currency = 'MXN' THEN e.amount
                ELSE e.amount * COALESCE(xr.rate_to_mxn, 1.0)
            END) - (c.costo_mxn * e.cantidad)) AS margen_mxn
        FROM read_parquet('data/ecommerce_orders.parquet') e
        LEFT JOIN dim_sku_mappings m ON e.product_handle = m.handle
        LEFT JOIN dim_exchange_rates xr 
            ON CAST(e.fecha AS DATE) = xr.fecha 
           AND e.currency = xr.currency
        LEFT JOIN dim_costos_historicos c 
            ON m.sku_erp = c.sku_erp 
           AND CAST(e.fecha AS DATE) >= c.fecha_inicio 
           AND CAST(e.fecha AS DATE) < c.fecha_fin;
    """)

    # 5. Consolidación de Hechos: Ventas Unificadas
    print("[5/5] Consolidando tabla analítica fct_ventas_unificadas...")
    con.execute("""
        CREATE OR REPLACE TABLE fct_ventas_unificadas AS
        SELECT * FROM stg_ventas_fisicas
        UNION ALL
        SELECT * FROM stg_ventas_ecommerce;
    """)
    
    total_sales = con.execute("SELECT count(*), sum(monto_neto_mxn) FROM fct_ventas_unificadas;").fetchone()
    print(f"\n[ÉXITO] Pipeline completado. Ventas totales unificadas: {total_sales[0]:,} transacciones por ${total_sales[1]:,.2f} MXN.")
    con.close()

if __name__ == "__main__":
    run_pipeline()