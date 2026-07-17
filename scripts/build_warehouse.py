import logging
from backend.warehouse.warehouse import WarehouseBuilder

logging.basicConfig(level=logging.INFO)

def main():
    builder = DuckDBWarehouseBuilder()
    builder.build_warehouse()
    print("Warehouse build complete.")

if __name__ == "__main__":
    main()
