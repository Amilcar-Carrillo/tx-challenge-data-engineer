# CafeNorte Data Solutions Pipeline

Solucion integral de ingenieria de datos para la unificacion de ventas fisicas (POS), comercio electronico multimoneda (Shopify) y control de inventarios/costos (ERP legacy) para CafeNorte.

Desarrollado como parte del Reto Tecnico para Data Solutions Engineer en Tuxpas.

---

## 1. Arquitectura y Decisiones de Diseno

* DuckDB: Motor analitico columnar OLAP para procesar Parquet, CSVs y JSON complejo sin levantar infraestructura costosa.
* Python (Pandas / PyArrow): Ingesta y normalizacion de catalogos jerarquicos.
* Pytest: Suite automatizada de integridad de datos.

### Modelo Dimensional (cafenorte_analytics.duckdb)
* dim_tiendas: Sucursales fisicas y regiones.
* dim_catalogo: SKUs y categorias.
* dim_costos_historicos: Costos unitarios modelados como SCD Tipo 2.
* dim_exchange_rates: Tipos de cambio USD y EUR a MXN.
* fct_inventario_diario: Stock diario con limpieza de registros 'N/A'.
* fct_ventas_unificadas: Transacciones unificadas en MXN con margen calculado.

---

## 2. Respuestas a Preguntas de Negocio

### Pregunta 1: Top 10 SKUs por rotacion de inventario (Ultimos 6 meses)
* Criterio: Unidades Vendidas / Stock Promedio Diario (01-Oct-2025 al 31-Mar-2026).

1. ERP-PROV-MX-054-B (Espresso Cafe Molido): Rotacion 23.43 (928 unidades vendidas / 39.61 stock prom)
2. ERP-PROV-MX-047-B (Filtros Mercancia): Rotacion 22.99 (894 unidades vendidas / 38.88 stock prom)
3. ERP-PROV-MX-038-A (Seleccion Cafe Grano): Rotacion 22.55 (881 unidades vendidas / 39.06 stock prom)
4. ERP-PROV-MX-057-C (Premium Cafe Grano): Rotacion 22.39 (877 unidades vendidas / 39.16 stock prom)
5. ERP-PROV-MX-024-A (Americano Cafe Molido): Rotacion 22.27 (848 unidades vendidas / 38.08 stock prom)
6. ERP-PROV-MX-037-C (Tradicional Cafe Molido): Rotacion 22.25 (872 unidades vendidas / 39.19 stock prom)
7. ERP-PROV-MX-034-D (Estandar Cafe Molido): Rotacion 21.89 (865 unidades vendidas / 39.51 stock prom)
8. ERP-PROV-MX-059-B (Organico Cafe Grano): Rotacion 21.87 (867 unidades vendidas / 39.65 stock prom)
9. ERP-PROV-MX-010-D (Descafeinado Cafe Grano): Rotacion 21.73 (839 unidades vendidas / 38.61 stock prom)
10. ERP-PROV-MX-003-D (Filtros Mercancia): Rotacion 21.63 (842 unidades vendidas / 38.93 stock prom)

---

### Pregunta 2: Tiendas con quiebres de stock > 3 dias consecutivos (Ultimo trimestre)
* Criterio: Ventana 01-Ene-2026 al 31-Mar-2026 donde stock == 0 por mas de 3 dias consecutivos.

* T038 (Cancun, Sureste): 1 SKU afectado, maximo 4 dias consecutivos.
* T023 (Cancun, Sureste): 1 SKU afectado, maximo 4 dias consecutivos.
* T016 (CDMX, Centro): 1 SKU afectado, maximo 4 dias consecutivos.
* T015 (Reynosa, Frontera): 1 SKU afectado, maximo 4 dias consecutivos.

---

### Pregunta 3: Crecimiento MoM de ventas por canal (Ultimo ano)
* Criterio: Ventas en MXN de Abril 2025 a Marzo 2026.
* Canal Fisico: Promedio mensual ~$1.72M MXN. Picos en mayo (+7.40%), octubre (+7.93%) y marzo (+8.97%).
* E-commerce: Promedio mensual ~$350K MXN (~17% total). Mayor crecimiento en octubre (+8.99%) y marzo (+8.51%).

---

### Pregunta 4: Productos con margen negativo y tiendas afectadas
* Criterio: Transacciones donde Precio de Venta < Costo Unitario Vigente.
* ERP-PROV-MX-015-D (Especial Cafe Molido): Perdidas en 31 tiendas fisicas (lideradas por T036 Leon con -$11,927.46 MXN y T032 Guadalajara con -$8,158.63 MXN).
* ERP-PROV-MX-002-B (Sandwich Comida Caliente): Perdidas recurrentes en T013 Cd. Juarez, T036 Leon y T029 Nuevo Laredo.

---

## 3. Instrucciones de Ejecucion

1. Clonar el repositorio y crear entorno virtual:
   python -m venv .venv
   .venv\Scripts\Activate.ps1

2. Instalar dependencias:
   pip install -r requirements.txt

3. Ejecutar pipeline completo y consultas analiticas:
   python main.py

4. Ejecutar pruebas unitarias:
   pytest
