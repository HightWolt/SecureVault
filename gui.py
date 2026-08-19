"""Графический интерфейс на customtkinter."""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from config import (
    APP_TITLE, APP_SIZE, APP_VERSION, CLIPBOARD_CLEAR_SECONDS, 
    PASSWORD_GEN_LENGTH, IDLE_TIMEOUT_SECONDS, PASSWORD_AUTOHIDE_SECONDS,
    BRUTEFORCE_BASE_DELAY, BRUTEFORCE_MAX_DELAY
)
from clipboard import copy_secure
from vault import VaultService


class LockScreen(ctk.CTkToplevel):
    """Экран блокировки - требует ввод мастер-пароля"""

    def __init__(self, parent, service: VaultService, on_unlock):
        super().__init__(parent)
        self.title("Заблокировано")
        self.geometry("400x250")
        self.resizable(False, False)
        self.grab_set()
        self.attributes('-topmost', True)

        self._service = service
        self._on_unlock = on_unlock
        self._failed_attempts = 0

        ctk.CTkLabel(self, text="🔒 Заблокировано",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(30, 10))

        ctk.CTkLabel(self, text="Введите мастер-пароль для разблокировки").pack(pady=5)

        self.pwd_entry = ctk.CTkEntry(self, show="•", width=280, height=40)
        self.pwd_entry.pack(pady=5)
        self.pwd_entry.bind("<Return>", lambda e: self._check())

        self.btn = ctk.CTkButton(self, text="Разблокировать", width=280, height=40,
                                 command=self._check)
        self.btn.pack(pady=10)

        self.status = ctk.CTkLabel(self, text="", text_color="red")
        self.status.pack()

        self.pwd_entry.focus()

    def _check(self):
        pwd = self.pwd_entry.get()
        if self._service.verify_master_password(pwd):
            self._failed_attempts = 0
            self._on_unlock()
            self.destroy()
        else:
            self._failed_attempts += 1
            delay = self._get_bruteforce_delay()
            self.status.configure(text=f"Неверный пароль (задержка {delay:.0f}с)")
            self._lock_input(delay)

    def _get_bruteforce_delay(self) -> float:
        """Экспоненциальная задержка: 1с, 2с, 4с, 8с... до максимума."""
        delay = BRUTEFORCE_BASE_DELAY * (2 ** (self._failed_attempts - 1))
        return min(delay, BRUTEFORCE_MAX_DELAY)

    def _lock_input(self, delay: float):
        """Блокирует поле ввода и кнопку на время задержки."""
        self.pwd_entry.configure(state="disabled")
        self.btn.configure(state="disabled")

        def _unlock():
            if self.winfo_exists():
                try:
                    self.pwd_entry.configure(state="normal")
                    self.btn.configure(state="normal")
                    self.pwd_entry.focus()
                    self.pwd_entry.delete(0, "end")
                except tk.TclError:
                    pass

        self.after(int(delay * 1000), _unlock)



class LoginWindow(ctk.CTk):
    """Окно ввода мастер-пароля."""

    def __init__(self, vault_exists: bool, on_submit):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION} - Вход")
        self.geometry("400x250")
        self.resizable(False, False)
        self._on_submit = on_submit
        self._vault_exists = vault_exists
        self.master_password: str | None = None
        self._failed_attempts = 0

        ctk.CTkLabel(self, text="🔐 Мастер-пароль",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(30, 10))

        self.pwd_entry = ctk.CTkEntry(self, show="•", width=280, height=40)
        self.pwd_entry.pack(pady=5)
        self.pwd_entry.bind("<Return>", lambda e: self._submit())

        self.btn = ctk.CTkButton(
            self, 
            text="Войти" if vault_exists else "Создать хранилище",
            width=280, height=40, 
            command=self._submit
        )
        self.btn.pack(pady=10)

        self.status = ctk.CTkLabel(self, text="", text_color="red")
        self.status.pack()

        self.pwd_entry.focus()

    def _submit(self):
        pwd = self.pwd_entry.get()
        if not pwd:
            self.status.configure(text="Введите пароль")
            return
        try:
            self._on_submit(pwd)
            self.master_password = pwd
            self._failed_attempts = 0
            self.withdraw()
            self.after(100, self.quit)
        except Exception as e:
            self._failed_attempts += 1
            delay = self._get_bruteforce_delay()
            if self.winfo_exists():
                try:
                    self.status.configure(text=f"{str(e)} (задержка {delay:.0f}с)")
                except tk.TclError:
                    pass
            self._lock_input(delay)

    def _get_bruteforce_delay(self) -> float:
        """Экспоненциальная задержка: 1с, 2с, 4с, 8с... до максимума."""
        delay = BRUTEFORCE_BASE_DELAY * (2 ** (self._failed_attempts - 1))
        return min(delay, BRUTEFORCE_MAX_DELAY)

    def _lock_input(self, delay: float):
        """Блокирует поле ввода и кнопку на время задержки."""
        self.pwd_entry.configure(state="disabled")
        self.btn.configure(state="disabled")

        def _unlock():
            if self.winfo_exists():
                try:
                    self.pwd_entry.configure(state="normal")
                    self.btn.configure(state="normal")
                    self.pwd_entry.focus()
                    self.pwd_entry.delete(0, "end")
                except tk.TclError:
                    pass

        self.after(int(delay * 1000), _unlock)


