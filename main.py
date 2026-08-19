#!/usr/bin/env python3
"""Точка входа приложения"""
import sys
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from config import APP_TITLE
from storage import vault_exists, init_vault, load_vault
from vault import VaultService
from gui import LoginWindow, MainApp


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    exists = vault_exists()

    # Callback валидации пароля
    def validate(password: str) -> None:
        """Проверяет/создаёт хранилище. Бросает исключение при ошибке."""
        if not exists:
            init_vault(password)
        else:
            load_vault(password)

    # ---Окно входа---
    login = LoginWindow(exists, validate)
    login.mainloop()

    try:
        login.destroy()
    except tk.TclError:
        pass

    # Если пользователь закрыл окно без входа
    if login.master_password is None:
        sys.exit(0)

    # --- Главное окно (после успешного входа) ---
    service = VaultService(login.master_password)
    app = MainApp(service)
    app.mainloop()

    try:
        login.destroy()
    except tk.TclError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        messagebox.showerror(APP_TITLE, f"Ошибка: {e}")
        raise