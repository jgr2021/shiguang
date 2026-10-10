"""Shared visual components and positioning for Shiguang's desktop windows."""
import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from tkinter import ttk, font as tkfont

from localization import tr

P = {"bg": "#F4F6F2", "paper": "#FFFFFF", "ink": "#273E34", "muted": "#738178",
     "line": "#E3E9E2", "green": "#2D6953", "pale": "#E7F0E8", "soft": "#F1F5EF",
     "orange": "#AC7339", "red": "#AB5148"}
FONT = "Microsoft YaHei UI"


def _hwnd(window):
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetParent.argtypes = [wintypes.HWND]
    user.GetParent.restype = wintypes.HWND
    return user.GetParent(window.winfo_id()) or window.winfo_id()


def work_area(owner):
    fallback = (0, 0, owner.winfo_screenwidth(), owner.winfo_screenheight())
    if sys.platform != "win32":
        return fallback
    try:
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user.MonitorFromWindow.restype = wintypes.HANDLE
        user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        user.GetMonitorInfoW.restype = wintypes.BOOL
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user.GetMonitorInfoW(user.MonitorFromWindow(_hwnd(owner), 2), ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    except (OSError, AttributeError, tk.TclError):
        pass
    return fallback


def decorate(window):
    """Use the OS title bar and shadow; unsupported Windows versions keep defaults."""
    if sys.platform != "win32":
        return
    try:
        api = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        api.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        api.restype = ctypes.c_long
        def color(hex_value):
            r, g, b = (int(hex_value[i:i + 2], 16) for i in (1, 3, 5))
            return r | (g << 8) | (b << 16)
        for attribute, raw in ((33, 2), (34, color(P["line"])), (35, color(P["bg"])), (36, color(P["ink"]))):
            value = ctypes.c_uint(raw)
            api(_hwnd(window), attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (OSError, AttributeError, tk.TclError):
        pass


def center_window(window, owner, width, height):
    owner.update_idletasks()
    left, top, right, bottom = work_area(owner)
    # Leave room for the native caption, border and the taskbar.
    width = min(width, max(320, right - left - 40))
    height = min(height, max(240, bottom - top - 82))
    minimum = window.minsize()
    window.minsize(min(minimum[0], width), min(minimum[1], height))
    if owner.winfo_ismapped() and owner.state() != "iconic":
        x = owner.winfo_rootx() + (owner.winfo_width() - width) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - height) // 2 - 16
    else:
        x, y = left + (right - left - width) // 2, top + (bottom - top - height) // 2 - 16
    x = max(left + 16, min(x, right - width - 16))
    y = max(top + 12, min(y, bottom - height - 48))
    # Tk's negative geometry offsets mean distance from the right/bottom. Set an
    # absolute native position for monitors to the left or above the primary one.
    window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
    window.update_idletasks()
    window.deiconify()
    if sys.platform == "win32":
        try:
            api = ctypes.WinDLL("user32").SetWindowPos
            api.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            api.restype = wintypes.BOOL
            api(_hwnd(window), None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010)
        except (OSError, AttributeError, tk.TclError):
            pass
    decorate(window)
    window.lift()


def prepare_window(window, owner, title, size=(780, 640), minimum=(520, 360), escape=False, on_show=None):
    window.withdraw()
    window.title(title + tr(' · 拾光'))
    window.configure(bg=P["bg"])
    window.transient(owner)
    window.minsize(*minimum)
    try:
        from app_config import program_dir
        icon = program_dir() / "shiguang.ico"
        if icon.exists():
            window.iconbitmap(str(icon))
    except tk.TclError:
        pass
    if escape:
        window.bind("<Escape>", lambda event: window.destroy())
    def show():
        if not window.winfo_exists() or not owner.winfo_exists():
            return
        center_window(window, owner, *size)
        if on_show:
            on_show()
    window.after_idle(show)
    return window


def new_window(owner, title, size=(780, 640), **kwargs):
    return prepare_window(tk.Toplevel(owner), owner, title, size, **kwargs)


class SoftButton(tk.Frame):
    """Rounded surface around a real Tk button, retaining keyboard activation."""
    def __init__(self, parent, text, command, primary=False, **kwargs):
        self.fill = kwargs.pop("bg", P["green"] if primary else P["soft"])
        self.foreground = kwargs.pop("fg", "#FFFFFF" if primary else P["ink"])
        self.label_text = text
        self.padx, self.pady = kwargs.pop("padx", 14), kwargs.pop("pady", 9)
        self.minimum_chars = kwargs.pop("width", 0)
        self.font = tkfont.Font(font=kwargs.pop("font", (FONT, 10)))
        self.hovered, self.focused = False, False
        self.state_value = kwargs.pop("state", "normal")
        super().__init__(parent, bg=parent.cget("bg"), borderwidth=0, highlightthickness=0)
        self.pack_propagate(False)
        self.surface = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.surface.place(x=0, y=0, relwidth=1, relheight=1)
        self.native = tk.Button(self, text=text, command=command, font=self.font, relief="flat", bd=0,
                                highlightthickness=0, takefocus=True, cursor="hand2", padx=0, pady=0,
                                state=self.state_value, **kwargs)
        self.native.place(x=8, y=3, relwidth=1, width=-16, relheight=1, height=-6)
        self.bind("<Configure>", lambda event: self._paint())
        for widget in (self.surface, self.native):
            widget.bind("<Enter>", lambda event: self._hover(True))
            widget.bind("<Leave>", lambda event: self._hover(False))
        self.surface.bind("<Button-1>", lambda event: self.native.invoke())
        self.native.bind("<FocusIn>", lambda event: self._focus(True))
        self.native.bind("<FocusOut>", lambda event: self._focus(False))
        self.native.bind("<Return>", lambda event: self.native.invoke())
        self._size()
        self._paint()

    def _size(self):
        width = max(self.font.measure(self.label_text), self.font.measure("0") * self.minimum_chars) + 2 * self.padx
        super().configure(width=width, height=self.font.metrics("linespace") + 2 * self.pady)

    def _hover(self, value):
        self.hovered = value
        self._paint()

    def _focus(self, value):
        self.focused = value
        self._paint()

    def _paint(self):
        if not hasattr(self, "native"):
            return
        disabled = self.state_value == "disabled"
        fill = P["soft"] if disabled else self.fill
        if self.hovered and not disabled:
            fill = "#245A46" if self.foreground in {"white", "#FFFFFF"} else P["pale"]
        foreground = P["muted"] if disabled else self.foreground
        self.native.configure(bg=fill, fg=foreground, activebackground=fill, activeforeground=foreground,
                              disabledforeground=P["muted"], cursor="arrow" if disabled else "hand2")
        self.surface.configure(cursor="arrow" if disabled else "hand2")
        width, height = max(self.winfo_width(), self.winfo_reqwidth()), max(self.winfo_height(), self.winfo_reqheight())
        radius = 11
        self.surface.delete("all")
        self.surface.create_polygon(2 + radius, 2, width - 2 - radius, 2, width - 2, 2,
                                    width - 2, 2 + radius, width - 2, height - 2 - radius,
                                    width - 2, height - 2, width - 2 - radius, height - 2,
                                    2 + radius, height - 2, 2, height - 2, 2, height - 2 - radius,
                                    2, 2 + radius, 2, 2, smooth=True, splinesteps=24, fill=fill,
                                    outline=P["green"] if self.focused and not disabled else fill,
                                    width=2 if self.focused and not disabled else 1)

    def configure(self, cnf=None, **kwargs):
        if not hasattr(self, "native"):
            return super().configure(cnf, **kwargs)
        if isinstance(cnf, dict):
            kwargs.update(cnf)
        if not kwargs:
            return self.native.configure(cnf)
        if "text" in kwargs:
            self.label_text = kwargs.pop("text")
            self.native.configure(text=self.label_text)
            self._size()
        if "bg" in kwargs:
            self.fill = kwargs.pop("bg")
        if "fg" in kwargs:
            self.foreground = kwargs.pop("fg")
        if "state" in kwargs:
            self.state_value = kwargs["state"]
        if kwargs:
            self.native.configure(**kwargs)
        self._paint()

    config = configure

    def focus_set(self):
        self.native.focus_set()


class SlimScrollbar(tk.Canvas):
    """Quiet, rounded vertical scrollbar with dragging and keyboard support."""
    def __init__(self, parent, command, orient="vertical", **kwargs):
        super().__init__(parent, width=12, height=1, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, takefocus=0, **kwargs)
        self.command = command
        self.first, self.last = 0.0, 1.0
        self.hovered = False
        self.drag_offset = None
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda event: self._draw())
        self.bind("<FocusOut>", lambda event: self._draw())
        self.bind("<MouseWheel>", self._wheel)
        for key, count, unit in (("Up", -1, "units"), ("Down", 1, "units"),
                                 ("Prior", -1, "pages"), ("Next", 1, "pages")):
            self.bind("<" + key + ">", lambda event, n=count, u=unit: self._scroll(n, u))
        self.bind("<Home>", lambda event: self._move(0))
        self.bind("<End>", lambda event: self._move(1))

    def set(self, first, last):
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self.configure(takefocus=int(self.last - self.first < .999))
        self._draw()

    def _geometry(self):
        track = max(1, self.winfo_height() - 12)
        visible = self.last - self.first
        thumb = min(track, max(28, track * visible))
        travel = max(0, track - thumb)
        top = 6 + travel * self.first / max(.0001, 1 - visible)
        return top, thumb, travel, visible

    def _draw(self):
        self.delete("all")
        if self.last - self.first >= .999:
            self.configure(cursor="arrow")
            return
        self.configure(cursor="hand2")
        top, thumb, _, _ = self._geometry()
        active = self.hovered or self.drag_offset is not None or self.focus_get() == self
        width = 7 if active else 5
        self.create_line(6, top + width / 2, 6, top + thumb - width / 2,
                         width=width, fill="#829D8E" if active else "#CCD8CE", capstyle="round")

    def _hover(self, value):
        self.hovered = value
        self._draw()

    def _press(self, event):
        if self.last - self.first >= .999:
            return "break"
        self.focus_set()
        top, thumb, _, _ = self._geometry()
        self.drag_offset = event.y - top if top <= event.y <= top + thumb else thumb / 2
        self._drag(event)
        return "break"

    def _drag(self, event):
        if self.drag_offset is not None:
            _, _, travel, visible = self._geometry()
            fraction = max(0, min(1, (event.y - 6 - self.drag_offset) / max(1, travel)))
            self.command("moveto", fraction * (1 - visible))
            self._draw()
        return "break"

    def _release(self, event):
        self.drag_offset = None
        self._draw()
        return "break"

    def _scroll(self, count, unit):
        self.command("scroll", count, unit)
        return "break"

    def _move(self, fraction):
        self.command("moveto", fraction)
        return "break"

    def _wheel(self, event):
        return self._scroll(-int(event.delta / 120) or (-1 if event.delta > 0 else 1), "units")


