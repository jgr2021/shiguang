"""Point-and-click tags and linked dates, fully local and keyboard accessible."""
import calendar
from datetime import date, datetime, timedelta
import re
import tkinter as tk
from tkinter import ttk

from diary import TZ
from localization import tr, day_title, month_title
from ui_design import P, FONT, SoftButton


def split_tags(value):
    return list(dict.fromkeys(tag.strip() for tag in re.split(r"[,，;；、\n]+", value) if tag.strip()))


class ChipFlow(tk.Frame):
    """Reflow real buttons without discarding focus on resize."""
    def __init__(self, parent):
        super().__init__(parent, bg=parent.cget("bg"))
        self.buttons = []
        self.bind("<Configure>", self._layout)

    def _layout(self, event=None):
        width = max(100, self.winfo_width())
        x = y = row_height = 0
        for button in self.buttons:
            w, h = min(width, button.winfo_reqwidth()), button.winfo_reqheight()
            if x and x + w > width:
                x, y, row_height = 0, y + row_height + 6, 0
            button.place(x=x, y=y, width=w, height=h)
            x += w + 6
            row_height = max(row_height, h)
        self.configure(height=max(1, y + row_height))

    def clear(self):
        for button in self.buttons:
            button.destroy()
        self.buttons = []


class TagPicker(tk.Frame):
    def __init__(self, parent, value="", suggestions=()):
        super().__init__(parent, bg=parent.cget("bg"))
        self.selected = split_tags(value)
        defaults = [tr(x) for x in ("工作", "学习", "生活", "旅行", "简历", "论文", "资料", "灵感")]
        self.options = list(dict.fromkeys(self.selected + list(suggestions) + defaults))
        self.flow = ChipFlow(self)
        self.flow.pack(fill="x", pady=(0, 10))
        self.chips = {}
        for tag in self.options:
            self._add_chip(tag)
        row = tk.Frame(self, bg=self.cget("bg"))
        row.pack(fill="x")
        self.custom = tk.StringVar()
        self.entry = ttk.Entry(row, textvariable=self.custom, font=(FONT, 10), width=12)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.entry.bind("<Return>", self._add_custom)
        SoftButton(row, tr("添加标签"), self._add_custom, padx=10, pady=7).pack(side="right")
        self.message = tk.Label(self, text=tr("点选即可，可多选或添加自己的标签。"),
                                bg=self.cget("bg"), fg=P["muted"], font=(FONT, 9), anchor="w", justify="left")
        self.message.pack(fill="x", pady=(6, 0))
        self.message.bind("<Configure>", lambda e: self.message.configure(wraplength=max(100, e.width)))

    def _add_chip(self, tag):
        button = SoftButton(self.flow, "", lambda key=tag: self.toggle(key), padx=11, pady=6, font=(FONT, 9))
        self.chips[tag] = button
        self.flow.buttons.append(button)
        self._paint(tag)
        self.flow.after_idle(self.flow._layout)

    def _paint(self, tag):
        selected = tag in self.selected
        label = tag if len(tag) <= 24 else tag[:23] + "…"
        self.chips[tag].configure(text=("✓ " if selected else "") + label,
                                  bg=P["green"] if selected else P["soft"],
                                  fg="white" if selected else P["ink"])

    def toggle(self, tag):
        if tag in self.selected:
            self.selected.remove(tag)
        else:
            self.selected.append(tag)
        self._paint(tag)
        self.flow._layout()

    def _add_custom(self, event=None):
        values = split_tags(self.custom.get())
        if any(len(tag) > 64 for tag in values):
            self.message.configure(text=tr("标签请保持在64字以内。"), fg=P["red"])
            return "break"
        for tag in values:
            known = next((existing for existing in self.chips if existing.casefold() == tag.casefold()), tag)
            if known not in self.selected:
                self.selected.append(known)
            if known not in self.chips:
                self._add_chip(known)
            else:
                self._paint(known)
        self.custom.set("")
        self.message.configure(text=tr("点选即可，可多选或添加自己的标签。"), fg=P["muted"])
        self.flow._layout()
        return "break"

    def value(self):
        # A typed tag is retained even if the user goes straight to Save.
        if self.custom.get().strip():
            if any(len(tag) > 64 for tag in split_tags(self.custom.get())):
                raise ValueError(tr("标签请保持在64字以内。"))
            self._add_custom()
        return ", ".join(self.selected)


