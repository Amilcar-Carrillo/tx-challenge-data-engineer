import duckdb
import pandas as pd

DB_PATH = "cafenorte_analytics.duckdb"

def get_connection():
    return duckdb.connect(DB_PATH)

def answer_q1_inventory_turnover(con):
    """
    Pregunta 1: Top 10 SKUs por rotacion de inventario en los ultimos 6 meses.
    Criterio:
      - Fecha maxima: 2026-03-31. Ultimos 6 meses: 2025-10-01 a 2026-03-31.
      - Rotacion = Unidades Vendidas (fisico + online) / Inventario Promedio Diario en Unidades.
    """
    query = """
    WITH date_range AS (
        SELECT DATE '2025-10-01' AS f_inicio, DATE '2026-03-31' AS f_fin
    ),
    ventas_sku AS (
        SELECT 
            v.sku_erp,
            SUM(v.cantidad) AS unidades_vendidas
        FROM fct_ventas_unificadas v, date_range dr
        WHERE v.fecha BETWEEN dr.f_inicio AND dr.f_fin
          AND v.sku_erp IS NOT NULL
        GROUP BY v.sku_erp
    ),
    inv_sku AS (
        SELECT 
            i.sku_erp,
            AVG(i.cantidad_en_stock) AS inventario_promedio
        FROM fct_inventario_diario i, date_range dr
        WHERE i.fecha BETWEEN dr.f_inicio AND dr.f_fin
        GROUP BY i.sku_erp
    )
    SELECT 
        v.sku_erp,
        c.nombre AS producto,
        c.categoria,
        v.unidades_vendidas,
        ROUND(i.inventario_promedio, 2) AS stock_promedio,
        ROUND(v.unidades_vendidas / NULLIF(i.inventario_promedio, 0), 2) AS rotacion_inventario
    FROM ventas_sku v
    JOIN inv_sku i ON v.sku_erp = i.sku_erp
    LEFT JOIN dim_catalogo c ON v.sku_erp = c.sku_erp
    ORDER BY rotacion_inventario DESC
    LIMIT 10;
    """
    return con.execute(query).df()

def answer_q2_stockouts(con):
    """
    Pregunta 2: Tiendas con quiebres de stock de mas de 3 dias consecutivos en el ultimo trimestre.
    Criterio:
      - Ultimo trimestre: 2026-01-01 a 2026-03-31.
      - Quiebre: cantidad_en_stock == 0 durante mas de 3 dias consecutivos.
    """
    query = """
    WITH trimestre_inv AS (
        SELECT 
            fecha,
            tienda_id,
            sku_erp,
            cantidad_en_stock,
            CASE WHEN cantidad_en_stock = 0 THEN 1 ELSE 0 END AS es_quiebre
        FROM fct_inventario_diario
        WHERE fecha BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
    ),
    consecutivos AS (
        SELECT 
            fecha,
            tienda_id,
            sku_erp,
            es_quiebre,
            fecha - CAST(ROW_NUMBER() OVER (PARTITION BY tienda_id, sku_erp, es_quiebre ORDER BY fecha) AS INTEGER) AS grupo_consecutivo
        FROM trimestre_inv
        WHERE es_quiebre = 1
    ),
    duracion_quiebres AS (
        SELECT 
            tienda_id,
            sku_erp,
            COUNT(*) AS dias_consecutivos_sin_stock,
            MIN(fecha) AS fecha_inicio_quiebre,
            MAX(fecha) AS fecha_fin_quiebre
        FROM consecutivos
        GROUP BY tienda_id, sku_erp, grupo_consecutivo
        HAVING COUNT(*) > 3
    )
    SELECT 
        d.tienda_id,
        t.ciudad,
        t.region,
        COUNT(DISTINCT d.sku_erp) AS skus_con_quiebre_mayor_3_dias,
        MAX(d.dias_consecutivos_sin_stock) AS max_dias_consecutivos_quiebre,
        COUNT(*) AS eventos_quiebre_mayor_3_dias
    FROM duracion_quiebres d
    LEFT JOIN dim_tiendas t ON d.tienda_id = t.tienda_id
    GROUP BY d.tienda_id, t.ciudad, t.region
    ORDER BY eventos_quiebre_mayor_3_dias DESC;
    """
    return con.execute(query).df()

