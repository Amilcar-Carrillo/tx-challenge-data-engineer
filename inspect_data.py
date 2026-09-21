import json

with open('data/inventory.json', 'r', encoding='utf-8') as f:
    inv = json.load(f)

prods = inv['catalogo']['productos']
print(f"Total productos en catálogo: {len(prods)}")
print("Ejemplo primer producto:")
print(json.dumps(prods[0], indent=2))