class ScrollPane(tk.Frame):
    def __init__(self, parent, bg=None, bind_wheel=False):
        super().__init__(parent, bg=bg or P["paper"])
        self.canvas = tk.Canvas(self, bg=self.cget("bg"), highlightthickness=0, bd=0, width=1, height=1)
        self.bar = SlimScrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._scrollbar)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=self.cget("bg"))
        self.slot = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.slot, width=event.width))
        if bind_wheel:
            self.winfo_toplevel().bind("<MouseWheel>", self.wheel, add="+")

    def _scrollbar(self, first, last):
        self.bar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.bar.pack_forget()
        elif not self.bar.winfo_manager():
            self.bar.pack(side="right", fill="y")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()

    def wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget and str(widget).startswith(str(self)):
            if self.inner.winfo_reqheight() > self.canvas.winfo_height():
                self.canvas.yview_scroll(-int(event.delta / 120), "units")
            return "break"


def heading(parent, title, subtitle="", eyebrow=None):
    box = tk.Frame(parent, bg=P["bg"], padx=28, pady=22)
    box.pack(fill="x")
    if eyebrow:
        tk.Label(box, text=eyebrow, font=(FONT, 9), fg=P["green"], bg=P["bg"]).pack(anchor="w", pady=(0, 7))
    tk.Label(box, text=title, font=(FONT, 22, "bold"), fg=P["ink"], bg=P["bg"]).pack(anchor="w")
    if subtitle:
        description = tk.Label(box, text=subtitle, font=(FONT, 10), fg=P["muted"], bg=P["bg"], justify="left", anchor="w")
        description.pack(fill="x", pady=(8, 0))
        description.bind("<Configure>", lambda event: description.configure(wraplength=max(140, event.width)))
    return box


