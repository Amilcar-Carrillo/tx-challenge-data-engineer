Set-Content -Path AI_LOG.md -Encoding UTF8 -Value @'
# Bitácora de Uso de IA (AI_LOG.md)
**Proyecto:** Pipeline y Modelo Analítico CaféNorte  
**Candidato:** Data Solutions Engineer  

---

## 1. Herramientas y Flujo de Trabajo
* **Modelo principal:** Gemini / Claude como copilotos interactivos de diseño y codificación.
* **Entorno:** Terminal integrada de VS Code / PowerShell bajo Windows 11.
* **Flujo de orquestación:** Modo interactivo iterativo por fases:
  1. *Exploración de datos:* Creación de scripts ad-hoc de introspección para archivos heterogéneos (Parquet, JSON de 31 MB y CSVs).
  2. *Diseño arquitectónico:* Propuesta de modelado dimensional desacoplado y selección de stack analítico local (DuckDB + Python).
  3. *Auditoría de negocio:* Formulación de consultas analíticas (rotación, quiebres consecutivos vía window functions, MoM y márgenes negativos).

---

## 2. Prompts Clave y Decisiones de Ingeniería

### Prompt 1: Inspección del archivo grande `inventory.json`
* **Prompt:**  
  > "Tengo un archivo inventory.json de 31MB. DuckDB falla con maximum_object_size exceeded. Escribe un script en Python que analice su estructura sin saturar memoria y me muestre cómo vienen el catálogo, los costos y los snapshots."
* **Respuesta de la IA:**  
  Propuso un script utilizando `json.load()` estándar para extraer las claves raíz y mostrar muestras de los primeros elementos de `tiendas_info`, `sku_mappings`, `catalogo` y `snapshots`.
* **Decisión tomada:**  
  **Aceptada y adaptada.** Permitió descubrir que `inventory.json` contenía un modelo dimensional implícito (SCD Tipo 2 en `cost_history` y mapeo de identificadores para resolver la heterogeneidad entre Shopify y el POS).

### Prompt 2: Cálculo de Quiebres de Stock Consecutivos (Pregunta 2)
* **Prompt:**  
  > "Necesito identificar en SQL las tiendas con quiebres de stock (stock == 0) de más de 3 días consecutivos en el trimestre 2026-01-01 a 2026-03-31 sobre la tabla fct_inventario_diario."
* **Respuesta de la IA:**  
  Generó una consulta con la técnica clásica de islas y lagunas (Gaps & Islands):  
  `fecha - ROW_NUMBER() OVER (PARTITION BY tienda_id, sku_erp, es_quiebre ORDER BY fecha)`.
* **Decisión tomada:**  
  **Modificada.** La IA inicialmente no acotaba los quiebres estrictamente dentro del rango de fechas antes de particionar, lo que podía arrastrar eventos de meses anteriores. Se agregó el filtro del trimestre en el CTE base y se agruparon los quiebres por sucursal y región para entregar un reporte ejecutivo de valor para operaciones.

### Prompt 3: Homologación Multimoneda y Cálculo de Margen Real (Preguntas 3 y 4)
* **Prompt:**  
  > "Escribe la lógica en SQL/DuckDB para unificar ventas físicas y de Shopify, convirtiendo USD y EUR a MXN según la fecha de la orden, y cruzando cada venta con el costo unitario vigente del producto a la fecha de la transacción."
* **Respuesta de la IA:**  
  Propuso un join directo de igualdad de fechas entre ventas y la tabla de costos.
* **Decisión tomada:**  
  **Modificada sustancialmente.** Un join por igualdad de fecha entre transacciones y `fecha_vigencia` de costos dejaba nulas la mayoría de las ventas, ya que el costo solo cambia esporádicamente. Se diseñó en su lugar una tabla de vigencias usando `LEAD()` con rangos semiabiertos `[fecha_inicio, fecha_fin)` y un join condicional `fecha >= fecha_inicio AND fecha < fecha_fin`.

---

## 3. Caso Concreto de Error / Propuesta Subóptima Detectada

* **El Error:**  
  Al generar el pipeline de ingesta de `snapshots` de inventario, la IA asumió tipos de datos numéricos puros y escribió:  
  `CAST(cantidad_en_stock AS INTEGER) AS cantidad_en_stock`  
  Al ejecutar `main.py`, DuckDB falló de inmediato con la excepción:  
  `_duckdb.ConversionException: Could not convert string 'N/A' to INT32 when casting from source column cantidad_en_stock`.

* **Detección y Causa Raíz:**  
  El ERP legacy contenía datos ruidosos donde las faltas de reporte o productos sin inventario se capturaron como la cadena `'N/A'` en lugar de números o valores nulos.
* **Corrección:**  
  Se rechazó el `CAST` rígido sugerido por la IA y se reemplazó por:  
  `COALESCE(TRY_CAST(cantidad_en_stock AS INTEGER), 0) AS cantidad_en_stock`  
  Esto permitió procesar los 230,776 snapshots sin truncar el pipeline y garantizó consistencia matemática en el cálculo del inventario promedio diario.

---

## 4. Autocrítica Final

El valor del asistente de IA radicó en acelerar la escritura de código boilerplate (desanidado de JSON a DataFrames, sintaxis inicial de queries analíticas y generación de mocks de prueba). Sin embargo, el **100% de la arquitectura, la detección de la naturaleza SCD Tipo 2 en los costos, la formulación de islas/lagunas para quiebres consecutivos y el diseño de una arquitectura AWS serverless de bajo costo ($50 USD/mes vs $200 USD presupuestados) fue producto del juicio técnico humano**. 

La validez de los resultados no se midió porque el código "corriera sin error", sino auditando la lógica de negocio: verificando que las ventas totales unificadas ($35.17M MXN) concordaran con la suma de fuentes y contrastando que los márgenes negativos respondieran a discrepancias reales entre listas de precios y costos de proveedores.
'@