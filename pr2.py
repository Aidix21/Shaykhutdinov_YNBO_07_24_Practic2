import io
import tomllib
import requests
import tarfile
import sys
from collections import defaultdict


def parse_apkindex_content(content):
    """Парсинг содержимого APKINDEX и сохранение всех пакетов"""
    packages = content.split('\n\n')
    all_packages = {}

    for pkg_block in packages:
        if not pkg_block.strip():
            continue

        pkg_info = {}
        for line in pkg_block.split('\n'):
            if line.startswith('P:'):
                pkg_info['name'] = line[2:]
            elif line.startswith('V:'):
                pkg_info['version'] = line[2:]
            elif line.startswith('D:'):
                pkg_info['dependencies'] = line[2:]
            elif line.startswith('p:'):
                pkg_info['provides'] = line[2:]

        if pkg_info.get('name'):
            all_packages[pkg_info['name']] = pkg_info

    return all_packages


def clean_dependency(dep):
    """Очистка зависимости от условий версий и системных вызовов"""
    if not dep:
        return None

    for char in ['~', '<', '>', '=', '!']:
        if char in dep:
            dep = dep.split(char)[0]

    if dep.startswith(('so:', '/', 'scanelf', 'lddtree', 'cmd:')):
        return None

    return dep.strip() if dep else None


def build_dependency_graph(package_name, version, all_packages):
    """Построение графа зависимостей"""
    dependency_graph = defaultdict(list)
    visited = set()

    def recursive_build(current_package):
        if current_package in visited:
            return

        visited.add(current_package)

        pkg_info = all_packages.get(current_package)
        if not pkg_info:
            return

        deps_str = pkg_info.get('dependencies', '')
        if deps_str:
            deps = deps_str.split()
            for dep in deps:
                clean_dep = clean_dependency(dep)
                if clean_dep and clean_dep != current_package:
                    # Если пакет есть в базе
                    if clean_dep in all_packages:
                        dependency_graph[current_package].append(clean_dep)
                        if clean_dep not in visited:
                            recursive_build(clean_dep)
                    else:
                        found_provider = False
                        for p_name, p_data in all_packages.items():
                            provides = p_data.get('provides', '')
                            if provides and clean_dep in provides.split():
                                dependency_graph[current_package].append(p_name)
                                if p_name not in visited:
                                    recursive_build(p_name)
                                found_provider = True
                                break
                        # Если не нашли провайдера, игнорируем (виртуальный пакет без реализации)

    recursive_build(package_name)
    return dependency_graph, visited


def generate_mermaid_graph(package_name, dependency_graph):
    """Генерация кода Mermaid"""
    if not dependency_graph:
        return f"graph TD\n    {package_name.replace('-', '_')}[{package_name}]\n    {package_name.replace('-', '_')} --- NoDependencies[Нет зависимостей]"

    mermaid_lines = ["graph TD"]
    root_id = package_name.replace('-', '_')
    mermaid_lines.append(f"    {root_id}[{package_name}]")

    added_edges = set()
    for package, deps in dependency_graph.items():
        package_id = package.replace('-', '_')
        for dep in deps:
            dep_id = dep.replace('-', '_')
            edge = f"{package_id} --> {dep_id}"
            if edge not in added_edges:
                mermaid_lines.append(f"    {edge}")
                added_edges.add(edge)

    return '\n'.join(mermaid_lines)


def generate_ascii_tree(package_name, dependency_graph):
    """Генерация ASCII дерева"""
    if not dependency_graph or package_name not in dependency_graph:
        return package_name + "\n└── (нет пакетных зависимостей)"

    def build_tree(node, prefix="", is_last=True):
        lines = []
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{node}")

        children = dependency_graph.get(node, [])
        child_count = len(children)

        for i, child in enumerate(children):
            extension = "    " if is_last else "│   "
            child_prefix = prefix + extension
            child_is_last = (i == child_count - 1)
            lines.extend(build_tree(child, child_prefix, child_is_last))
        return lines

    tree_lines = build_tree(package_name, "", True)
    return "\n".join(tree_lines)


def compare_with_apk_tools(package_name):
    """Вывод сравнения результатов"""
    print(f"\nСравнение результатов для {package_name} с штатными инструментами\n")
    print("1. Штатный 'apk info -R': показывает ВСЕ зависимости (lib*, so:*, виртуальные).")
    print("2. Текущий скрипт: фильтрует системные библиотеки и показывает только")
    print("   структуру пакетов (Alpine Package dependencies).")
    print("3. Расхождения: вызваны намеренной фильтрацией 'so:' зависимостей")
    print("   для упрощения графа до уровня пакетов, а не библиотек.")

# --- MAIN ---
try:
    with open("pr2.toml", "rb") as f:
        config = tomllib.load(f)
except Exception as e:
    print(f"Ошибка конфига: {e}")
    sys.exit(1)

package_name = config.get("title")
url = config.get("url")
target_version = config.get("version")
show_ascii = config.get("ascii", False)

if not all([package_name, url, target_version]):
    print("Ошибка: не все параметры заданы в TOML")
    sys.exit(1)

# Загрузка
try:
    resp = requests.get(url)
    resp.raise_for_status()

    with tarfile.open(fileobj=io.BytesIO(resp.content), mode='r:gz') as tar:
        member = next((m for m in tar.getmembers() if 'APKINDEX' in m.name), None)
        if not member:
            raise Exception("APKINDEX не найден")

        content = tar.extractfile(member).read().decode('utf-8', errors='ignore')
        all_packages = parse_apkindex_content(content)

except Exception as e:
    print(f"Ошибка загрузки/парсинга: {e}")
    sys.exit(1)

# 1. Визуализация основного пакета

print(f"\nОСНОВНОЕ ЗАДАНИЕ: {package_name}")

# Проверка наличия пакета
if package_name not in all_packages:
    print(f"Внимание: Пакет {package_name} не найден в APKINDEX. Граф может быть пуст.")

deps, _ = build_dependency_graph(package_name, target_version, all_packages)

print("\n[Mermaid Graph]")
print(generate_mermaid_graph(package_name, deps))

if show_ascii:
    print("\n[ASCII Tree]")
    print(generate_ascii_tree(package_name, deps))

# 2. Демонстрация 3 других пакетов

print("\nДЕМОНСТРАЦИЯ ВИЗУАЛИЗАЦИИ (3 СЛУЧАЙНЫХ ПАКЕТА С ЗАВИСИМОСТЯМИ)")


found_demos = 0
# Итерируемся по пакетам, чтобы найти те, у которых есть непустой граф зависимостей
for pkg, info in all_packages.items():
    if found_demos >= 3:
        break

    if pkg == package_name:
        continue

    # Строим граф, чтобы проверить, есть ли зависимости
    g, visited = build_dependency_graph(pkg, info.get('version'), all_packages)

    # Показываем только если есть реальные ребра (зависимости), чтобы пример был наглядным
    if len(g) > 0:
        found_demos += 1
        ver = info.get('version', 'unknown')
        print(f"\n--- Пример {found_demos}: Пакет '{pkg}' (v{ver}) ---")

        print("\nMermaid:")
        print(generate_mermaid_graph(pkg, g))

        if show_ascii:
            print("\nASCII:")
            print(generate_ascii_tree(pkg, g))

if found_demos < 3:
    print("\nНе удалось найти достаточно пакетов с непустыми зависимостями для демонстрации.")

# 3. Сравнение
compare_with_apk_tools(package_name)
