from src.pipeline import run_pipeline
from src.queries import run_all_queries

if __name__ == "__main__":
    print("Iniciando ejecución completa para CaféNorte...\n")
    run_pipeline()
    run_all_queries()
    print("\nEjecución finalizada con éxito.")