class MainApp(ctk.CTk):
    """Главное окно приложения."""

    def __init__(self, service: VaultService):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry(APP_SIZE)
        self.svc = service
        self.current_name: str | None = None
        self._pwd_visible: bool = False
        self._idle_timer: str | None = None
        self._autohide_timer: str | None = None
        self._category_filter: str = ""

        self._build_ui()
        self._refresh_list()
        self._start_idle_timer()
        self._bind_hotkeys()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Обработчик закрытия окна с подтверждением."""
        if messagebox.askyesno("Выход", "Закрыть SecureVault?"):
            if self._idle_timer:
                self.after_cancel(self._idle_timer)
            if self._autohide_timer:
                self.after_cancel(self._autohide_timer)

            self.unbind_all("<Key>")
            self.unbind_all("<Button>")
            self.unbind_all("<Control-Key>")
            self.unbind_all("<Escape>")

            self.destroy()

    # ---- Горячие клавиши ----

    def _bind_hotkeys(self):
        """Привязывает горячие клавиши."""
        self.bind_all("<Control-Key>", self._on_hotkey)
        self.bind_all("<Escape>", lambda e: self._hide_password_if_visible())

    def _on_hotkey(self, event):
        """Обработчик горячих клавиш с поддержкой разных раскладок"""
        RU_TO_EN = {'т': 'n', 'а': 'f', 'д': 'l', 'п': 'g', 'у': 'e', 'ш': 'i'}
        KEYCODE_MAP = {78: 'n', 70: 'f', 76: 'l', 71: 'g', 69: 'e', 73: 'i'}

        resolved_key: str

        key_from_code = KEYCODE_MAP.get(event.keycode)
        if key_from_code is not None:
            resolved_key = key_from_code
        else:
            keysym_raw = event.keysym
            if keysym_raw is None:
                return
            keysym = keysym_raw.lower()
            if keysym in RU_TO_EN:
                resolved_key = RU_TO_EN[keysym]
            else:
                resolved_key = keysym

        actions = {
            'n': self._add_dialog,
            'f': lambda: self.search.focus_set(),
            'l': self._lock,
            'g': self._gen_dialog,
            'e': self._export_dialog,
            'i': self._import_dialog,
        }

        action = actions.get(resolved_key)
        if action:
            action()

    def _hide_password_if_visible(self):
        """Скрывает пароль, если он показан (Escape)."""
        if self._pwd_visible:
            self._pwd_visible = False
            self.d_pwd.configure(text="Пароль: ••••••••")
            self.btn_show.configure(text="👁 Показать пароль")
            if self._autohide_timer:
                self.after_cancel(self._autohide_timer)

    # ---- Автоблокировка ----

    def _start_idle_timer(self):
        """Запускает таймер неактивности"""
        self._reset_idle_timer()
        self.bind_all("<Key>", self._on_user_activity)
        self.bind_all("<Button>", self._on_user_activity)

    def _on_user_activity(self, event=None):
        """Сбрасывает таймер при активности пользователя."""
        self._reset_idle_timer()

    def _reset_idle_timer(self):
        """Сбрасывает таймер неактивности."""
        if self._idle_timer:
            self.after_cancel(self._idle_timer)
        self._idle_timer = self.after(IDLE_TIMEOUT_SECONDS * 1000, self._lock)

    def _lock(self):
        """Блокирует приложение."""
        if not self.winfo_exists():
            return
        LockScreen(self, self.svc, self._unlock)

    def _unlock(self):
        """Разблокирует приложение"""
        self._reset_idle_timer()
        self.focus_force()

    # ---- Автосокрытие пароля ----
    def _schedule_autohide(self):
        """Запускает таймер автосокрытия пароля"""
        if self._autohide_timer:
            self.after_cancel(self._autohide_timer)
        self._autohide_timer = self.after(
            PASSWORD_AUTOHIDE_SECONDS * 1000, 
            self._autohide_password
        )

    def _autohide_password(self):
        """Автоматически скрывает пароль."""
        if self._pwd_visible and self.current_name:
            self._pwd_visible = False
            self.d_pwd.configure(text="Пароль: ••••••••")
            self.btn_show.configure(text="👁 Показать пароль")
            self._flash_status(f"🙈 Пароль скрыт автоматически (через {PASSWORD_AUTOHIDE_SECONDS}с)")

    # ---- Построение интерфейса ----

    def _build_ui(self):
        # Верхняя панель: поиск + действия
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)

        self.search = ctk.CTkEntry(top, placeholder_text="🔍 Поиск...", width=300)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda e: self._refresh_list())

        self.category_filter = ctk.CTkComboBox(
            top,
            values=["Все категории"] + self.svc.get_categories_with_counts(),
            width=180,
            command=self._on_category_filter_change
        )
        self.category_filter.set("Все категории")
        self.category_filter.pack(side="left", padx=5)

        ctk.CTkButton(top, text="➕ Добавить (Ctrl+N)", width=150, command=self._add_dialog).pack(side="left", padx=5)
        ctk.CTkButton(top, text="🎲 Генератор (Ctrl+G)", width=155, command=self._gen_dialog).pack(side="left", padx=5)
        ctk.CTkButton(top, text="📊 Аудит", width=100, command=self._audit).pack(side="left", padx=5)
        ctk.CTkButton(top, text="📤 Экспорт (Ctrl+E)", width=130, command=self._export_dialog).pack(side="left", padx=5)
        ctk.CTkButton(top, text="📥 Импорт (Ctrl+I)", width=130, command=self._import_dialog).pack(side="left", padx=5)
        ctk.CTkButton(top, text="🔑 Сменить пароль", width=130, command=self._change_password_dialog).pack(side="left", padx=5)

        # Основная область: список слева, детали справа
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Список
        self.listbox = ctk.CTkScrollableFrame(body, width=280)
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Детали
        self.details = ctk.CTkFrame(body)
        self.details.grid(row=0, column=1, sticky="nsew")
        self._build_details()

        # Статус-бар
        self.statusbar = ctk.CTkLabel(self, text="Записей: 0", anchor="w")
        self.statusbar.pack(side="left", fill="x", expand=True, padx=10, pady=(0, 10))

        version_label = ctk.CTkLabel(self, text=APP_VERSION, text_color="gray")
        version_label.pack(side="right", padx=10, pady=(0, 10))

    def _build_details(self):
        for w in self.details.winfo_children():
            w.destroy()
        
        self.current_name = None
        
        self.d_title = ctk.CTkLabel(self.details, text="Выберите запись слева",
                                    font=ctk.CTkFont(size=20, weight="bold"))
        self.d_title.pack(pady=20)

        self.d_category = ctk.CTkLabel(self.details, text="")
        self.d_category.pack(pady=5)

        self.d_login = ctk.CTkLabel(self.details, text="")
        self.d_login.pack(pady=5)

        self.d_pwd = ctk.CTkLabel(self.details, text="")
        self.d_pwd.pack(pady=5)

        self.d_note = ctk.CTkLabel(self.details, text="")
        self.d_note.pack(pady=5)

        btns = ctk.CTkFrame(self.details, fg_color="transparent")
        btns.pack(pady=20)

        self.btn_show = ctk.CTkButton(btns, text="👁 Показать пароль", command=self._show_pwd)
        self.btn_show.pack(side="left", padx=5)
        self.btn_copy_login = ctk.CTkButton(btns, text="📋 Копировать логин", command=self._copy_login)
        self.btn_copy_login.pack(side="left", padx=5)
        self.btn_copy_pwd = ctk.CTkButton(btns, text="🔑 Копировать пароль", command=self._copy_pwd)
        self.btn_copy_pwd.pack(side="left", padx=5)
        self.btn_edit = ctk.CTkButton(btns, text="✏ Редактировать",
                                      fg_color="orange", hover_color="darkorange",
                                      command=self._edit_dialog)
        self.btn_edit.pack(side="left", padx=5)
        self.btn_del = ctk.CTkButton(btns, text="🗑 Удалить", fg_color="red", 
                                    hover_color="darkred", command=self._delete)
        self.btn_del.pack(side="left", padx=5)

        self._set_buttons_state(False)

    def _set_buttons_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in (self.btn_show, self.btn_copy_login, self.btn_copy_pwd, self.btn_edit, self.btn_del):
            b.configure(state=state)

    # ---- Обновление списка ----

    def _refresh_list(self):
        for w in self.listbox.winfo_children():
            w.destroy()

        query = self.search.get()

        if self._category_filter:
            names = self.svc.search_by_category(self._category_filter)
        else:
            names = self.svc.list_entries()

        if query:
            q = query.lower()
            names = [n for n in names if q in n.lower()]

        for name in names:
            btn = ctk.CTkButton(self.listbox, text=name, anchor="w",
                                command=lambda n=name: self._select(n))
            btn.pack(fill="x", pady=2)

        self.statusbar.configure(text=f"Записей: {len(self.svc.list_entries())} | Показано: {len(names)}")

    def _select(self, name: str):
        self.current_name = name
        entry = self.svc.get_entry(name)
        if not entry:
            return

        self.d_title.configure(text=f"📁 {name}")
        category = entry.get("category", "")
        self.d_category.configure(text=f"Категория: {category or '—'}")
        self.d_login.configure(text=f"Логин: {entry['login']}")
        self.d_pwd.configure(text="Пароль: ••••••••")
        self.d_note.configure(text=f"Заметка: {entry.get('note') or '—'}")
        self._pwd_visible = False
        self.btn_show.configure(text="👁 Показать пароль")
        self._set_buttons_state(True)

    def _on_category_filter_change(self, selected: str):
        """Обработчик смены фильтра категории."""
        if selected == "Все категории":
            self._category_filter = "" 
        else:
            category = selected.rsplit(" (", 1)[0] if " (" in selected else selected
            self._category_filter = category
        self._refresh_list()

    def _update_category_filter(self):
        """Обновляет список категорий в фильтре."""
        current = self.category_filter.get()
        current_name = current.rsplit(" (", 1)[0] if " (" in current else current

        new_values = ["Все категории"] + self.svc.get_categories_with_counts()
        self.category_filter.configure(values=new_values)

        restored = False
        for val in new_values:
            val_name = val.rsplit(" (", 1)[0] if " (" in val else val
            if val_name == current_name:
                self.category_filter.set(val)
                restored = True
                break
        
        if not restored:
            self.category_filter.set("Все категории")

    # ----Действия ----

    def _show_pwd(self):
        if not self.current_name:
            return
        entry = self.svc.get_entry(self.current_name)
        if not entry:
            return
        self._pwd_visible = not self._pwd_visible
        if self._pwd_visible:
            self.d_pwd.configure(text=f"Пароль: {entry['password']}")
            self.btn_show.configure(text="🙈 Скрыть пароль")
            self._schedule_autohide()
        else:
            self.d_pwd.configure(text="Пароль: ••••••••")
            self.btn_show.configure(text="👁 Показать пароль")
            if self._autohide_timer:
                self.after_cancel(self._autohide_timer)

    def _copy_login(self):
        if not self.current_name:
            return
        entry = self.svc.get_entry(self.current_name)
        if not entry:
            return
        copy_secure(entry["login"], CLIPBOARD_CLEAR_SECONDS)
        self._flash_status(f"✅ Логин скопирован (очистится через {CLIPBOARD_CLEAR_SECONDS}с)")

    def _copy_pwd(self):
        if not self.current_name:
            return
        entry = self.svc.get_entry(self.current_name)
        if not entry:
            return
        copy_secure(entry["password"], CLIPBOARD_CLEAR_SECONDS)
        self._flash_status(f"✅ Пароль скопирован (очистится через {CLIPBOARD_CLEAR_SECONDS}с)")

    def _delete(self):
        if not self.current_name:
            return
        if messagebox.askyesno("Удаление", f"Удалить запись '{self.current_name}'?"):
            self.svc.delete_entry(self.current_name)
            self.current_name = None
            self._build_details()
            self._refresh_list()

    def _flash_status(self, text: str):
        """Показывает сообщение в статус-баре, затем вернуть счётчик."""
        self.statusbar.configure(text=text, text_color="green")

        def _reset():
            # Защита: не трогаем виджет, если окно уже закрыто
            if not self.winfo_exists():
                return
            try:
                self.statusbar.configure(
                    text=f"Записей: {len(self.svc.list_entries())}",
                    text_color=("gray10", "gray90")
                )
            except tk.TclError:
                pass

        self.after(3000, _reset)

    # ----Диалоги ----

    def _add_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Новая запись")
        dlg.geometry("400x400")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Имя (например: github)").pack(pady=(15, 5))
        e_name = ctk.CTkEntry(dlg, width=300)
        e_name.pack()

        ctk.CTkLabel(dlg, text="Категория (необязательно)").pack(pady=(10, 5))
        categories = [""] + self.svc.get_categories()
        e_category = ctk.CTkComboBox(dlg, values=categories, width=300)
        e_category.set("")
        e_category.pack()

        ctk.CTkLabel(dlg, text="Логин").pack(pady=(10, 5))
        e_login = ctk.CTkEntry(dlg, width=300)
        e_login.pack()

        ctk.CTkLabel(dlg, text="Пароль").pack(pady=(10, 5))
        pwd_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        pwd_frame.pack()
        e_pwd = ctk.CTkEntry(pwd_frame, width=220)
        e_pwd.pack(side="left")
        ctk.CTkButton(pwd_frame, text="🎲", width=40,
                      command=lambda: e_pwd.delete(0, "end") or e_pwd.insert(0, self.svc.generate_password())).pack(side="left", padx=5)

        ctk.CTkLabel(dlg, text="Заметка").pack(pady=(10, 5))
        e_note = ctk.CTkEntry(dlg, width=300)
        e_note.pack()

        def save():
            try:
                self.svc.add_entry(
                    e_name.get(), 
                    e_login.get(), 
                    e_pwd.get(), 
                    e_note.get(),
                    e_category.get()
                )
                self._refresh_list()
                self._update_category_filter()
                dlg.destroy()
            except ValueError as e:
                messagebox.showerror("Ошибка", str(e))

        ctk.CTkButton(dlg, text="💾 Сохранить", command=save).pack(pady=15)

    def _gen_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Генератор паролей")
        dlg.geometry("400x200")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Длина пароля").pack(pady=(20, 5))
        length_var = ctk.IntVar(value=PASSWORD_GEN_LENGTH)
        slider = ctk.CTkSlider(dlg, from_=8, to=64, number_of_steps=56, variable=length_var)
        slider.pack(fill="x", padx=30)

        result = ctk.CTkEntry(dlg, width=300, font=ctk.CTkFont(family="monospace"))
        result.pack(pady=15)

        def gen():
            result.delete(0, "end")
            result.insert(0, self.svc.generate_password(length_var.get()))

        ctk.CTkButton(dlg, text="🎲 Сгенерировать пароль", command=gen).pack(side="left", padx=20)
        ctk.CTkButton(dlg, text="📋 Копировать",
                      command=lambda: copy_secure(result.get(), CLIPBOARD_CLEAR_SECONDS)).pack(side="left")

        gen()

    def _edit_dialog(self):
        """Диалог редактирования записей"""
        if not self.current_name:
            return
        entry = self.svc.get_entry(self.current_name)
        if not entry:
            return

        current_name = self.current_name

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Редактирование: {current_name}")
        dlg.geometry("400x400")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text=f"Имя: {current_name}",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        ctk.CTkLabel(dlg, text="Категория (необязательно)").pack(pady=(10, 5))
        categories = [""] + self.svc.get_categories()
        e_category = ctk.CTkComboBox(dlg, values=categories, width=300)
        e_category.set(entry.get("category", ""))
        e_category.pack()

        ctk.CTkLabel(dlg, text="Логин").pack(pady=(10, 5))
        e_login = ctk.CTkEntry(dlg, width=300)
        e_login.insert(0, entry["login"])
        e_login.pack()

        ctk.CTkLabel(dlg, text="Пароль").pack(pady=(10, 5))
        pwd_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        pwd_frame.pack()
        e_pwd = ctk.CTkEntry(pwd_frame, width=220)
        e_pwd.insert(0, entry["password"])
        e_pwd.pack(side="left")
        ctk.CTkButton(pwd_frame, text="🎲", width=40,
                      command=lambda: e_pwd.delete(0, "end") or e_pwd.insert(0, self.svc.generate_password())).pack(side="left", padx=5)

        ctk.CTkLabel(dlg, text="Заметка").pack(pady=(10, 5))
        e_note = ctk.CTkEntry(dlg, width=300)
        e_note.insert(0, entry.get("note", ""))
        e_note.pack()

        def save():
            try:
                self.svc.update_entry(
                    current_name,
                    e_login.get(),
                    e_pwd.get(),
                    e_note.get(),
                    e_category.get()
                )
                self._select(current_name)
                self._update_category_filter()
                dlg.destroy()
            except ValueError as e:
                messagebox.showerror("Ошибка", str(e))

        ctk.CTkButton(dlg, text="💾 Сохранить", command=save).pack(pady=15)

    def _export_dialog(self):
        """Диалог экспорта записей"""
        from tkinter import filedialog

        dlg = ctk.CTkToplevel(self)
        dlg.title("Экспорт записей")
        dlg.geometry("400x200")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Выберите формат экспорта:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 10))

        def export_csv():
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
            )
            if filepath:
                try:
                    csv_data = self.svc.export_csv()
                    with open(filepath, "w", encoding="utf-8", newline="") as f:
                        f.write(csv_data)
                    self._flash_status("✅ Экспортировано в CSV")
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))

        def export_json():
            filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
            )
            if filepath:
                try:
                    json_data = self.svc.export_json()
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(json_data)
                    self._flash_status("✅ Экспортировано в JSON")
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))

        ctk.CTkButton(dlg, text="📄 CSV (для KeePass/Bitwarden)",
                      width=280, command=export_csv).pack(pady=5)
        ctk.CTkButton(dlg, text="📋 JSON (резервная копия)",
                      width=280, command=export_json).pack(pady=5)

        ctk.CTkLabel(dlg, text="⚠️ CSV содержит пароли в открытом виде!",
                     text_color="orange").pack(pady=10)

    def _import_dialog(self):
        """Диалог импорта записей"""
        from tkinter import filedialog

        filepath = filedialog.askopenfilename(
            filetypes=[("CSV файлы", "*.csv"), ("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if filepath.endswith(".csv"):
                count = self.svc.import_csv(content)
            elif filepath.endswith(".json"):
                count = self.svc.import_json(content)
            else:
                messagebox.showerror("Ошибка", "Неподдерживаемый формат файла")
                return

            self._refresh_list()
            self._flash_status(f"✅ Импортировано записей: {count}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _change_password_dialog(self):
        """Диалог смены мастер-пароля."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Смена мастер-пароля")
        dlg.geometry("400x350")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="🔑 Смена мастер-пароля",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 10))

        ctk.CTkLabel(dlg, text="Текущий пароль").pack(pady=(5, 2))
        e_old = ctk.CTkEntry(dlg, show="•", width=300)
        e_old.pack()

        ctk.CTkLabel(dlg, text="Новый пароль").pack(pady=(10, 2))
        e_new = ctk.CTkEntry(dlg, show="•", width=300)
        e_new.pack()

        ctk.CTkLabel(dlg, text="Подтвердите новый пароль").pack(pady=(10, 2))
        e_confirm = ctk.CTkEntry(dlg, show="•", width=300)
        e_confirm.pack()

        status = ctk.CTkLabel(dlg, text="", text_color="red")
        status.pack(pady=5)

        def submit():
            old_pwd = e_old.get()
            new_pwd = e_new.get()
            confirm_pwd = e_confirm.get()

            if new_pwd != confirm_pwd:
                status.configure(text="Пароли не совпадают")
                return

            try:
                self.svc.change_master_password(old_pwd, new_pwd)
                self._flash_status("✅ Мастер-пароль изменён")
                dlg.destroy()
            except Exception as e:
                status.configure(text=str(e))

        ctk.CTkButton(dlg, text="💾 Сменить пароль", command=submit).pack(pady=15)

    def _audit(self):
        report = self.svc.audit()
        msg = "📊 АУДИТ ХРАНИЛИЩА\n\n"
        if not report["weak"] and not report["duplicates"]:
            msg += "✅ Всё отлично! Слабых и повторяющихся паролей нет."
        else:
            if report["weak"]:
                msg += "⚠️ Слабые пароли (<12 символов):\n  • " + "\n  • ".join(report["weak"]) + "\n\n"
            if report["duplicates"]:
                msg += "⚠️ Повторяющиеся пароли:\n"
                for pwd, names in report["duplicates"].items():
                    if pwd:
                        mask = f"{pwd[0]}{'*' * min(len(pwd) - 1, 8)}"
                    else:
                        mask = "(пустой)"
                    msg += f"  • Пароль '{mask}': {', '.join(names)}\n"
        messagebox.showinfo("Аудит", msg)