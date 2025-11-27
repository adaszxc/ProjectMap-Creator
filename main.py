import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font
from datetime import datetime

# ============================ ИМПОРТЫ И ЗАВИСИМОСТИ ============================
# Импорты стандартных модулей и tkinter-интерфейса.

UI_SCALE = 2 # Масштаб интерфейса

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TREES_DIR = os.path.join(SCRIPT_DIR, "Деревья")

class Node:
    # =============================== КЛАСС NODE ===============================
    # Узел дерева проекта: файл или папка с дополнительными флагами.

    def __init__(self, name, path, is_dir, is_symlink, parent=None):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.is_symlink = is_symlink
        self.parent = parent
        self.children = []
        self.skip = False  # [×]
        self.has_children = False  # для корректного вывода "/" для корня и симлинков


class ProjectTreeApp:
    # =========================== КЛАСС PROJECTTREEAPP ===========================
    # Основное приложение: UI, построение дерева и генерация текстового файла.

    def __init__(self, root):
        self.root = root
        self.root.title("ProjectMap-Creator")

        self.root_node = None
        self.root_path = None
        self.item_to_node = {}
        self.current_node = None

        self._build_ui()

    def _build_ui(self):
        # ============================= ПОСТРОЕНИЕ UI =============================
        # Создание основного окна, дерева и панели деталей.

        base_font = font.nametofont("TkDefaultFont")
        base_font.configure(size=int(base_font["size"] * UI_SCALE))

        style = ttk.Style()
        style.configure("Treeview", rowheight=int(20 * UI_SCALE))

        main_frame = ttk.Frame(self.root, padding=int(10 * UI_SCALE))
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        self.choose_root_button = ttk.Button(
            top_frame,
            text="Выбрать корневую папку",
            command=self.choose_root_folder,
        )
        self.choose_root_button.pack(side=tk.LEFT)

        self.save_button = ttk.Button(
            top_frame,
            text="Сохранить дерево",
            command=self.save_tree,
            state=tk.DISABLED,
        )
        self.save_button.pack(side=tk.LEFT, padx=(int(100 * UI_SCALE), 0))

        splitter = ttk.Panedwindow(main_frame, orient=tk.HORIZONTAL)
        splitter.pack(fill=tk.BOTH, expand=True, pady=(int(10 * UI_SCALE), 0))

        tree_frame = ttk.Frame(splitter)
        details_frame = ttk.Frame(splitter)

        splitter.add(tree_frame, weight=3)
        splitter.add(details_frame, weight=2)

        self.tree = ttk.Treeview(tree_frame, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        details_inner = ttk.Frame(details_frame)
        details_inner.pack(fill=tk.BOTH, expand=True)

        path_label_title = ttk.Label(details_inner, text="Путь:")
        path_label_title.grid(row=0, column=0, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        self.path_label = ttk.Label(
            details_inner,
            text="",
            wraplength=int(300 * UI_SCALE),
            justify=tk.LEFT,
        )
        self.path_label.grid(row=0, column=1, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        type_label_title = ttk.Label(details_inner, text="Тип:")
        type_label_title.grid(row=1, column=0, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        self.type_label = ttk.Label(details_inner, text="")
        self.type_label.grid(row=1, column=1, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        symlink_label_title = ttk.Label(details_inner, text="Симлинк [→]:")
        symlink_label_title.grid(row=2, column=0, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        self.symlink_label = ttk.Label(details_inner, text="нет")
        self.symlink_label.grid(row=2, column=1, sticky=tk.W, pady=(0, int(5 * UI_SCALE)))

        skip_label_title = ttk.Label(details_inner, text="Не раскрывать [×]:")
        skip_label_title.grid(
            row=3,
            column=0,
            sticky=tk.W,
            pady=(int(10 * UI_SCALE), int(5 * UI_SCALE)),
        )

        self.skip_var = tk.IntVar(value=0)
        self.skip_check = ttk.Checkbutton(
            details_inner,
            variable=self.skip_var,
            command=self.on_skip_toggle,
        )
        self.skip_check.grid(
            row=3,
            column=1,
            sticky=tk.W,
            pady=(int(10 * UI_SCALE), int(5 * UI_SCALE)),
        )

        for i in range(4):
            details_inner.rowconfigure(i, weight=0)
        details_inner.columnconfigure(1, weight=1)

        self._update_details(None)


    def choose_root_folder(self):
        # ======================= ВЫБОР КОРНЕВОЙ ПАПКИ ==========================
        # Выбор корня проекта и подготовка папки "Деревья" рядом со скриптом.

        path = filedialog.askdirectory()
        if not path:
            return

        self.root_path = os.path.abspath(path)

        try:
            os.makedirs(TREES_DIR, exist_ok=True)
        except OSError:
            pass

        self.root_node = self._build_tree(self.root_path)
        if self.root_node is None:
            messagebox.showerror("Ошибка", "Не удалось прочитать структуру каталога.")
            return

        self._fill_treeview()
        self.save_button.config(state=tk.NORMAL)


    def _build_tree(self, path):
        # ========================= ПОСТРОЕНИЕ ДЕРЕВА ============================
        # Рекурсивное построение структуры Node для каталога.

        path = os.path.abspath(path)
        name = os.path.basename(path.rstrip("\\/")) or path
        is_symlink = os.path.islink(path)
        is_dir = os.path.isdir(path)

        node = Node(name=name, path=path, is_dir=is_dir, is_symlink=is_symlink)

        if not is_dir:
            node.has_children = False
            return node

        try:
            entries = []
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name in (".", ".."):
                        continue
                    entries.append(entry)
        except OSError:
            node.has_children = False
            return node

        dirs = [e for e in entries if e.is_dir(follow_symlinks=False)]
        files = [e for e in entries if not e.is_dir(follow_symlinks=False)]

        dirs.sort(key=lambda e: e.name.casefold())
        files.sort(key=lambda e: e.name.casefold())

        children_nodes = []

        for entry in dirs:
            entry_path = entry.path
            entry_is_symlink = entry.is_symlink()
            if entry_is_symlink:
                child = self._build_symlink_dir_node(entry)
            else:
                child = self._build_tree(entry_path)
            if child is not None:
                child.parent = node
                children_nodes.append(child)

        for entry in files:
            entry_path = entry.path
            entry_is_symlink = entry.is_symlink()
            child = Node(
                name=entry.name,
                path=entry_path,
                is_dir=False,
                is_symlink=entry_is_symlink,
                parent=node,
            )
            children_nodes.append(child)

        node.children = children_nodes
        node.has_children = bool(children_nodes)

        return node

    def _build_symlink_dir_node(self, entry):
        # =========================== УЗЕЛ ДЛЯ СИМЛИНКА ==========================
        # Создание узла для каталога-симлинка без рекурсии внутрь.

        path = entry.path
        name = entry.name
        node = Node(name=name, path=path, is_dir=True, is_symlink=True)

        has_children = False
        try:
            with os.scandir(path) as it:
                for _ in it:
                    has_children = True
                    break
        except OSError:
            has_children = False

        node.has_children = has_children
        node.children = []

        return node

    def _fill_treeview(self):
        # ========================= ЗАПОЛНЕНИЕ TREEVIEW ==========================
        # Перенос структуры Node в виджет дерева.

        self.tree.delete(*self.tree.get_children())
        self.item_to_node.clear()
        self.current_node = None

        if not self.root_node:
            return

        root_item = self.tree.insert("", "end", text=self.root_node.name, open=True)
        self.item_to_node[root_item] = self.root_node
        self.root_node.tree_item = root_item

        self._insert_children(self.root_node, root_item)

        self.tree.selection_set(root_item)
        self._update_details(self.root_node)

    def _insert_children(self, node, parent_item):
        # ========================== ДОБАВЛЕНИЕ ПОТОМКОВ =========================
        # Рекурсивное добавление дочерних узлов в дерево.

        for child in node.children:
            item = self.tree.insert(parent_item, "end", text=child.name, open=False)
            self.item_to_node[item] = child
            child.tree_item = item
            if child.is_dir and not child.is_symlink and child.children:
                self._insert_children(child, item)

    def on_tree_select(self, event):
        # ===================== ОБРАБОТКА ВЫБОРА УЗЛА ДЕРЕВА =====================
        # Обновление панели деталей при смене выделения.

        selection = self.tree.selection()
        if not selection:
            self._update_details(None)
            return

        item_id = selection[0]
        node = self.item_to_node.get(item_id)
        self.current_node = node
        self._update_details(node)

    def on_tree_double_click(self, event):
        # =================== ОБРАБОТКА ДВОЙНОГО КЛИКА ПО УЗЛУ ===================
        # Переключение флага skip [×] для папок, включая корень, без раскрытия.

        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return "break"

        node = self.item_to_node.get(item_id)
        if not node or not node.is_dir:
            return "break"

        node.skip = not node.skip
        self.current_node = node
        self._update_details(node)

        return "break"


    def _update_details(self, node):
        # ================== ОБНОВЛЕНИЕ ПАНЕЛИ ДЕТАЛЕЙ СПРАВА ====================
        # Отображение пути, типа и флагов для выбранного узла.

        if node is None:
            self.path_label.config(text="")
            self.type_label.config(text="")
            self.symlink_label.config(text="нет")
            self.skip_var.set(0)
            self.skip_check.state(["disabled"])
            return

        self.path_label.config(text=node.path)

        if node.is_dir:
            self.type_label.config(text="папка")
        else:
            self.type_label.config(text="файл")

        self.symlink_label.config(text="да" if node.is_symlink else "нет")

        if node.is_dir:
            self.skip_check.state(["!disabled"])
            self.skip_var.set(1 if node.skip else 0)
        else:
            self.skip_check.state(["disabled"])
            self.skip_var.set(0)

    def on_skip_toggle(self):
        # ================= ОБРАБОТКА ПЕРЕКЛЮЧЕНИЯ ФЛАГА SKIP [×] =================
        # Переключение флага skip через чекбокс для любой папки, включая корень.

        if not self.current_node:
            return
        if not self.current_node.is_dir:
            return
        self.current_node.skip = bool(self.skip_var.get())

    def save_tree(self):
        # ========================== СОХРАНЕНИЕ ДЕРЕВА ===========================
        # Формирование текста дерева и сохранение в файл UTF-8 без BOM.

        if not self.root_node or not self.root_path:
            return

        text = self._generate_tree_text()

        default_dir = TREES_DIR
        os.makedirs(default_dir, exist_ok=True)

        root_name = self.root_node.name
        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y %H.%M")
        default_name = f"{root_name} {date_str}.txt"

        while True:
            file_path = filedialog.asksaveasfilename(
                title="Сохранить дерево",
                initialdir=default_dir,
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")],
            )

            if not file_path:
                return

            if os.path.exists(file_path):
                messagebox.showerror("Ошибка", "Файл с таким именем уже существует")
                continue

            break

        try:
            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
            return

        messagebox.showinfo("Готово", "Файл успешно сохранён.")

    def _generate_tree_text(self):
        # ======================== ГЕНЕРАЦИЯ ТЕКСТА ДЕРЕВА =======================
        # Формирование строк дерева проекта для записи в файл.

        lines = []

        lines.append("   [×] - обозначает что пользователь не стал раскрывать эту папку ")
        lines.append("   [→] - обозначает символическую ссылку или junction (не раскрывается)")
        lines.append("   Если у имени папки нет завершающего /, значит папка пустая.")

        lines.append(f"ROOT: {self.root_path}")

        if self.root_node.is_dir:
            has_children = self.root_node.has_children or bool(self.root_node.children)
            root_line = self._format_node_line(self.root_node)
            if not has_children:
                root_line = root_line.replace("/", "")
        else:
            root_line = self.root_node.name

        lines.append(root_line)

        if self.root_node.is_dir and not self.root_node.skip and self.root_node.children:
            self._render_children(self.root_node, prefix="", lines=lines)

        return "\n".join(lines)

    def _render_children(self, node, prefix, lines):
        # ======================= РЕКУРСИВНЫЙ ВЫВОД ПОТОМКОВ =====================
        # Вывод дочерних узлов с нужными префиксами линий.

        children = node.children
        count = len(children)
        for index, child in enumerate(children):
            is_last = index == count - 1
            connector = "└─ " if is_last else "├─ "
            line_prefix = prefix + connector
            line_text = self._format_node_line(child)
            lines.append(line_prefix + line_text)

            if child.is_dir and not child.is_symlink and not child.skip and child.children:
                new_prefix = prefix + ("   " if is_last else "│  ")
                self._render_children(child, new_prefix, lines)

    def _format_node_line(self, node):
        # ========================= ФОРМАТИРОВАНИЕ СТРОКИ ========================
        # Формирование строки для узла с учётом /, [×] и [→].

        if not node.is_dir:
            return node.name

        if node.is_symlink:
            has_children = node.has_children
        else:
            has_children = bool(node.children)

        slash = "/" if has_children else ""

        mark_before = "[×] " if node.skip else ""
        mark_after = " [→]" if node.is_symlink else ""

        return f"{mark_before}{node.name}{slash}{mark_after}"


def main():
    # ============================ ТОЧКА ВХОДА APP ==============================
    # Создание и запуск главного окна приложения.

    root = tk.Tk()
    app = ProjectTreeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