def answer_q3_mom_growth(con):
    """
    Pregunta 3: Crecimiento mes a mes (MoM) de ventas por canal en el ultimo año.
    Criterio:
      - Periodo: 2025-04-01 a 2026-03-31.
      - MoM % = (Venta_Actual - Venta_Anterior) / Venta_Anterior * 100
    """
    query = """
    WITH mensual AS (
        SELECT 
            STRFTIME(fecha, '%Y-%m') AS anio_mes,
            canal,
            SUM(monto_neto_mxn) AS venta_neta_mxn
        FROM fct_ventas_unificadas
        WHERE fecha >= DATE '2025-04-01' AND fecha <= DATE '2026-03-31'
        GROUP BY 1, 2
    ),
    calculo_mom AS (
        SELECT 
            anio_mes,
            canal,
            ROUND(venta_neta_mxn, 2) AS venta_mxn,
            LAG(venta_neta_mxn) OVER (PARTITION BY canal ORDER BY anio_mes) AS venta_mes_anterior,
            ROUND(
                ((venta_neta_mxn - LAG(venta_neta_mxn) OVER (PARTITION BY canal ORDER BY anio_mes)) 
                 / NULLIF(LAG(venta_neta_mxn) OVER (PARTITION BY canal ORDER BY anio_mes), 0)) * 100, 
                2
            ) AS crecimiento_mom_pct
        FROM mensual
    )
    SELECT * FROM calculo_mom
    ORDER BY anio_mes, canal;
    """
    return con.execute(query).df()

def answer_q4_negative_margins(con):
    """
    Pregunta 4: Productos con margen negativo y tiendas donde ocurren.
    """
    query = """
    SELECT 
        v.tienda_id,
        COALESCE(t.ciudad, 'Canal Digital') AS ciudad,
        v.canal,
        v.sku_erp,
        c.nombre AS producto,
        COUNT(*) AS num_transacciones_negativas,
        SUM(v.cantidad) AS unidades_afectadas,
        ROUND(SUM(v.monto_neto_mxn), 2) AS venta_total_mxn,
        ROUND(SUM(v.costo_total_mxn), 2) AS costo_total_mxn,
        ROUND(SUM(v.margen_mxn), 2) AS perdida_total_mxn
    FROM fct_ventas_unificadas v
    LEFT JOIN dim_tiendas t ON v.tienda_id = t.tienda_id
    LEFT JOIN dim_catalogo c ON v.sku_erp = c.sku_erp
    WHERE v.margen_mxn < 0
    GROUP BY v.tienda_id, t.ciudad, v.canal, v.sku_erp, c.nombre
    ORDER BY perdida_total_mxn ASC;
    """
    return con.execute(query).df()

def run_all_queries():
    con = get_connection()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    
    print("\n" + "="*80)
    print("PREGUNTA 1: TOP 10 SKUs POR ROTACION DE INVENTARIO (ULTIMOS 6 MESES)")
    print("="*80)
    q1 = answer_q1_inventory_turnover(con)
    print(q1.to_string(index=False))

    print("\n" + "="*80)
    print("PREGUNTA 2: TIENDAS CON QUIEBRES DE STOCK > 3 DIAS CONSECUTIVOS (ULTIMO TRIMESTRE)")
    print("="*80)
    q2 = answer_q2_stockouts(con)
    print(q2.to_string(index=False))

    print("\n" + "="*80)
    print("PREGUNTA 3: CRECIMIENTO MoM DE VENTAS POR CANAL (ULTIMO AÑO)")
    print("="*80)
    q3 = answer_q3_mom_growth(con)
    print(q3.to_string(index=False))

    print("\n" + "="*80)
    print("PREGUNTA 4: PRODUCTOS CON MARGEN NEGATIVO Y TIENDAS AFECTADAS")
    print("="*80)
    q4 = answer_q4_negative_margins(con)
    if len(q4) == 0:
        print("No se registraron transacciones con margen negativo.")
    else:
        print(q4.to_string(index=False))
        
    con.close()

if __name__ == "__main__":
    run_all_queries()