from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import resolve_font
from .epub_reader import read_epub
from .pdf_writer import write_pdf
from .translation import TranslationConfig, fetch_available_models
from .translation_progress import TranslationCheckpoint, translate_book_with_checkpoint


WINDOW_BACKGROUND = "#f5f5f2"
PANEL_BACKGROUND = "#ffffff"
TEXT_COLOR = "#222522"
MUTED_COLOR = "#5f665f"
ACCENT_COLOR = "#087e6b"
ACCENT_ACTIVE = "#056353"
ERROR_COLOR = "#b3261e"
TARGET_LANGUAGES = (
    "简体中文",
    "繁體中文",
    "English",
    "日本語",
    "한국어",
    "Français",
    "Deutsch",
    "Español",
    "Português",
    "Italiano",
    "Русский",
    "العربية",
)


def default_output_path(source: Path) -> Path:
    return source.with_name(f"{source.stem}.pdf")


def normalize_output_path(value: Path) -> Path:
    return value if value.suffix.lower() == ".pdf" else value.with_suffix(".pdf")


class ConverterApp(ttk.Frame):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root, padding=(28, 24))
        self.root = root
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.connection_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.connection_running = False
        self.models_loaded = False
        self.output_file: Path | None = None

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.font_var = tk.StringVar()
        self.translate_var = tk.BooleanVar(value=False)
        self.api_base_var = tk.StringVar(value="https://api.openai.com/v1")
        self.model_var = tk.StringVar(value="gpt-5.6-terra")
        self.api_key_var = tk.StringVar()
        self.language_var = tk.StringVar(value="简体中文")
        self.chunk_size_var = tk.StringVar(value="20000")
        self.status_var = tk.StringVar(value="选择一本 EPUB 开始转换")
        self.api_status_var = tk.StringVar(value="填写 API 地址和密钥后测试连接。")
        self.output_status_var = tk.StringVar(value="输出文件将在转换完成后显示")
        self.translation_widgets: list[ttk.Widget] = []

        self.api_base_var.trace_add("write", self._clear_loaded_models)
        self.api_key_var.trace_add("write", self._clear_loaded_models)

        self._configure_window()
        self._build_layout()
        self._set_translation_state()
        self.pack(fill="both", expand=True)

    def _configure_window(self) -> None:
        self.root.title("EPUB to PDF")
        self.root.geometry("920x760")
        self.root.minsize(760, 660)
        self.root.configure(background=WINDOW_BACKGROUND)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=WINDOW_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("TLabel", background=PANEL_BACKGROUND, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL_BACKGROUND, foreground=MUTED_COLOR, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=WINDOW_BACKGROUND, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 22))
        style.configure("Subtitle.TLabel", background=WINDOW_BACKGROUND, foreground=MUTED_COLOR, font=("Segoe UI", 10))
        style.configure("TEntry", padding=7)
        style.configure("TCheckbutton", background=PANEL_BACKGROUND, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 10))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI", 9))
        style.configure("Primary.TButton", background=ACCENT_COLOR, foreground="#ffffff", font=("Segoe UI Semibold", 10))
        style.map("Primary.TButton", background=[("active", ACCENT_ACTIVE), ("disabled", "#9da8a2")])
        style.configure("Horizontal.TProgressbar", troughcolor="#e5e8e4", background=ACCENT_COLOR, lightcolor=ACCENT_COLOR, darkcolor=ACCENT_COLOR)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="EPUB 转 PDF", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="可选地使用兼容 OpenAI Responses API 的模型接口翻译正文", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 18))

        files = self._panel(row=2)
        files.columnconfigure(1, weight=1)
        self._path_row(files, 0, "输入 EPUB", self.source_var, self._choose_source, "选择文件")
        self._path_row(files, 1, "输出 PDF", self.output_var, self._choose_output, "选择位置")
        self._path_row(files, 2, "字体（可选）", self.font_var, self._choose_font, "选择字体")
        ttk.Label(files, text="未指定字体时会自动查找 Windows 中文字体。", style="Muted.TLabel").grid(row=3, column=1, sticky="w", pady=(0, 10))

        translation = self._panel(row=3, pady=(14, 0))
        translation.columnconfigure(1, weight=1)
        self.translation_check = ttk.Checkbutton(
            translation, text="转换前翻译正文", variable=self.translate_var,
            command=self._set_translation_state,
        )
        self.translation_check.grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(13, 10))
        self._field_row(translation, 1, "API 地址", self.api_base_var)
        self._field_row(translation, 2, "API 密钥", self.api_key_var, show="*")
        self.connection_button = ttk.Button(translation, text="测试连接并获取模型", command=self._test_connection)
        self.connection_button.grid(row=3, column=1, sticky="w", pady=(6, 3))
        ttk.Label(translation, textvariable=self.api_status_var, style="Muted.TLabel", wraplength=600).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 6))
        self._model_row(translation, 5)
        self._language_row(translation, 6)
        self._field_row(translation, 7, "请求字符数", self.chunk_size_var)
        ttk.Label(translation, text="密钥只用于本次请求，不会保存到文件。", style="Muted.TLabel").grid(row=8, column=1, sticky="w", pady=(0, 13))

        action = self._panel(row=4, pady=(14, 0))
        action.columnconfigure(0, weight=1)
        self.convert_button = ttk.Button(action, text="开始转换", style="Primary.TButton", command=self._start_conversion)
        self.convert_button.grid(row=0, column=0, sticky="w", padx=14, pady=(13, 8))
        self.progress = ttk.Progressbar(action, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", padx=14)
        ttk.Label(action, textvariable=self.status_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w", padx=14, pady=(8, 13))

        result = self._panel(row=5, pady=(14, 0))
        result.columnconfigure(0, weight=1)
        ttk.Label(result, text="输出", font=("Segoe UI Semibold", 10)).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))
        ttk.Label(result, textvariable=self.output_status_var, style="Muted.TLabel", wraplength=740).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        buttons = ttk.Frame(result, style="Panel.TFrame")
        buttons.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 13))
        self.open_file_button = ttk.Button(buttons, text="打开 PDF", command=self._open_output, state="disabled")
        self.open_file_button.grid(row=0, column=0)
        self.open_folder_button = ttk.Button(buttons, text="打开所在文件夹", command=self._open_output_folder, state="disabled")
        self.open_folder_button.grid(row=0, column=1, padx=(8, 0))

    def _panel(self, row: int, pady: tuple[int, int] = (0, 0)) -> ttk.Frame:
        panel = ttk.Frame(self, style="Panel.TFrame", padding=(0, 0))
        panel.grid(row=row, column=0, sticky="ew", pady=pady)
        return panel

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command, button_text: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(14, 12), pady=8)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Button(parent, text=button_text, command=command).grid(row=row, column=2, padx=(8, 14), pady=8)

    def _field_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, show: str | None = None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(14, 12), pady=5)
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=5)
        self.translation_widgets.append(entry)

    def _language_row(self, parent: ttk.Frame, row: int) -> None:
        ttk.Label(parent, text="目标语言").grid(row=row, column=0, sticky="w", padx=(14, 12), pady=5)
        selector = ttk.Combobox(
            parent, textvariable=self.language_var, values=TARGET_LANGUAGES,
            state="readonly",
        )
        selector.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=5)
        self.translation_widgets.append(selector)

    def _model_row(self, parent: ttk.Frame, row: int) -> None:
        ttk.Label(parent, text="模型").grid(row=row, column=0, sticky="w", padx=(14, 12), pady=5)
        self.model_selector = ttk.Combobox(parent, textvariable=self.model_var, state="disabled")
        self.model_selector.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=5)

    def _choose_source(self) -> None:
        selected = filedialog.askopenfilename(title="选择 EPUB 文件", filetypes=[("EPUB 文件", "*.epub"), ("所有文件", "*.*")])
        if selected:
            source = Path(selected)
            self.source_var.set(str(source))
            if not self.output_var.get().strip():
                self.output_var.set(str(default_output_path(source)))

    def _choose_output(self) -> None:
        source = Path(self.source_var.get()) if self.source_var.get().strip() else Path("book.epub")
        selected = filedialog.asksaveasfilename(
            title="选择 PDF 输出位置", defaultextension=".pdf", initialfile=default_output_path(source).name,
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if selected:
            self.output_var.set(selected)

    def _choose_font(self) -> None:
        selected = filedialog.askopenfilename(title="选择 TrueType 字体", filetypes=[("TrueType 字体", "*.ttf *.otf"), ("所有文件", "*.*")])
        if selected:
            self.font_var.set(selected)

    def _set_translation_state(self) -> None:
        for widget in self.translation_widgets:
            if self.connection_running:
                widget.configure(state="disabled")
                continue
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if self.translate_var.get() else "disabled")
            else:
                widget.configure(state="normal" if self.translate_var.get() else "disabled")
        self.connection_button.configure(state="normal" if self.translate_var.get() and not self.connection_running else "disabled")
        self.model_selector.configure(state="readonly" if self.translate_var.get() and self.models_loaded else "disabled")

    def _clear_loaded_models(self, *_args) -> None:
        if not self.models_loaded:
            return
        self.models_loaded = False
        self.model_var.set("")
        self.model_selector.configure(values=(), state="disabled")
        self.api_status_var.set("API 地址或密钥已修改，请重新测试连接。")

    def _test_connection(self) -> None:
        if self.connection_running:
            return
        api_base = self.api_base_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if not api_base:
            messagebox.showerror("缺少 API 地址", "请填写 API 根地址，例如 https://api.openai.com/v1。", parent=self.root)
            return
        if not api_key:
            messagebox.showerror("缺少 API 密钥", "请填写 API 密钥后再测试连接。", parent=self.root)
            return

        self.connection_running = True
        self.models_loaded = False
        self.model_selector.configure(values=(), state="disabled")
        self.connection_button.configure(state="disabled")
        self.api_status_var.set("正在测试连接并获取模型列表...")
        threading.Thread(target=self._connection_worker, args=(api_base, api_key), daemon=True).start()
        self.after(100, self._poll_connection_events)

    def _connection_worker(self, api_base: str, api_key: str) -> None:
        try:
            models = fetch_available_models(TranslationConfig(api_base=api_base, api_key=api_key))
            self.connection_events.put(("success", models))
        except Exception as exc:  # Keep worker errors visible in the GUI instead of leaving controls locked.
            self.connection_events.put(("error", str(exc)))

    def _poll_connection_events(self) -> None:
        try:
            event, value = self.connection_events.get_nowait()
        except queue.Empty:
            if self.connection_running:
                self.after(100, self._poll_connection_events)
            return
        self.connection_running = False
        if event == "success":
            models = list(value)
            self.models_loaded = True
            self.model_selector.configure(values=models)
            if self.model_var.get() not in models:
                self.model_var.set("")
            self.api_status_var.set(f"连接成功，已获取 {len(models)} 个模型。请选择一个支持 Responses API 的文本模型。")
            self._set_translation_state()
        else:
            self.api_status_var.set("连接失败。请检查 API 地址、密钥和服务权限。")
            self._set_translation_state()
            messagebox.showerror("API 连接失败", str(value), parent=self.root)

    def _start_conversion(self) -> None:
        if self.running:
            return
        source_text = self.source_var.get().strip()
        output_text = self.output_var.get().strip()
        if not source_text:
            messagebox.showerror("缺少输入文件", "请选择要转换的 EPUB 文件。", parent=self.root)
            return
        if not output_text:
            messagebox.showerror("缺少输出路径", "请选择 PDF 输出位置。", parent=self.root)
            return
        if self.connection_running:
            messagebox.showinfo("正在测试连接", "请等待模型列表加载完成后再开始转换。", parent=self.root)
            return
        output = normalize_output_path(Path(output_text))
        if output != Path(output_text):
            self.output_var.set(str(output))
        if self.translate_var.get() and (not self.api_base_var.get().strip() or not self.model_var.get().strip()):
            messagebox.showerror("翻译配置不完整", "请先测试连接并从模型列表中选择一个模型。", parent=self.root)
            return
        try:
            chunk_size = int(self.chunk_size_var.get())
            if self.translate_var.get() and chunk_size < 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("请求字符数无效", "翻译时请求字符数必须是不小于 100 的整数。", parent=self.root)
            return

        self.running = True
        self.output_file = None
        self.convert_button.configure(state="disabled")
        self.open_file_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self.status_var.set("正在读取 EPUB...")
        self.output_status_var.set("转换正在进行，请保持窗口打开。")
        self.progress.start(12)
        request = {
            "source": Path(source_text), "output": output, "font": Path(self.font_var.get()) if self.font_var.get().strip() else None,
            "translate": self.translate_var.get(), "api_base": self.api_base_var.get().strip(), "model": self.model_var.get().strip(),
            "api_key": self.api_key_var.get().strip() or None, "target_language": self.language_var.get().strip(), "chunk_size": chunk_size,
        }
        threading.Thread(target=self._convert_worker, args=(request,), daemon=True).start()
        self.after(100, self._poll_events)

    def _convert_worker(self, request: dict) -> None:
        checkpoint: TranslationCheckpoint | None = None
        try:
            if not request["source"].is_file():
                raise FileNotFoundError(f"找不到 EPUB 文件：{request['source']}")
            book = read_epub(request["source"])
            if request["translate"]:
                self.events.put(("status", "正在翻译正文..."))
                book, checkpoint = translate_book_with_checkpoint(
                    book,
                    request["source"],
                    request["output"],
                    TranslationConfig(
                        model=request["model"], target_language=request["target_language"], api_base=request["api_base"],
                        api_key=request["api_key"], chunk_size=request["chunk_size"],
                    ),
                    progress=lambda message: self.events.put(("status", message)),
                )
            self.events.put(("status", "正在排版并写入 PDF..."))
            write_pdf(book, request["output"], resolve_font(request["font"]))
            if checkpoint:
                checkpoint.clear()
            self.events.put(("success", request["output"]))
        except Exception as exc:  # The UI must turn every worker failure into an actionable message.
            message = str(exc)
            if checkpoint and checkpoint.path.exists():
                message += f"\n\n翻译进度已保存。使用相同 EPUB、输出路径、模型和目标语言重新开始，即可继续：\n{checkpoint.path}"
            self.events.put(("error", message))

    def _poll_events(self) -> None:
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status_var.set(str(value))
                elif event == "success":
                    self._finish_success(Path(value))
                    return
                elif event == "error":
                    self._finish_error(str(value))
                    return
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_events)

    def _finish_success(self, output: Path) -> None:
        self.running = False
        self.output_file = output
        self.progress.stop()
        self.convert_button.configure(state="normal")
        self.open_file_button.configure(state="normal")
        self.open_folder_button.configure(state="normal")
        self.status_var.set("转换完成")
        self.output_status_var.set(f"PDF 已保存到：{output}")

    def _finish_error(self, message: str) -> None:
        self.running = False
        self.progress.stop()
        self.convert_button.configure(state="normal")
        self.status_var.set("转换失败")
        self.output_status_var.set("未生成 PDF。请检查输入文件、字体或 API 配置。")
        messagebox.showerror("转换失败", message, parent=self.root)

    def _open_output(self) -> None:
        if self.output_file and self.output_file.is_file():
            webbrowser.open(self.output_file.resolve().as_uri())

    def _open_output_folder(self) -> None:
        if self.output_file:
            webbrowser.open(self.output_file.parent.resolve().as_uri())


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
