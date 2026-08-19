"""Бизнес-логика менеджера паролей."""
import io
import csv
import string
import secrets
from typing import Optional

from storage import load_vault, save_vault


class VaultService:
    def __init__(self, master_password: str):
        self._password = master_password
        self._data: dict = {}
        self.reload()

    def reload(self) -> None:
        self._data = load_vault(self._password)

    def _save(self) -> None:
        save_vault(self._data, self._password)

    def list_entries(self) -> list[str]:
        return sorted(self._data.keys())

    def get_entry(self, name: str) -> Optional[dict]:
        return self._data.get(name)

    def add_entry(self, name: str, login: str, password: str, note: str = "", category: str = "") -> None:
        if not name:
            raise ValueError("Имя записи не может быть пустым")
        self._data[name] = {
            "login": login,
            "password": password,
            "note": note,
            "category": category
        }
        self._save()

    def delete_entry(self, name: str) -> None:
        if name in self._data:
            del self._data[name]
            self._save()

    def search(self, query: str) -> list[str]:        
        q = query.lower()
        return [n for n in self._data if q in n.lower()]

    def export_csv(self) -> str:
        """Экспорт записей в CSV (для импорта в KeePass/Bitwarden)."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "login", "password", "note", "category"])
        for name in sorted(self._data.keys()):
            entry = self._data[name]
            writer.writerow([
                name,
                entry["login"],
                entry["password"],
                entry.get("note", ""),
                entry.get("category", "")
            ])
        return output.getvalue()

    def export_json(self) -> str:
        """Экспорт записей в JSON (для резервного копирования)."""
        import json
        return json.dumps(self._data, ensure_ascii=False, indent=2)
    
    def import_csv(self, csv_content: str) -> int:
        """Импорт записей из CSV. Возвращает количество добавленных записей."""
        reader = csv.DictReader(io.StringIO(csv_content))
        count = 0
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            self._data[name] = {
                "login": row.get("login", ""),
                "password": row.get("password", ""),
                "note": row.get("note", ""),
                "category": row.get("category", "")
            }
            count += 1

        if count > 0:
            self._save()

        return count

    def import_json(self, json_content: str) -> int:
        """Импорт записей из JSON. Возвращает количество добавленных записей."""
        import json
        data = json.loads(json_content)
        count = 0
        for name, entry in data.items():
            if not name or not isinstance(entry, dict):
                continue
            self._data[name] = {
                "login": entry.get("login", ""),
                "password": entry.get("password", ""),
                "note": entry.get("note", ""),
                "category": entry.get("category", "")
            }
            count += 1
        if count > 0:
            self._save()
        return count

    def change_master_password(self, old_password: str, new_password: str) -> None:
        """Меняет мастер-пароль и перешиврует хранилище."""
        if old_password != self._password:
            raise ValueError("Неверный текущий пароль")
        if not new_password:
            raise ValueError("Новый пароль не может быть пустым")
        if len(new_password) < 8:
            raise ValueError("Новый пароль должен быть не менее 8 символов")
        self._password = new_password
        self._save()

    @staticmethod
    def generate_password(length: int = 20) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def audit(self) -> dict:
        """Аудит: слабые и повторяющиеся пароли."""
        weak = []
        dup: dict[str, list[str]] = {}
        for name, entry in self._data.items():
            pwd = entry.get("password", "")
            if len(pwd) < 12:
                weak.append(name)
            dup.setdefault(pwd, []).append(name)
        duplicates = {k: v for k, v in dup.items() if len(v) > 1}
        return {"weak": weak, "duplicates": duplicates}

    def verify_master_password(self, password: str) -> bool:
        """Проверяет мастер-пароль без его раскрытия."""
        return password == self._password

    def update_entry(self, name: str, login: str, password: str, note: str = "", category: str = "") -> None:
        """Обновляет существующую запись"""
        if name not in self._data:
            raise ValueError(f"Запись '{name}' не найдена")
        self._data[name] = {
            "login": login,
            "password": password,
            "note": note,
            "category": category
        }
        self._save()

    def get_categories(self) -> list[str]:
        """Возвращает список всех уникальных категорий."""
        categories = set()
        for entry in self._data.values():
            cat = entry.get("category", "")
            if cat:
                categories.add(cat)
        return sorted(categories)

    def search_by_category(self, category: str) -> list[str]:
        """Возвращает имена записей по категории."""
        return [name for name, entry in self._data.items()
                if entry.get("category", "") == category]

    def get_category_counts(self) -> dict[str, int]:
        """Возвращает количество записей по каждой категории."""
        counts: dict[str, int] = {}
        for entry in self._data.values():
            cat = entry.get("category", "")
            if cat:
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_categories_with_counts(self) -> list[str]:
        """Возвращает список категорий с количеством записей."""
        counts = self.get_category_counts()
        result = []
        for cat in sorted(counts.keys()):
            result.append(f"{cat} ({counts[cat]})")
        return result

    def clear_password(self) -> None:
        """Очищает мастер-пароль из памяти (вызывать при выходе)"""
        self._password = ""
        self._data = {}