import ast
import os
import sys


def get_imports(directory):
    imports = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                try:
                    with open(os.path.join(root, file), encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for name in node.names:
                                    imports.add(name.name.split('.')[0])
                            elif isinstance(node, ast.ImportFrom):
                                if node.module and node.level == 0:
                                    imports.add(node.module.split('.')[0])
                except Exception:
                    pass
    return imports

stdlib = sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set()
local = {'backend', 'frontend', 'shared', 'tests', 'data', 'docs', 'scripts', 'sql', 'conftest'}

all_imports = get_imports('.')
external = [m for m in all_imports if m not in stdlib and m not in local]

print("External Modules Found:")
for m in sorted(external):
    print(m)
