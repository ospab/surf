import os
import subprocess
import sys


def build_executable():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, "main.py")
    ui_dir = os.path.join(base_dir, "ui")
    styles_dir = os.path.join(base_dir, "styles")
    resources_dir = os.path.join(base_dir, "resources")

    # Компиляция формы перед сборкой
    history_ui = os.path.join(ui_dir, "history.ui")
    history_py = os.path.join(ui_dir, "ui_history.py")
    if os.path.exists(history_ui):
        print(f"Компиляция {history_ui} -> {history_py}...")
        subprocess.run([sys.executable, "-m", "PyQt6.uic.pyuic", history_ui, "-o", history_py], check=True)

    # Параметры PyInstaller
    # На Windows разделитель пути данных - точка с запятой ';'
    sep = ";" if sys.platform == "win32" else ":"
    data_args = [
        f"--add-data={ui_dir}{sep}ui",
        f"--add-data={styles_dir}{sep}styles",
        f"--add-data={resources_dir}{sep}resources",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=surf",
        "--noconsole",
        "--onedir",
        "--clean",
        # Перезаписывать dist/surf без вопроса: иначе повторная сборка падает,
        # если папка уже существует
        "--noconfirm",
        f"--icon={os.path.join(resources_dir, 'icons', 'app.ico')}",
        *data_args,
        main_script,
    ]

    print("Запуск сборки PyInstaller...")
    print("Команда:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\nСборка успешно завершена! Исполняемый файл находится в папке dist/surf/")


if __name__ == "__main__":
    build_executable()
