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

# Вывод всех параметров в формате ключ-значение
print("Настраиваемые параметры:")
try:
    package_name = config.get("title", "Не указано")
    url = config.get("url", "Не указан")
    test_mode = config.get("test", False)
    version = config.get("version", "Не указана")
    ascii_tree = config.get("ascii", False)
    
    print(f"Имя пакета: {package_name}")
    print(f"URL репозитория: {url}")
    print(f"Тестовый режим: {test_mode}")
    print(f"Версия пакета: {version}")
    print(f"Режим ASCII-дерева: {ascii_tree}")
    
except KeyError as e:
    print(f"Ошибка: Отсутствует обязательный параметр в конфигурации: {e}")
    sys.exit(1)

# Обработка URL и загрузка данных
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
            if member.name.endswith('APKINDEX'):
                apkindex_member = member
                break
        
        if apkindex_member is None:
            print("Ошибка: Файл APKINDEX не найден в архиве")
            sys.exit(1)
            
        content = tar.extractfile(apkindex_member)
        if content:
            print("\nСодержимое APKINDEX:")
            print(content.read().decode('utf-8', errors='ignore'))
        else:
            print("Ошибка: Не удалось извлечь файл APKINDEX")
            
except tarfile.TarError as e:
    print(f"Ошибка при работе с tar-архивом: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Неожиданная ошибка: {e}")
    sys.exit(1)

# Демонстрация режимов (заглушки для дальнейшей реализации)
if test_mode:
    print("\nРежим тестового репозитория активирован")

if ascii_tree:
    print("\nРежим вывода в формате ASCII-дерева активирован")
    # Здесь будет реализация построения дерева зависимостей
