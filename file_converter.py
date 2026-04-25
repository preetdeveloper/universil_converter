import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from PIL import Image, ImageTk
import os
import threading

# ─── CONFIG ───────────────────────────────────────────────────────────────────
ASSETS = r"C:\Users\Preet\Desktop\o\code\file_converter"
APP_TITLE = "UniConvert"
WIN_W, WIN_H = 700, 700

# Which formats each input type can convert TO
CONVERSION_MAP = {
    ".jpg":  ["png", "jpeg", "ico", "pdf", "bmp", "webp"],
    ".jpeg": ["jpg", "png", "ico", "pdf", "bmp", "webp"],
    ".jfif": ["jpg", "png", "jpeg", "ico", "pdf"],
    ".png":  ["jpg", "jpeg", "ico", "pdf", "bmp", "webp"],
    ".bmp":  ["jpg", "png", "jpeg", "ico", "pdf"],
    ".webp": ["jpg", "png", "jpeg", "pdf"],
    ".ico":  ["png", "jpg"],
    ".pdf":  ["jpg", "png", "jpeg"],
    ".txt":  ["pdf"],
    ".svg":  ["png", "jpg", "pdf"],
}

FORMAT_ICONS = ["ico", "jfif", "jpeg", "jpg", "pdf", "png", "svg", "txt"]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ─── CONVERSION LOGIC ─────────────────────────────────────────────────────────
def do_convert(input_path, output_format, output_folder, progress_cb, done_cb):
    try:
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_file = os.path.join(output_folder, f"{base}.{output_format}")
        ext = os.path.splitext(input_path)[1].lower()

        progress_cb(20)

        # PDF → Image
        if ext == ".pdf" and output_format in ("jpg", "jpeg", "png"):
            try:
                from pdf2image import convert_from_path
            except ImportError:
                done_cb(False, "Install pdf2image + poppler:\npip install pdf2image")
                return
            pages = convert_from_path(input_path)
            progress_cb(60)
            if len(pages) == 1:
                pages[0].save(out_file)
            else:
                for i, page in enumerate(pages):
                    page.save(os.path.join(output_folder, f"{base}_page{i+1}.{output_format}"))
            progress_cb(100)
            done_cb(True, out_file)
            return

        # TXT → PDF
        if ext == ".txt" and output_format == "pdf":
            try:
                from reportlab.pdfgen import canvas as rl_canvas
            except ImportError:
                done_cb(False, "Install reportlab:\npip install reportlab")
                return
            with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            progress_cb(40)
            c = rl_canvas.Canvas(out_file)
            y = 800
            for line in lines:
                if y < 50:
                    c.showPage()
                    y = 800
                c.drawString(40, y, line.rstrip())
                y -= 15
            c.save()
            progress_cb(100)
            done_cb(True, out_file)
            return

        # SVG → raster
        if ext == ".svg":
            try:
                import cairosvg
                progress_cb(60)
                if output_format == "png":
                    cairosvg.svg2png(url=input_path, write_to=out_file)
                elif output_format in ("jpg", "jpeg"):
                    tmp = out_file.replace(f".{output_format}", "_tmp.png")
                    cairosvg.svg2png(url=input_path, write_to=tmp)
                    Image.open(tmp).convert("RGB").save(out_file)
                    os.remove(tmp)
                elif output_format == "pdf":
                    cairosvg.svg2pdf(url=input_path, write_to=out_file)
                progress_cb(100)
                done_cb(True, out_file)
            except ImportError:
                done_cb(False, "Install cairosvg:\npip install cairosvg")
            return

        # Image → Image / ICO / PDF
        img = Image.open(input_path)
        progress_cb(40)

        if output_format == "ico":
            img.save(out_file, format="ICO", sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
        elif output_format == "pdf":
            rgb = img.convert("RGB")
            rgb.save(out_file, format="PDF")
        elif output_format in ("jpg", "jpeg", "jfif"):
            img.convert("RGB").save(out_file, format="JPEG", quality=95)
        else:
            img.save(out_file, format=output_format.upper())

        progress_cb(100)
        done_cb(True, out_file)

    except Exception as e:
        done_cb(False, str(e))


# ─── MAIN APP ─────────────────────────────────────────────────────────────────
class UniConvert(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(1000, 500)
        self.maxsize(1200, 800)
        # self.resizable(True, False)

        self.input_path = None
        self.output_folder = None
        self.selected_format = tk.StringVar(value="")
        self.format_buttons = {}
        self.icon_images = {}   # keep refs alive

        self._load_icons()
        self._build_ui()

    # ── load all PNG icons from assets folder ──
    def _load_icons(self):
        for name in FORMAT_ICONS:
            path = os.path.join(ASSETS, f"{name}.png")
            if os.path.exists(path):
                img = Image.open(path).resize((56, 56), Image.LANCZOS)
                self.icon_images[name] = ImageTk.PhotoImage(img)

        # browse & convert buttons
        for name in ("browse", "convert"):
            path = os.path.join(ASSETS, f"{name}.png")
            if os.path.exists(path):
                img = Image.open(path).resize((110, 42), Image.LANCZOS)
                self.icon_images[name] = ImageTk.PhotoImage(img)

        # background
        bg_path = os.path.join(ASSETS, "background.png")
        if os.path.exists(bg_path):
            self.bg_pil = Image.open(bg_path)
        else:
            self.bg_pil = None

    # ── build all widgets ──
    def _build_ui(self):
        # Canvas for background
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._on_resize)

        # ── Title ──
        self.lbl_title = ctk.CTkLabel(
            self, text="UniConvert",
            font=ctk.CTkFont(family="Segoe UI Black", size=26, weight="bold"),
            text_color="#ffffff"
        )
        self.lbl_title.place(relx=0.5, y=18, anchor="n")

        # ── LEFT PANEL ──
        self.left = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=16, border_width=1, border_color="#2a2a4a")
        self.left.place(relx=0.03, rely=0.14, relwidth=0.44, relheight=0.70)

        ctk.CTkLabel(self.left, text="📂  Upload File",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#a0a0cc").pack(pady=(14,6))

        # browse button (image or fallback)
        if "browse" in self.icon_images:
            self.btn_browse = tk.Button(
                self.left, image=self.icon_images["browse"],
                bd=0, bg="#1a1a2e", activebackground="#1a1a2e",
                cursor="hand2", command=self._browse_file
            )
        else:
            self.btn_browse = ctk.CTkButton(self.left, text="Browse", command=self._browse_file)
        self.btn_browse.pack(pady=4)

        self.lbl_file = ctk.CTkLabel(
            self.left, text="No file selected",
            font=ctk.CTkFont(size=10), text_color="#666688",
            wraplength=160
        )
        self.lbl_file.pack(pady=(6,2), padx=8)

        self.lbl_type = ctk.CTkLabel(
            self.left, text="",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#7fb3f5"
        )
        self.lbl_type.pack(pady=2)

        # output folder
        ctk.CTkLabel(self.left, text="💾  Output Folder",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#a0a0cc").pack(pady=(16,4))

        self.btn_folder = ctk.CTkButton(
            self.left, text="Select Folder", height=30,
            fg_color="#2a2a5a", hover_color="#3a3a7a",
            font=ctk.CTkFont(size=11), command=self._choose_folder
        )
        self.btn_folder.pack(padx=12)

        self.lbl_folder = ctk.CTkLabel(
            self.left, text="Same as input file",
            font=ctk.CTkFont(size=9), text_color="#555577",
            wraplength=160
        )
        self.lbl_folder.pack(pady=3)

        # ── RIGHT PANEL ──
        self.right = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=16, border_width=1, border_color="#2a2a4a")
        self.right.place(relx=0.53, rely=0.14, relwidth=0.44, relheight=0.70)

        self.lbl_convert_title = ctk.CTkLabel(
            self.right, text="🔄  Convert To",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#a0a0cc"
        )
        self.lbl_convert_title.pack(pady=(14,6))

        self.format_frame = ctk.CTkScrollableFrame(
            self.right, fg_color="transparent", height=220
        )
        self.format_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.lbl_hint = ctk.CTkLabel(
            self.right, text="Upload a file first",
            font=ctk.CTkFont(size=10), text_color="#444466"
        )
        self.lbl_hint.place(relx=0.5, rely=0.5, anchor="center")

        # ── BOTTOM ──
        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self.progress.place(relx=0.03, rely=0.86, relwidth=0.94)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(
            self, text="Ready", font=ctk.CTkFont(size=10), text_color="#556677"
        )
        self.lbl_status.place(relx=0.5, rely=0.90, anchor="n")

        # convert button
        if "convert" in self.icon_images:
            self.btn_convert = tk.Button(
                self, image=self.icon_images["convert"],
                bd=0, bg="#0d0d1a", activebackground="#0d0d1a",
                cursor="hand2", command=self._start_convert
            )
        else:
            self.btn_convert = ctk.CTkButton(self, text="Convert!", command=self._start_convert)
        self.btn_convert.place(relx=0.5, rely=0.93, anchor="n")

        self._draw_bg(WIN_W, WIN_H)

    # ── background resize ──
    def _on_resize(self, event):
        self._draw_bg(event.width, event.height)

    def _draw_bg(self, w, h):
        if self.bg_pil:
            img = self.bg_pil.resize((w, h), Image.LANCZOS)
            self._bg_tk = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self._bg_tk, anchor="nw")
        else:
            self.canvas.configure(bg="#0d0d1a")

    # ── browse file ──
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[
                ("All supported", "*.jpg *.jpeg *.jfif *.png *.bmp *.webp *.ico *.pdf *.txt *.svg"),
                ("Images", "*.jpg *.jpeg *.jfif *.png *.bmp *.webp *.ico *.svg"),
                ("Documents", "*.pdf *.txt"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        self.input_path = path
        name = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        self.lbl_file.configure(text=name)
        self.lbl_type.configure(text=f"Type: {ext.upper()}")
        self.progress.set(0)
        self.lbl_status.configure(text="Ready")
        self._show_format_options(ext)

    # ── show format buttons ──
    def _show_format_options(self, ext):
        for w in self.format_frame.winfo_children():
            w.destroy()
        self.format_buttons.clear()
        self.selected_format.set("")
        self.lbl_hint.place_forget()

        options = CONVERSION_MAP.get(ext, [])
        if not options:
            self.lbl_hint.configure(text=f"No conversions\nfor {ext}")
            self.lbl_hint.place(relx=0.5, rely=0.5, anchor="center")
            return

        # grid: 3 per row
        for i, fmt in enumerate(options):
            col = i % 3
            row = i // 3
            cell = ctk.CTkFrame(self.format_frame, fg_color="transparent")
            cell.grid(row=row, column=col, padx=4, pady=4)

            if fmt in self.icon_images:
                btn = tk.Button(
                    cell, image=self.icon_images[fmt],
                    bd=2, bg="#1a1a2e", activebackground="#2a2a5a",
                    relief="flat", cursor="hand2",
                    command=lambda f=fmt: self._select_format(f)
                )
                btn.pack()
                lbl = tk.Label(cell, text=fmt.upper(), fg="#888899", bg="#1a1a2e",
                               font=("Segoe UI", 8))
                lbl.pack()
            else:
                btn = ctk.CTkButton(
                    cell, text=fmt.upper(), width=60, height=40,
                    fg_color="#2a2a4a", hover_color="#3a3a6a",
                    command=lambda f=fmt: self._select_format(f)
                )
                btn.pack()

            self.format_buttons[fmt] = btn

    # ── select output format ──
    def _select_format(self, fmt):
        # reset all
        for f, btn in self.format_buttons.items():
            if isinstance(btn, tk.Button):
                btn.configure(bg="#1a1a2e", relief="flat")
            else:
                btn.configure(fg_color="#2a2a4a")

        # highlight selected
        sel = self.format_buttons.get(fmt)
        if sel:
            if isinstance(sel, tk.Button):
                sel.configure(bg="#2a4a8a", relief="groove")
            else:
                sel.configure(fg_color="#2a4a8a")

        self.selected_format.set(fmt)
        self.lbl_status.configure(text=f"Will convert → {fmt.upper()}")

    # ── choose output folder ──
    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder = folder
            short = folder if len(folder) < 30 else "..." + folder[-27:]
            self.lbl_folder.configure(text=short)

    # ── start conversion ──
    def _start_convert(self):
        if not self.input_path:
            messagebox.showwarning("No File", "Please select a file first!")
            return
        fmt = self.selected_format.get()
        if not fmt:
            messagebox.showwarning("No Format", "Please select output format!")
            return

        out_folder = self.output_folder or os.path.dirname(self.input_path)
        self.progress.set(0)
        self.lbl_status.configure(text="Converting...")
        self.btn_convert.configure(state="disabled") if hasattr(self.btn_convert, 'configure') else None

        def progress_cb(val):
            self.progress.set(val / 100)
            self.update_idletasks()

        def done_cb(success, info):
            self.btn_convert.configure(state="normal") if hasattr(self.btn_convert, 'configure') else None
            if success:
                self.lbl_status.configure(text=f"✅ Done! Saved.")
                messagebox.showinfo("Success!", f"File saved:\n{info}")
            else:
                self.lbl_status.configure(text="❌ Failed")
                messagebox.showerror("Error", f"Conversion failed:\n{info}")

        t = threading.Thread(
            target=do_convert,
            args=(self.input_path, fmt, out_folder, progress_cb, done_cb),
            daemon=True
        )
        t.start()


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = UniConvert()
    app.mainloop()