def merge_spans(spans):
    result = []
    for start, end in sorted((date.fromisoformat(a), date.fromisoformat(b)) for a, b in spans):
        if start > end:
            raise ValueError(tr("日期范围无效。"))
        if result and start.toordinal() <= result[-1][1].toordinal() + 1:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


class LinkedDatePicker(tk.Frame):
    def __init__(self, parent, spans, initial_day):
        super().__init__(parent, bg=parent.cget("bg"))
        self.spans = merge_spans(spans)
        self.month = date.fromisoformat(spans[0][0]).replace(day=1) if spans else initial_day.replace(day=1)
        self.anchor = None
        self.mode = "days"
        self.initial_day = initial_day
        modes = tk.Frame(self, bg=self.cget("bg"))
        modes.pack(fill="x", pady=(0, 10))
        self.day_mode = SoftButton(modes, tr("点选日期"), lambda: self.set_mode("days"), pady=7)
        self.day_mode.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.range_mode = SoftButton(modes, tr("连续日期"), lambda: self.set_mode("range"), pady=7)
        self.range_mode.pack(side="left", fill="x", expand=True, padx=(4, 0))
        header = tk.Frame(self, bg=self.cget("bg"))
        header.pack(fill="x", pady=(0, 8))
        SoftButton(header, "‹", lambda: self.change_month(-1), padx=11, pady=5).pack(side="left")
        SoftButton(header, "›", lambda: self.change_month(1), padx=11, pady=5).pack(side="right")
        self.month_label = tk.Label(header, font=(FONT, 12, "bold"), bg=self.cget("bg"), fg=P["ink"])
        self.month_label.pack(fill="x", expand=True, pady=4)
        week = tk.Frame(self, bg=self.cget("bg"))
        week.pack(fill="x")
        for column, name in enumerate(("周一", "周二", "周三", "周四", "周五", "周六", "周日")):
            week.columnconfigure(column, weight=1, uniform="days")
            tk.Label(week, text=tr(name), bg=self.cget("bg"), fg=P["muted"], font=(FONT, 8)).grid(row=0, column=column, sticky="ew", pady=(0, 6))
        self.days = tk.Frame(self, bg=self.cget("bg"))
        self.days.pack(fill="x")
        self.day_buttons = []
        for i in range(42):
            self.days.columnconfigure(i % 7, weight=1, uniform="days")
            button = tk.Button(self.days, text="", command=lambda index=i: self.choose(self.visible_days[index]),
                               font=(FONT, 10), relief="flat", bd=0, highlightthickness=1,
                               highlightbackground=self.cget("bg"), highlightcolor=P["green"],
                               cursor="hand2", pady=3, takefocus=True)
            button.grid(row=i // 7, column=i % 7, sticky="nsew", padx=2, pady=2)
            button.bind("<Return>", lambda e, index=i: self.choose(self.visible_days[index]))
            self.day_buttons.append(button)
        self.hint = tk.Label(self, bg=self.cget("bg"), fg=P["muted"], font=(FONT, 9), justify="left", anchor="w")
        self.hint.pack(fill="x", pady=(8, 10))
        self.hint.bind("<Configure>", lambda e: self.hint.configure(wraplength=max(140, e.width)))
        shortcuts = tk.Frame(self, bg=self.cget("bg"))
        shortcuts.pack(fill="x", pady=(0, 12))
        for key, caption in (("today", "今天"), ("week", "本周"), ("month", "本月")):
            SoftButton(shortcuts, tr(caption), lambda k=key: self.shortcut(k), padx=11, pady=5, font=(FONT, 9)).pack(side="left", padx=(0, 5))
        self.summary = tk.Label(self, font=(FONT, 9, "bold"), bg=self.cget("bg"), fg=P["green"], anchor="w")
        self.summary.pack(fill="x", pady=(0, 6))
        self.selected_flow = ChipFlow(self)
        self.selected_flow.pack(fill="x")
        self.render()

    def set_mode(self, mode):
        self.mode, self.anchor = mode, None
        self.render()

    def change_month(self, offset):
        value = self.month.year * 12 + self.month.month - 1 + offset
        year, month = divmod(value, 12)
        if 1 <= year <= 9999:
            self.month = date(year, month + 1, 1)
            self.render()

    def choose(self, day):
        if day is None:
            return "break"
        if self.mode == "range":
            if self.anchor is None:
                self.anchor = day
            else:
                start, end = sorted((self.anchor, day))
                self._add(start, end)
                self.anchor = None
        else:
            existing = next(((a, b) for a, b in self.spans if a <= day <= b), None)
            if existing:
                a, b = existing
                self.spans.remove([a, b])
                if a < day:
                    self.spans.append([a, day - timedelta(days=1)])
                if day < b:
                    self.spans.append([day + timedelta(days=1), b])
                self.spans.sort()
            else:
                self._add(day, day)
        self.render()
        return "break"

    def _add(self, start, end):
        values = [[a.isoformat(), b.isoformat()] for a, b in self.spans]
        self.spans = merge_spans(values + [[start.isoformat(), end.isoformat()]])

    def shortcut(self, key):
        current = datetime.now(TZ).date()
        if key == "today":
            start = end = current
        elif key == "week":
            start = current - timedelta(days=current.weekday())
            end = start + timedelta(days=6)
        else:
            start = self.month
            end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        self.anchor = None
        self.month = start.replace(day=1)
        self._add(start, end)
        self.render()

    def remove(self, start, end):
        self.spans.remove([start, end])
        self.render()

    def values(self):
        if self.anchor is not None:
            raise ValueError(tr("请再点一个日期，完成这段日期选择。"))
        if not self.spans:
            raise ValueError(tr("请至少关联一天。"))
        return [[a.isoformat(), b.isoformat()] for a, b in self.spans]

    def render(self):
        self.month_label.configure(text=month_title(self.month))
        for mode, button in (("days", self.day_mode), ("range", self.range_mode)):
            active = self.mode == mode
            button.configure(bg=P["pale"] if active else P["soft"], fg=P["green"] if active else P["muted"])
        first = self.month.toordinal() - self.month.weekday()
        self.visible_days = [date.fromordinal(first + i) if 1 <= first + i <= date.max.toordinal() else None for i in range(42)]
        current = datetime.now(TZ).date()
        for day, button in zip(self.visible_days, self.day_buttons):
            if day is None:
                button.configure(text="", state="disabled", bg=self.cget("bg"), highlightbackground=self.cget("bg"))
                continue
            selected = day == self.anchor or any(a <= day <= b for a, b in self.spans)
            button.configure(text=str(day.day), state="normal", bg=P["green"] if selected else (P["soft"] if day.month == self.month.month else self.cget("bg")),
                             fg="white" if selected else (P["ink"] if day.month == self.month.month else "#AAB5AC"),
                             activebackground=P["pale"], activeforeground=P["green"],
                             highlightbackground=P["green"] if day == current else self.cget("bg"))
        if self.anchor is not None:
            hint = tr("已选开始：{0}，再点结束日期。", day_title(self.anchor))
        else:
            hint = tr("可选择多个日期，再点一次取消。") if self.mode == "days" else tr("先点开始，再点结束，可添加多段。")
        self.hint.configure(text=hint)
        self.summary.configure(text=tr("已关联 {0} 天", sum((b - a).days + 1 for a, b in self.spans)))
        self.selected_flow.clear()
        for a, b in self.spans:
            def label(day):
                return (str(day.year) + " · " if day.year != current.year else "") + day_title(day)
            caption = label(a) if a == b else label(a) + " – " + label(b)
            chip = SoftButton(self.selected_flow, caption + "  ×", lambda start=a, end=b: self.remove(start, end),
                              padx=10, pady=5, font=(FONT, 8), bg=P["pale"], fg=P["green"])
            self.selected_flow.buttons.append(chip)
        self.selected_flow.after_idle(self.selected_flow._layout)
