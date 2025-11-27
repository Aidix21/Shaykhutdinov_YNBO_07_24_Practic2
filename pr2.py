import io
import tomllib
import requests
import tarfile
import sys

try:
    with open("pr2.toml", "rb") as f:
        config = tomllib.load(f)
except FileNotFoundError:
    print("Ошибка: Конфигурационный файл pr2.toml не найден")
    sys.exit(1)
except tomllib.TOMLDecodeError as e:
    print(f"Ошибка: Неверный формат TOML файла: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Ошибка при чтении конфигурационного файла: {e}")
    sys.exit(1)

# Получение параметров из конфигурации
try:
    package_name = config.get("title")
    url = config.get("url")
    version = config.get("version")
    
    if not package_name or not url or not version:
        raise KeyError("Отсутствуют обязательные параметры")
        
except KeyError as e:
    print(f"Ошибка: {e}")
    sys.exit(1)

# Загрузка и обработка APKINDEX
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Ошибка при загрузке данных из {url}: {e}")
    sys.exit(1)

try:
    tar_gz_bytes = response.content
    tar_gz_file = io.BytesIO(tar_gz_bytes)
    
    with tarfile.open(fileobj=tar_gz_file, mode='r:gz') as tar:
        # Поиск файла APKINDEX в архиве
        apkindex_member = None
        for member in tar.getmembers():
            if 'APKINDEX' in member.name:
                apkindex_member = member
                break
        
        if apkindex_member is None:
            print("Ошибка: Файл APKINDEX не найден в архиве")
            sys.exit(1)
            
        content = tar.extractfile(apkindex_member)
        if content:
            apkindex_content = content.read().decode('utf-8', errors='ignore')
            
            # Парсинг APKINDEX для поиска заданного пакета и его зависимостей
            packages = apkindex_content.split('\n\n')
            target_package = None
            
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
                
                if pkg_info.get('name') == package_name and pkg_info.get('version') == version:
                    target_package = pkg_info
                    break
            
            if target_package:
                print(f"Прямые зависимости пакета {package_name} версии {version}:")
                if target_package.get('dependencies'):
                    deps = target_package['dependencies'].split()
                    for dep in deps:
                        # Убираем условия версий (все что после ~, <, >, = и т.д.)
                        clean_dep = dep.split('~')[0].split('<')[0].split('>')[0].split('=')[0]
                        if clean_dep:
                            print(f"  - {clean_dep}")
                else:
                    print("  Зависимости отсутствуют")
            else:
                print(f"Пакет {package_name} версии {version} не найден в репозитории")
                
        else:
            print("Ошибка: Не удалось извлечь файл APKINDEX")
            
except tarfile.TarError as e:
    print(f"Ошибка при работе с tar-архивом: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Неожиданная ошибка: {e}")
    sys.exit(1)
