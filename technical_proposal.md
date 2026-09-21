# Propuesta Técnica: Plataforma Analítica Unificada CaféNorte
**Preparado para:** Dirección General y Dirección de TI — CaféNorte  
**Elaborado por:** Data Solutions Engineering  
**Fecha:** Septiembre 2026  
**Restricción Presupuestaria Clave:** $\le$ USD $200 / mes  

---

## 1. Resumen Ejecutivo
CaféNorte opera actualmente con datos fragmentados en tres silos: terminales de punto de venta (POS) en ~40 sucursales físicas, un ERP legacy con información de inventario y catálogos, y una tienda digital en Shopify con cobros multimoneda (MXN, USD, EUR). Esta dispersión provoca discrepancias de cifras entre áreas, falta de visibilidad en márgenes reales y riesgos operativos por quiebres de inventario.

Proponemos una **Arquitectura Serverless basada en AWS y DuckDB**, diseñada específicamente para unificar ventas e inventarios sin servidores aprovisionados 24/7, garantizando una única fuente de la verdad con un costo mensual proyectado de **USD $48 - $75**, muy por debajo del límite de **USD $200/mes**.

---

## 2. Arquitectura Propuesta en AWS

[Fuentes de Datos]
├── POS Sucursales (CSV diario)
├── ERP Legacy (JSON inventario/SCD2)
├── Shopify API (Parquet órdenes)
└── Tipos de Cambio (CSV / API Banxico)
│
▼ (Transferencia Segura SFTP / EventBridge Schedulers)
[Amazon S3 - Data Lakehouse]
├── s3://cafenorte-lakehouse/raw/ (Bronze: datos crudos inmutables)
├── s3://cafenorte-lakehouse/curated/ (Silver: Parquet normalizado y particionado)
└── s3://cafenorte-lakehouse/analytics/ (Gold: Modelos dimensionales estrella)
│
▼ (Orquestación diaria / micro-batch)
[Cómputo Serverless: AWS Lambda + DuckDB]
├── Ingesta y desanidado de JSON legacy
├── Conversión cambiaria dinámica (USD/EUR -> MXN)
└── Cálculo de márgenes históricos (SCD Tipo 2)
│
▼
[Consumo Analítico & BI]
├── Amazon Athena (SQL Serverless bajo demanda)
└── Conexión a Power BI / QuickSight / Metabase

### Justificación de Componentes
1. **Amazon S3 (Bronze / Silver / Gold)**: Almacenamiento desacoplado de alta durabilidad (99.999999999%). Los datos históricos y diarios se almacenan en formato Parquet comprimido con Snappy, optimizando espacio y costos de escaneo.
2. **Cómputo Serverless (AWS Lambda con Layer DuckDB / Polars)**: Para un volumen diario de ~80k transacciones y 230k snapshots, un clúster tipo EMR o Glue Spark representa un sobrecosto injustificado. DuckDB embebido en una función Lambda (o tarea Fargate Spot de 2 vCPU / 4 GB RAM) ejecuta el procesamiento completo en menos de 90 segundos a costo fraccionado por milisegundo.
3. **Servido Analítico (Amazon Athena)**: Motor de consultas interactivo serverless basado en Presto/Trino. Solo factura por volumen de datos escaneados ($5.00 USD por TB). Al consultar sobre Parquet particionado por `fecha` y `canal`, el escaneo mensual promedio no supera los 50 GB.
4. **Orquestación y Seguridad (AWS EventBridge + IAM + KMS)**: Ejecución calendarizada diaria (03:00 AM) con cifrado en reposo y principio de menor privilegio por rol.

---

## 3. Estimación de Costos Mensuales (AWS Pricing)

| Servicio | Detalle de Uso Estimado | Costo Mensual Proyectado (USD) |
| :--- | :--- | :---: |
| **Amazon S3** | ~35 GB de datos crudos y Parquet analítico + peticiones PUT/GET | $1.20 |
| **AWS Lambda** | 1 ejecución diaria de 90 s con 3 GB RAM (~4,050 GB-s/mes) | $0.15 |
| **Amazon Athena** | ~50 a 100 GB de consultas analíticas escaneadas al mes | $0.50 |
| **Amazon CloudWatch** | Métricas operativas, retención de logs por 30 días y alarmas | $3.50 |
| **AWS EventBridge / Secrets Manager**| Disparadores automáticos y almacenamiento seguro de credenciales | $1.00 |
| **Base Analítica Ligera (Opcional)** | Amazon RDS PostgreSQL (db.t4g.micro, Single-AZ) si BI requiere JDBC constante | $18.50 - $29.00 |
| **Margen de Crecimiento (Buffer)** | Imprevistos o incremento de volumen | $20.00 |
| **Total Mensual Estimado** | **Arquitectura Serverless Completa** | **$44.85 – $55.35 USD / mes** |

*Ahorro frente al presupuesto límite:* **> 72% de margen libre mensual**.

---

## 4. Plan de Implementación por Fases

[Semana 1-2] FASE 1: Ingesta & Data Lakehouse

Configuración de buckets S3 y políticas IAM.

Automatización de ingesta desde POS, Shopify y ERP.

Conciliación cambiaria a MXN.

[Semana 3-4] FASE 2: Modelo Analítico & Pruebas

Pipeline de transformación en Lambda/DuckDB (vistas Gold).

SCD Tipo 2 de costos unitarios y control de márgenes negativos.

Implementación de tests automáticos de consistencia.

[Semana 5-6] FASE 3: Explotación Analítica & Entrega

Vistas optimizadas en Athena para consumo de BI.

Tablero de control de quiebres de stock y rotación de inventarios.

Documentación de handover y capacitación técnica al equipo de TI.

### Matriz de Riesgos y Mitigación
* **Riesgo 1: Caída o retraso en la carga de inventario del ERP legacy.**  
  *Mitigación:* Implementación de alertas SNS en CloudWatch; si a las 04:00 AM no se detecta el archivo diario, se dispara una notificación de contingencia y el pipeline procesa con el snapshot previo marcando bandera de auditoría.
* **Riesgo 2: Datos atípicos o cadenas inválidas (`'N/A'`) en stocks.**  
  *Mitigación:* Reglas de validación en la capa Bronze (`TRY_CAST` con alertas automáticas de anomalías hacia TI).

---

## 5. Preguntas Abiertas para el Cliente antes del Despliegue

1. **Latencia de Negocio**: ¿Requiere la Dirección reportes diarios cerrados al corte de medianoche (T+1), o existen casos de uso que justifiquen ingesta intradía/micro-batch cada hora?
2. **Mapeo Maestro de Catálogo**: Detectamos 65 SKUs mapeados formalmente en `sku_mappings` frente a 70 productos en el catálogo maestro. ¿Cuál es el proceso formal de alta de nuevos productos para sincronizar POS, Shopify y ERP?
3. **Márgenes Negativos Detectados**: El análisis inicial reveló pérdidas sistemáticas en el SKU `ERP-PROV-MX-015-D` (Especial Café Molido) en múltiples sucursales físicas. ¿Obedece a una campaña comercial deliberada de descuento o a un desalineamiento de costos con proveedores?

