"""Конфигурация приложения."""
from pathlib import Path

# Версия приложения
APP_VERSION = "1.1.2"

# Пути
APP_DIR = Path.home() / ".secure_vault"
VAULT_FILE = APP_DIR / "vault.enc"

# Криптография
SALT_SIZE = 16
ARGON2_TIME_COST = 3
ARGON2_MEM_COST = 65536 # 64MB
ARGON2_PARALLELISM = 4
KEY_LENGTH = 32

# GUI
APP_TITLE = "SecureVault"
APP_SIZE = "1400x650"
CLIPBOARD_CLEAR_SECONDS = 20
PASSWORD_GEN_LENGTH = 20

# Создать директорию при импорте
APP_DIR.mkdir(parents=True, exist_ok=True)

# Бездействие до блокировки
IDLE_TIMEOUT_SECONDS = 300

#Время автосокрытия пароля
PASSWORD_AUTOHIDE_SECONDS = 10

# Защита от брутфорса
BRUTEFORCE_BASE_DELAY = 1.0
BRUTEFORCE_MAX_DELAY = 30.0