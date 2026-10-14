"""Readable, size-aware day previews for the offline month view."""
import tkinter as tk
from tkinter import font as tkfont

from localization import tr, get_language, day_title
from ui_design import FONT, P, work_area
from holiday_calendar import holiday_info


def one_line(value, limit=240):
    text = " ".join(str(value or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def day_preview(tasks, note, files):
    """Keep the next tasks first, while allowing journal and file previews."""
    task_rows = []
    for task in tasks:
        title = one_line(task["title"])
        timing = task["at_time"] or tr("全天")
        if task["done"]:
            text, color = tr("已完成：{0}", timing + " " + title), P["muted"]
        else:
            text = timing + " " + title
            color = P["orange"] if task["priority"] else P["green"]
        task_rows.append((text, color, "tasks", None))
    extras = []
    if note:
        extras.append((tr("日记：{0}", one_line(note, 160)), P["ink"], "note", None))
    file_rows = [(tr("附件：{0}", one_line(f["title"] or f["original_name"])),
                  P["green"], "files", f['id']) for f in files]
    return task_rows[:2] + extras + file_rows[:1] + task_rows[2:] + file_rows[1:]


class CalendarDayCell(tk.Canvas):
    """A reusable day cell. Resizing only repaints, never queries the database."""
    def __init__(self, parent, command):
        super().__init__(parent, width=1, height=1, highlightthickness=0,
                         borderwidth=0, cursor="hand2", takefocus=True)
        self.command = command
        self.day = None
        self.rows = []
        self.hit_targets = []
        self.selected = self.current = self.is_today = False
        self.signature = None
        self.tip = self.tip_job = None
        self.day_font = tkfont.Font(self, family=FONT, size=10, weight="bold")
        self.row_font = tkfont.Font(self, family=FONT, size=9)
        self.small_font = tkfont.Font(self, family=FONT, size=8)
        self.bind("<Configure>", lambda event: self.paint())
        self.bind("<Button-1>", self.choose)
        self.bind("<Return>", self.choose)
        self.bind("<space>", self.choose)
        self.bind("<Enter>", self.schedule_tip)
        self.bind("<Leave>", self.hide_tip)
        self.bind("<Escape>", self.hide_tip)
        self.bind("<FocusIn>", lambda event: self.paint())
        self.bind("<FocusOut>", lambda event: self.paint())
        self.bind("<Destroy>", self.hide_tip)

    def update_day(self, day, rows, selected, current, is_today):
        signature = (day, tuple(rows), selected, current, is_today, get_language())
        if signature == self.signature:
            return
        self.hide_tip()
        self.signature = signature
        self.day, self.rows = day, rows
        self.selected, self.current, self.is_today = selected, current, is_today
        self.paint()

    @staticmethod
    def fit(text, width, font):
        if width <= 0:
            return ""
        if font.measure(text) <= width:
            return text
        if font.measure("…") > width:
            return ""
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if font.measure(text[:middle] + "…") <= width:
                low = middle
            else:
                high = middle - 1
        return text[:low] + "…"

    def paint(self):
        if self.day is None:
            return
        width, height = self.winfo_width(), self.winfo_height()
        if width < 8 or height < 8:
            return
        bg = P["pale"] if self.selected else P["paper"] if self.current else "#F7F9F5"
        self.configure(bg=bg)
        self.delete("all")
        self.hit_targets = []
        if self.selected or self.focus_get() is self:
            self.create_rectangle(1, 1, width - 2, height - 2, outline=P["green"], width=2)
        padding = 7
        number_color = P["green"] if self.is_today else P["ink"] if self.current else P["muted"]
        self.create_text(padding, 7, anchor="nw", text=str(self.day.day),
                         font=self.day_font, fill=number_color)
        holiday_right = width - padding
        if self.is_today:
            badge = tr("今天")
            badge_width = self.small_font.measure(badge) + 8
            left = width - padding - badge_width
            if left > padding + self.day_font.measure(str(self.day.day)) + 3:
                holiday_right = left - 4
                badge_height = self.small_font.metrics("linespace") + 3
                self.create_rectangle(left, 6, width - padding, 6 + badge_height,
                                      fill=P["green"], outline="")
                self.create_text(left + 4, 7, anchor="nw", text=badge,
                                 font=self.small_font, fill="white")
            else:
                self.create_line(padding, 5, width - padding, 5, fill=P["green"], width=3)
        holiday = holiday_info(self.day)
        if holiday:
            holiday_left = padding + self.day_font.measure(str(self.day.day)) + 6
            available = holiday_right - holiday_left
            holiday_text = holiday['label']
            if self.small_font.measure(holiday_text) > available and holiday['marker']:
                holiday_text = holiday['marker']
            self.create_text(holiday_left, 8, anchor='nw', text=self.fit(holiday_text, available, self.small_font),
                             font=self.small_font, fill=P['red'] if holiday['status'] == 'rest' else P['orange'])
        top = self.day_font.metrics("linespace") + 14
        row_height = self.row_font.metrics("linespace") + 4
        capacity = max(0, (height - top - 5) // row_height)
        file_count = sum(row[2] == 'files' for row in self.rows)
        if file_count and capacity >= 2:
            # Keep a visible attachment entry even when task rows fill the day.
            footer_height = self.small_font.metrics('linespace') + 8
            footer_y = height - footer_height
            self.create_text(padding, footer_y + 2, anchor='nw',
                             text=self.fit(tr('附件 {0}', file_count), width - 2 * padding, self.small_font),
                             font=self.small_font, fill=P['green'])
            self.hit_targets.append((0, footer_y, width, height, 'files', None))
            capacity = max(0, (footer_y - top - 3) // row_height)
        if not capacity or not self.rows:
            return
        # Keep actual content even in a short cell; overflow goes in the tooltip.
        overflow = len(self.rows) > capacity and capacity >= 2
        visible = min(len(self.rows), capacity - (1 if overflow else 0))
        for index, (text, color, kind, identifier) in enumerate(self.rows[:visible]):
            self.create_text(padding, top + index * row_height, anchor="nw",
                             text=self.fit(text, width - 2 * padding, self.row_font),
                             font=self.row_font, fill=color)
            self.hit_targets.append((0, top + index * row_height, width, top + (index + 1) * row_height, kind, identifier))
        if overflow:
            text = tr("还有 {0} 项", len(self.rows) - visible)
            self.create_text(padding, top + visible * row_height, anchor="nw",
                             text=self.fit(text, width - 2 * padding, self.small_font),
                             font=self.small_font, fill=P["muted"])

    def choose(self, event=None):
        self.hide_tip()
        if self.day is not None:
            # A note-only/file-only day opens the relevant content immediately.
            tab = self.rows[0][2] if self.rows else "tasks"
            identifier = None
            if event is not None and getattr(event, 'num', None) == 1:
                for left, top, right, bottom, target, key in self.hit_targets:
                    if left <= event.x < right and top <= event.y < bottom:
                        tab, identifier = target, key
                        break
            self.command(self.day, tab, identifier)
        return "break"

    def schedule_tip(self, event=None):
        self.hide_tip()
        if self.rows or (self.day and holiday_info(self.day)):
            self.tip_job = self.after(450, self.show_tip)

    def show_tip(self):
        self.tip_job = None
        holiday = holiday_info(self.day) if self.day else None
        if not self.winfo_exists() or (not self.rows and not holiday) or not self.winfo_ismapped():
            return
        tip = self.tip = tk.Toplevel(self)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.configure(bg=P["line"])
        panel = tk.Frame(tip, bg=P["paper"], padx=14, pady=12)
        panel.pack(padx=1, pady=1)
        tk.Label(panel, text=day_title(self.day), bg=P["paper"], fg=P["ink"],
                 font=(FONT, 11, "bold"), anchor="w").pack(fill="x", pady=(0, 7))
        if holiday:
            tk.Label(panel, text=holiday['description'], bg=P['paper'], fg=P['red'] if holiday['status'] == 'rest' else P['orange'],
                     font=(FONT, 10), anchor='w', justify='left', wraplength=300).pack(fill='x', pady=(0, 7))
        for text, color, _kind, _identifier in self.rows[:8]:
            tk.Label(panel, text=one_line(text, 180), wraplength=300, justify="left",
                     anchor="w", bg=P["paper"], fg=color,
                     font=(FONT, 10)).pack(fill="x", pady=2)
        hint = tr("点击日期查看详情")
        if len(self.rows) > 8:
            hint = tr("还有 {0} 项", len(self.rows) - 8) + " · " + hint
        tk.Label(panel, text=hint, bg=P["paper"], fg=P["muted"],
                 font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        tip.update_idletasks()
        left, top, right, bottom = work_area(self.winfo_toplevel())
        tw, th = tip.winfo_reqwidth(), tip.winfo_reqheight()
        x = self.winfo_rootx() + self.winfo_width() + 6
        if x + tw > right - 6:
            x = self.winfo_rootx() - tw - 6
        x = max(left + 6, min(x, right - tw - 6))
        y = max(top + 6, min(self.winfo_rooty(), bottom - th - 6))
        tip.geometry(f"{x:+d}{y:+d}")
        tip.deiconify()

    def hide_tip(self, event=None):
        if self.tip_job:
            try:
                self.after_cancel(self.tip_job)
            except tk.TclError:
                pass
            self.tip_job = None
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None
