import pytest
import duckdb
import os

DB_PATH = "cafenorte_analytics.duckdb"

@pytest.fixture(scope="session")
def db_connection():
    if not os.path.exists(DB_PATH):
        from src.pipeline import run_pipeline
        run_pipeline()
    con = duckdb.connect(DB_PATH, read_only=True)
    yield con
    con.close()

def test_ventas_unificadas_no_vacias(db_connection):
    count = db_connection.execute("SELECT count(*) FROM fct_ventas_unificadas;").fetchone()[0]
    assert count > 0, "fct_ventas_unificadas no debe estar vacia"

def test_inventario_stock_no_negativo(db_connection):
    negative_stock = db_connection.execute(
        "SELECT count(*) FROM fct_inventario_diario WHERE cantidad_en_stock < 0;"
    ).fetchone()[0]
    assert negative_stock == 0, "No debe haber inventario con valores negativos"

def test_ventas_monto_mxn_valido(db_connection):
    null_or_zero_revenue = db_connection.execute(
        "SELECT count(*) FROM fct_ventas_unificadas WHERE monto_neto_mxn IS NULL OR monto_neto_mxn <= 0;"
    ).fetchone()[0]
    assert null_or_zero_revenue == 0, "Todas las ventas deben tener monto positivo en MXN"

def test_canales_validos(db_connection):
    canales = db_connection.execute(
        "SELECT DISTINCT canal FROM fct_ventas_unificadas ORDER BY canal;"
    ).fetchall()
    canales_list = [c[0] for c in canales]
    assert set(canales_list) == {"Fisico", "E-commerce"}, "Los canales deben ser Fisico y E-commerce"