def empty_state(parent, title, description, command=None, action_text=None):
    box = tk.Frame(parent, bg=parent.cget("bg"), pady=26)
    box.pack(fill="both", expand=True)
    drawing = tk.Canvas(box, width=124, height=94, bg=box.cget("bg"), highlightthickness=0)
    drawing.pack(pady=(6, 16))
    drawing.create_oval(19, 3, 105, 89, fill=P["pale"], outline="")
    drawing.create_rectangle(39, 17, 88, 75, fill=P["paper"], outline="#B9CEBD", width=2)
    for y in (32, 44, 56):
        drawing.create_line(49, y, 76, y, fill="#BDCEC0", width=2)
    drawing.create_oval(72, 56, 98, 82, fill=P["green"], outline="")
    drawing.create_line(78, 68, 83, 73, 92, 64, fill="white", width=2)
    tk.Label(box, text=title, font=(FONT, 16, "bold"), bg=box.cget("bg"), fg=P["ink"]).pack(pady=(0, 8))
    tk.Label(box, text=description, font=(FONT, 10), bg=box.cget("bg"), fg=P["muted"], wraplength=480, justify="center").pack(padx=20)
    if command:
        SoftButton(box, action_text, command, True).pack(pady=(22, 6))
    return box


def install_styles(app):
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TEntry", fieldbackground=P["paper"], bordercolor=P["line"], lightcolor=P["line"], darkcolor=P["line"], padding=9)
    style.map("TEntry", bordercolor=[("focus", P["green"])])
    style.configure("TCombobox", padding=8, fieldbackground=P["paper"], background=P["soft"], bordercolor=P["line"], arrowsize=13)
    style.map("TCombobox", fieldbackground=[("readonly", P["paper"])], selectbackground=[("readonly", P["paper"])], selectforeground=[("readonly", P["ink"])])
    style.configure("Treeview", font=(FONT, 10), rowheight=42, background=P["paper"], fieldbackground=P["paper"], foreground=P["ink"], borderwidth=0)
    style.configure("Treeview.Heading", font=(FONT, 9, "bold"), background=P["soft"], foreground=P["muted"], relief="flat", padding=(12, 12))
    style.map("Treeview", background=[("selected", P["pale"])], foreground=[("selected", P["green"])])
    style.configure("Vertical.TScrollbar", background="#D9E2D8", troughcolor=P["bg"], borderwidth=0, arrowsize=10, relief="flat")
