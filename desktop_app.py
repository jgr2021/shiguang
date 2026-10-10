"""Shiguang: a fully local Tk desktop calendar. No network services required."""
from localization import tr, set_language, get_language, LANGUAGES, month_title, day_title
import argparse
from datetime import date, datetime, timedelta
import hashlib
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

from diary import TZ
from file_store import FileStore
from ui_extras import Features
from schedule_widgets import DateField, TimeField
from app_config import bootstrap, default_data_dir, program_dir
from ui_design import P, FONT, SoftButton, SlimScrollbar, ScrollPane, prepare_window, new_window, heading, empty_state, install_styles, decorate

WEEK = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def today():
    return datetime.now(TZ).date()


def label(parent, text="", size=10, color=None, bold=False, bg=None, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"), fg=color or P["ink"], bg=bg or parent.cget("bg"), **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    return SoftButton(parent, text, command, primary, **kwargs)


class ScrollFrame(ScrollPane):
    pass


class TaskDialog(tk.Toplevel):
    def __init__(self, app, task=None, owner=None, day=None):
        owner = owner or app
        super().__init__(owner)
        self.app, self.task = app, task
        prepare_window(self, owner, tr('编辑待办') if task else tr('安排一件事'), (610, 655), (500, 420),
                       on_show=lambda: (self.grab_set(), title_entry.focus_set()))
        heading(self, tr('编辑待办') if task else tr('安排一件事'), tr('给想做的事，留一个合适的位置。'), tr('日程安排'))
        controls = tk.Frame(self, bg=P["bg"], padx=28, pady=18)
        controls.pack(side="bottom", fill="x")
        pane = ScrollPane(self, bg=P["paper"], bind_wheel=True)
        pane.pack(fill="both", expand=True, padx=26)
        frame = tk.Frame(pane.inner, bg=P["paper"], padx=22, pady=20)
        frame.pack(fill="x")
        label(frame, tr('待办内容')).pack(anchor="w")
        self.title_var = tk.StringVar(value=task["title"] if task else app.quick_var.get())
        title_entry = ttk.Entry(frame, textvariable=self.title_var, width=46, font=(FONT, 11))
        title_entry.pack(fill="x", pady=(6, 14), ipady=5)
        dates = tk.Frame(frame, bg=P["paper"])
        dates.pack(fill="x")
        self.day_var = tk.StringVar(value=task["day"] if task else (day or app.selected).isoformat())
        self.time_var = tk.StringVar(value=task["at_time"] if task else "")
        for text, variable, widget, column in ((tr('日期'), self.day_var, DateField, 0), (tr('时间'), self.time_var, TimeField, 1)):
            area = tk.Frame(dates, bg=P["paper"])
            area.grid(row=0, column=column, sticky="ew", padx=(0, 12) if column == 0 else (0, 0))
            dates.columnconfigure(column, weight=1)
            label(area, text, 9, P["muted"]).pack(anchor="w")
            widget(area, variable).pack(fill="x", pady=(6, 12))
        self.priority_var = tk.IntVar(value=task["priority"] if task else 0)
        tk.Checkbutton(frame, text=tr('标为重要'), variable=self.priority_var, bg=P["paper"], fg=P["ink"], activebackground=P["paper"], font=(FONT, 10), anchor="w").pack(fill="x", pady=(0, 10))
        label(frame, tr('备注'), 10).pack(anchor="w")
        self.notes = tk.Text(frame, height=5, width=44, font=(FONT, 10), bg=P["soft"], fg=P["ink"], relief="flat", padx=10, pady=10, wrap="word", undo=True)
        self.notes.pack(fill="x", pady=(6, 18))
        if task:
            self.notes.insert("1.0", task["notes"])
        if task:
            button(controls, tr('删除'), self.remove, fg=P["red"]).pack(side="left")
        button(controls, tr('保存待办'), self.save, primary=True).pack(side="right")
        button(controls, tr('取消'), self.destroy).pack(side="right", padx=10)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Control-Return>", lambda event: self.save())

    def save(self):
        try:
            data = {"day": self.day_var.get().strip(), "title": self.title_var.get(), "at_time": self.time_var.get().strip(), "priority": self.priority_var.get(), "notes": self.notes.get("1.0", "end-1c"), "done": self.task["done"] if self.task else 0}
            self.app.store.save_task(data, self.task["id"] if self.task else None, self.task["version"] if self.task else None)
        except Exception as error:
            messagebox.showerror(tr('还没有保存'), str(error), parent=self)
            return
        if not self.task:
            self.app.quick_var.set("")
        self.app.refresh()
        self.app.notice(tr('待办已保存在本机'))
        self.destroy()

    def remove(self):
        if messagebox.askyesno(tr('删除待办'), tr('删除这条待办？\n\n') + self.task["title"], parent=self):
            try:
                self.app.store.delete_task(self.task["id"], self.task["version"])
            except Exception as error:
                messagebox.showerror(tr('未删除'), str(error), parent=self)
                return
            self.app.refresh()
            self.app.notice(tr('已删除待办'))
            self.destroy()


class PlannerApp(tk.Tk):
    def __init__(self, data_root, initial_language=None):
        super().__init__()
        self.title(tr('拾光日历'))
        self.configure(bg=P["bg"])
        self.geometry("%dx%d" % (min(1280, self.winfo_screenwidth() - 70), min(780, self.winfo_screenheight() - 155)))
        self.minsize(1000, 630)
        bootstrap(data_root)
        self.store = FileStore(data_root)
        if not self.store.setting("ui_language") and initial_language in LANGUAGES:
            self.store.set_setting("ui_language", initial_language)
        set_language(self.store.setting("ui_language", "zh-CN"))
        self.title(tr('拾光日历'))
        self.features = Features(self)
        self.calendar_cells = []
        self.task_signature = None
        self.last_today = today()
        self.data_version = self.store.db.execute("PRAGMA data_version").fetchone()[0]
        icon = program_dir() / "shiguang.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.selected = today()
        self.month = self.selected.replace(day=1)
        self.active_tab = "tasks"
        self.note_version = 0
        self.note_loaded = ""
        self.note_dirty = False
        self.save_job = None
        self.clock_job = None
        self.quick_var = tk.StringVar()
        install_styles(self)
        self.build()
        self.load_note()
        self.refresh()
        self.bind("<Control-n>", lambda event: self.open_editor())
        self.bind("<Control-s>", lambda event: self.save_note())
        self.bind("<Control-t>", lambda event: self.select_day(today()))
        self.bind("<Control-f>", lambda event: self.features.search())
        self.bind_all("<MouseWheel>", self.mousewheel, add="+")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.report_callback_exception = self.callback_error
        self.clock_job = self.after(30000, self.tick)
        self.after(350, self.features.welcome)
        self.after_idle(lambda: decorate(self))

    def build(self):
        header = tk.Frame(self, bg=P["bg"], padx=28, pady=16)
        header.pack(fill="x")
        mark = tk.Canvas(header, width=43, height=43, bg=P["bg"], highlightthickness=0)
        mark.create_rectangle(3, 3, 40, 40, fill=P["green"], outline="")
        mark.create_rectangle(11, 12, 32, 31, outline="#FFFFFF", width=2)
        mark.create_line(11, 18, 32, 18, fill="#FFFFFF", width=2)
        mark.create_line(16, 9, 16, 14, fill="#FFFFFF", width=2)
        mark.create_line(27, 9, 27, 14, fill="#FFFFFF", width=2)
        mark.create_oval(23, 23, 27, 27, fill="#DBEAC3", outline="")
        mark.pack(side="left", padx=(0, 12))
        names = tk.Frame(header, bg=P["bg"])
        names.pack(side="left")
        label(names, tr('拾光日历'), 20, bold=True).pack(anchor="w")
        label(names, tr('每天一点，慢慢向前。'), 9, P["muted"]).pack(anchor="w", pady=(3, 0))
        button(header, tr('设置'), self.features.settings).pack(side="right", padx=(0, 10))
        self.open_button = button(header, tr('所有待办'), self.all_tasks)
        self.open_button.pack(side="right", padx=(0, 10))
        button(header, tr('拾光助手'), self.features.chat, primary=True).pack(side="right", padx=(0, 10))
        button(header, tr('云文件'), self.features.cloud).pack(side="right", padx=(0, 10))
        button(header, tr('搜索'), self.features.search).pack(side="right", padx=(0, 10))
        body = tk.Frame(self, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        body.columnconfigure(0, weight=3, minsize=470)
        body.columnconfigure(1, weight=2, minsize=345)
        body.rowconfigure(0, weight=1)
        calendar_panel = tk.Frame(body, bg=P["paper"], padx=20, pady=20)
        calendar_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        month_header = tk.Frame(calendar_panel, bg=P["paper"])
        month_header.pack(fill="x", pady=(0, 18))
        self.month_label = label(month_header, size=18, bold=True)
        self.month_label.pack(side="left")
        self.today_button = button(month_header, tr('回到今天'), lambda: self.select_day(today()), primary=True)
        self.today_button.pack(side="right", padx=(8, 0))
        button(month_header, "›", lambda: self.change_month(1), width=2).pack(side="right", padx=(5, 0))
        button(month_header, "‹", lambda: self.change_month(-1), width=2).pack(side="right")
        headings = tk.Frame(calendar_panel, bg=P["paper"])
        headings.pack(fill="x", pady=(0, 9))
        for col, name in enumerate(WEEK):
            headings.columnconfigure(col, weight=1, uniform="week")
            label(headings, tr(name), 9, P["muted"]).grid(row=0, column=col, sticky="ew")
        self.calendar_grid = tk.Frame(calendar_panel, bg=P["line"])
        self.calendar_grid.pack(fill="both", expand=True)
        legend = tk.Frame(calendar_panel, bg=P["paper"])
        legend.pack(fill="x", pady=(15, 0))
        label(legend, tr('● 日记   ▣ 附件   ·  绿色标记为今天'), 9, P["muted"]).pack(side="left")
        self.month_count = label(legend, "", 9, P["green"])
        self.month_count.pack(side="right")
        self.detail = tk.Frame(body, bg=P["paper"], padx=22, pady=20)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.detail.configure(width=370)
        self.detail.pack_propagate(False)
        self.day_heading = label(self.detail, size=20, bold=True)
        self.day_heading.pack(anchor="w")
        self.day_description = label(self.detail, size=9, color=P["muted"])
        self.day_description.pack(anchor="w", pady=(5, 18))
        tabs = tk.Frame(self.detail, bg=P["paper"])
        tabs.pack(fill="x", pady=(0, 15))
        self.tab_tasks = button(tabs, tr('当天待办'), lambda: self.switch_tab("tasks"))
        self.tab_tasks.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.tab_note = button(tabs, tr('当天日记'), lambda: self.switch_tab("note"))
        self.tab_note.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.tab_files = button(tabs, tr('附件'), lambda: self.switch_tab("files"))
        self.tab_files.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.task_panel = tk.Frame(self.detail, bg=P["paper"])
        self.task_panel.pack(fill="both", expand=True)
        self.quick = ttk.Entry(self.task_panel, textvariable=self.quick_var, font=(FONT, 11))
        self.quick.pack(fill="x", ipady=4)
        self.quick.bind("<Return>", lambda event: self.quick_add())
        label(self.task_panel, tr('写下一件事，按 Enter 添加'), 9, P["muted"]).pack(anchor="w", pady=(6, 10))
        addrow = tk.Frame(self.task_panel, bg=P["paper"])
        addrow.pack(fill="x", pady=(0, 13))
        button(addrow, tr('+ 添加待办'), self.quick_add, primary=True).pack(side="left")
        button(addrow, tr('时间 / 备注'), self.open_editor).pack(side="left", padx=8)
        self.tasks_scroll = ScrollFrame(self.task_panel)
        self.tasks_scroll.pack(fill="both", expand=True)
        self.task_summary = label(self.task_panel, size=9, color=P["muted"])
        self.task_summary.pack(anchor="w", pady=(12, 0))
        self.overdue_button = button(self.task_panel, "", self.all_tasks)
        self.note_panel = tk.Frame(self.detail, bg=P["paper"])
        label(self.note_panel, tr('想法、进展、感受，都可以留在这里。'), 9, P["muted"]).pack(anchor="w", pady=(0, 10))
        text_area = tk.Frame(self.note_panel, bg=P["soft"])
        text_area.pack(fill="both", expand=True)
        self.note_text = tk.Text(text_area, wrap="word", font=(FONT, 11), bg=P["soft"], fg=P["ink"], insertbackground=P["green"], borderwidth=0, highlightthickness=0, padx=14, pady=14, undo=True, height=8)
        text_bar = SlimScrollbar(text_area, command=self.note_text.yview)
        self.note_text.configure(yscrollcommand=text_bar.set)
        self.note_text.pack(side="left", fill="both", expand=True)
        text_bar.pack(side="right", fill="y")
        self.note_text.bind("<<Modified>>", self.note_changed)
        self.note_status = label(self.note_panel, "", 9, P["muted"])
        self.note_status.pack(anchor="w", pady=(9, 10))
        self.features.build_files(self.detail)
        footer = tk.Frame(self, bg=P["bg"], padx=30, pady=10)
        footer.pack(fill="x")
        self.status = label(footer, tr('离线日历 · 所有记录保存在这台电脑'), 9, P["muted"])
        self.status.pack(side="left")
        label(footer, tr('Ctrl+N 新待办    Ctrl+S 保存日记    Ctrl+T 今天'), 9, P["muted"]).pack(side="right")
        self.paint_tabs()

    def notice(self, text, error=False):
        self.status.configure(text=text, fg=P["red"] if error else P["green"])

    def apply_language(self, code, source_window, reopen):
        if code not in LANGUAGES:
            return
        if self.features.ai or self.features.busy_count:
            messagebox.showinfo(tr('界面语言 / Language'), tr('请等待文件处理完成或停止助手后，再切换语言。'), parent=source_window)
            return
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel) and child is not source_window and child.state() != "withdrawn":
                messagebox.showinfo(tr('界面语言 / Language'), tr('请先关闭其他窗口，再切换语言，以保留正在编辑的内容。'), parent=source_window)
                return
        if not self.save_note():
            return
        self.store.set_setting("ui_language", code)
        if code == get_language():
            self.notice(tr('语言已切换并保存，下次打开会沿用。'))
            return
        active_tab = self.active_tab
        cursor, view = self.note_text.index("insert"), self.note_text.yview()[0]
        source_window.destroy()
        if self.features.chat_window and self.features.chat_window.winfo_exists():
            self.features.chat_window.destroy()
        self.features.chat_window = None
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                child.destroy()
        set_language(code)
        self.title(tr('拾光日历'))
        self.calendar_cells = []
        self.task_signature = None
        self.build()
        self.load_note()
        self.refresh()
        self.switch_tab(active_tab)
        self.note_text.mark_set("insert", cursor)
        self.note_text.yview_moveto(view)
        self.notice(tr('语言已切换并保存，下次打开会沿用。'))
        self.after_idle(reopen)

    def change_month(self, delta):
        index = self.month.year * 12 + self.month.month - 1 + delta
        if not 1 <= index // 12 <= 9998:
            return
        self.month = date(index // 12, index % 12 + 1, 1)
        self.render_calendar()

    def render_calendar(self):
        self.month_label.configure(text=month_title(self.month))
        start = self.month - timedelta(days=self.month.weekday())
        dates = [start + timedelta(days=n) for n in range(42)]
        tasks = self.store.tasks(dates[0].isoformat(), dates[-1].isoformat())
        notes = self.store.note_dates(dates[0].isoformat(), dates[-1].isoformat())
        files = self.store.file_dates(dates[0].isoformat(), dates[-1].isoformat())
        by_day = {}
        for task in tasks:
            by_day.setdefault(task["day"], []).append(task)
        actual_today = today()
        for col in range(7):
            self.calendar_grid.columnconfigure(col, weight=1, uniform="dates")
        for row in range(6):
            self.calendar_grid.rowconfigure(row, weight=1, uniform="dates", minsize=60)
        for index, day in enumerate(dates):
            selected, current = day == self.selected, day.month == self.month.month
            bg = P["pale"] if selected else P["paper"] if current else "#FAFBF8"
            if index >= len(self.calendar_cells):
                frame = tk.Frame(self.calendar_grid, padx=4, pady=4, highlightthickness=2, cursor="hand2")
                frame.grid(row=index // 7, column=index % 7, sticky="nsew", padx=1, pady=1)
                frame.pack_propagate(False)
                number = label(frame, size=10, anchor="w", width=1)
                number.pack(fill="x")
                count = label(frame, size=8, anchor="w", width=1)
                count.pack(fill="x", pady=(2, 0))
                marks = label(frame, size=8, anchor="w", width=1)
                marks.pack(fill="x")
                cell = {"frame": frame, "number": number, "count": count, "marks": marks, "day": day, "signature": None}
                for widget in (frame, number, count, marks):
                    widget.bind("<Button-1>", lambda event, chosen=cell: self.select_day(chosen["day"]))
                self.calendar_cells.append(cell)
            cell = self.calendar_cells[index]
            cell["day"] = day
            records = by_day.get(day.isoformat(), [])
            finished = sum(task["done"] for task in records)
            count_text = (tr('{0} 项', len(records)) + (f" · {finished} ✓" if finished else " ···")) if records else ""
            marks_text = ("● " if day.isoformat() in notes else "") + (f"▣ {files[day.isoformat()]}" if files.get(day.isoformat()) else "")
            signature = (day, selected, current, actual_today, count_text, marks_text)
            if cell["signature"] != signature:
                cell["signature"] = signature
                cell["frame"].configure(bg=bg, highlightbackground=P["green"] if selected else bg)
                cell["number"].configure(text=tr('{0} 今天', day.day) if day == actual_today else str(day.day), bg=P["green"] if day == actual_today else bg, fg="white" if day == actual_today else P["ink"] if current else "#B1B7B0", font=(FONT, 10, "bold" if selected or day == actual_today else "normal"))
                cell["count"].configure(text=count_text, bg=bg, fg=P["muted"] if records and finished == len(records) else P["green"])
                cell["marks"].configure(text=marks_text, bg=bg, fg=P["green"])
        current_tasks = [task for task in tasks if task["day"].startswith(self.month.strftime("%Y-%m"))]
        self.month_count.configure(text=tr('本月 {0} 件事', len(current_tasks)))

    def select_day(self, day):
        if not self.save_note():
            return
        self.selected = day
        self.month = day.replace(day=1)
        self.load_note()
        self.refresh()

    def refresh(self):
        self.render_calendar()
        self.day_heading.configure(text=day_title(self.selected))
        prefix = tr('今天 · ') if self.selected == today() else ""
        self.day_description.configure(text=prefix + tr(WEEK[self.selected.weekday()]) + f"  /  {self.selected.year}")
        self.render_tasks()
        self.features.render_files()
        total, overdue = self.store.db.execute("SELECT count(*),coalesce(sum(day<?),0) FROM planner_tasks WHERE done=0", (today().isoformat(),)).fetchone()
        self.open_button.configure(text=tr('所有待办  {0}', total))
        self.overdue_button.pack_forget()
        if overdue:
            self.overdue_button.configure(text=tr('另有 {0} 项过期待办  ›', overdue))
            self.overdue_button.pack(fill="x", pady=(12, 0))
        if hasattr(self, "all_window") and self.all_window.winfo_exists():
            self.render_all_tasks()

    def render_tasks(self):
        tasks = self.store.tasks(self.selected.isoformat(), self.selected.isoformat())
        signature = (self.selected, tuple((t["id"], t["version"]) for t in tasks))
        if self.task_signature == signature:
            return
        self.task_signature = signature
        self.tasks_scroll.clear()
        if not tasks:
            empty = tk.Frame(self.tasks_scroll.inner, bg=P["paper"], pady=32)
            empty.pack(fill="x")
            label(empty, tr('留一点空间给今天'), 14, P["green"], bold=True).pack(anchor="w")
            label(empty, tr('从一件小事开始安排。'), 10, P["muted"]).pack(anchor="w", pady=10)
        last_done = None
        for task in tasks:
            if last_done != task["done"]:
                label(self.tasks_scroll.inner, tr('已完成') if task["done"] else tr('等待完成'), 9, P["muted"]).pack(anchor="w", pady=(8, 6))
                last_done = task["done"]
            self.task_row(self.tasks_scroll.inner, task)
        completed = sum(task["done"] for task in tasks)
        self.task_summary.configure(text=tr('{0} / {1} 已完成', completed, len(tasks)) if tasks else '')

    def task_row(self, parent, task, show_date=False, card=False):
        row = tk.Frame(parent, bg=P["paper"], pady=13, padx=10 if card else 0,
                       highlightthickness=1 if card else 0, highlightbackground=P["line"])
        row.pack(fill="x", pady=(0, 9) if card else 0)
        check = tk.Button(row, text="✓" if task["done"] else "○", command=lambda: self.toggle(task), fg=P["green"] if task["done"] else P["muted"], bg=P["paper"], activebackground=P["pale"], borderwidth=0, font=(FONT, 17), width=2, cursor="hand2")
        check.pack(side="left", anchor="n")
        edit = tk.Button(row, text="···", command=lambda: self.open_editor(task, owner=parent.winfo_toplevel()), fg=P["muted"], bg=P["paper"], relief="flat", font=(FONT, 12), width=2, cursor="hand2")
        edit.pack(side="right", anchor="n")
        content = tk.Frame(row, bg=P["paper"])
        content.pack(side="left", fill="both", expand=True)
        title = label(content, task["title"], 11, P["muted"] if task["done"] else P["ink"], wraplength=245, justify="left", anchor="w")
        title.pack(fill="x")
        title.bind("<Configure>", lambda event, widget=title: widget.configure(wraplength=max(110, event.width)) if int(widget.cget("wraplength")) != max(110, event.width) else None)
        title.bind("<Double-Button-1>", lambda event: self.open_editor(task, owner=parent.winfo_toplevel()))
        metadata = []
        if show_date:
            metadata.append(task["day"])
        if task["at_time"]:
            metadata.append(task["at_time"])
        if task["priority"]:
            metadata.append(tr('重要'))
        if task["notes"]:
            metadata.append(tr('有备注'))
        if metadata:
            label(content, " · ".join(metadata), 9, P["orange"] if task["priority"] else P["muted"]).pack(anchor="w", pady=(4, 0))
        if not card:
            tk.Frame(parent, bg=P["line"], height=1).pack(fill="x")

    def toggle(self, task):
        try:
            self.store.toggle(task["id"], task["version"])
            self.refresh()
            self.notice(tr('已完成，做得不错。') if not task["done"] else tr('已恢复为待办'))
        except Exception as error:
            messagebox.showerror(tr('未能更新'), str(error), parent=self)
            self.refresh()

    def quick_add(self):
        if not self.quick_var.get().strip():
            self.quick.focus_set()
            self.notice(tr('先写下想做的事情'))
            return
        try:
            self.store.save_task({"day": self.selected.isoformat(), "title": self.quick_var.get()})
        except Exception as error:
            messagebox.showerror(tr('还没有保存'), str(error), parent=self)
            return
        self.quick_var.set("")
        self.refresh()
        self.quick.focus_set()
        self.notice(tr('待办已保存在本机'))

    def open_editor(self, task=None, owner=None, day=None):
        return TaskDialog(self, task, owner, day)

    def switch_tab(self, name):
        self.active_tab = name
        self.task_panel.pack_forget()
        self.note_panel.pack_forget()
        self.features.file_panel.pack_forget()
        {"tasks": self.task_panel, "note": self.note_panel, "files": self.features.file_panel}[name].pack(fill="both", expand=True)
        self.paint_tabs()
        if name == "note":
            self.note_text.focus_set()

    def paint_tabs(self):
        for name, widget in (("tasks", self.tab_tasks), ("note", self.tab_note), ("files", self.tab_files)):
            widget.configure(bg=P["pale"] if self.active_tab == name else P["soft"], fg=P["green"] if self.active_tab == name else P["muted"])

    def load_note(self):
        record = self.store.note(self.selected.isoformat())
        self.note_version, self.note_loaded = record["version"], record["body"]
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", record["body"])
        self.note_text.edit_reset()
        self.note_text.edit_modified(False)
        self.note_dirty = False
        self.note_status.configure(text=tr('已保存在本机') if record["body"] else tr('输入后自动保存'), fg=P["muted"])

    def note_changed(self, event=None):
        if not self.note_text.edit_modified():
            return
        self.note_text.edit_modified(False)
        self.note_dirty = self.note_text.get("1.0", "end-1c") != self.note_loaded
        if self.save_job:
            self.after_cancel(self.save_job)
        if self.note_dirty:
            self.note_status.configure(text=tr('正在保存……'), fg=P["muted"])
            self.save_job = self.after(600, lambda: self.save_note(quiet=True))

    def save_note(self, quiet=False):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        body = self.note_text.get("1.0", "end-1c")
        if body == self.note_loaded:
            return True
        try:
            record = self.store.save_note(self.selected.isoformat(), body, self.note_version)
        except Exception as error:
            self.note_status.configure(text=tr('保存失败，文字仍在编辑框中'), fg=P["red"])
            self.notice(tr('日记尚未保存，请保留当前文字'), error=True)
            if not quiet:
                messagebox.showerror(tr('日记尚未保存'), str(error), parent=self)
            return False
        self.note_version, self.note_loaded = record["version"], record["body"]
        self.note_dirty = False
        self.note_status.configure(text=tr('已保存 · ') + datetime.now(TZ).strftime("%H:%M"), fg=P["green"])
        self.notice(tr('日记已保存在本机'))
        self.render_calendar()
        return True

    def archive_note(self):
        if not self.save_note():
            return
        try:
            result = self.store.archive_note(self.selected.isoformat())
        except Exception as error:
            messagebox.showerror(tr('尚未归档'), str(error), parent=self)
            return
        self.refresh()
        self.notice(tr('这份原文已经归档，无需重复保存') if result["status"] == "duplicate" else tr('原文已保留到档案；可向拾光助手提问或复盘'))
        self.note_status.configure(text=tr('已归档 · ') + result["id"], fg=P["green"])

    def show_history(self):
        rows = self.store.archived_for_day(self.selected.isoformat())
        window = new_window(self, tr('历史记录'), (780, 680), escape=True)
        heading(window, tr('历史记录'), self.selected.isoformat(), tr('日记档案'))
        if not rows:
            empty_state(window, tr('这一天，还没有归档'), tr('输入后自动保存'))
            return
        pane = ScrollPane(window, bg=P["bg"], bind_wheel=True)
        pane.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        for row in rows:
            pending = row["desktop"] and not row["processed_at"]
            card = tk.Frame(pane.inner, bg=P["paper"], padx=22, pady=20)
            card.pack(fill="x", pady=(0, 14))
            label(card, row["created_at"] + (tr('  · 等待 Agent 整理') if pending else tr('  · 已归档')), 9, P["muted"]).pack(anchor="w", pady=(0, 14))
            content = tk.Text(card, font=(FONT, 11), wrap="word", relief="flat", height=12, bg=P["paper"], fg=P["ink"], spacing1=3, spacing3=6)
            bar = SlimScrollbar(card, command=content.yview)
            content.configure(yscrollcommand=bar.set)
            bar.pack(side="right", fill="y")
            content.pack(fill="both", expand=True)
            content.insert("1.0", row["raw_text"])
            content.configure(state="disabled")
            content.bind("<MouseWheel>", lambda event, editor=content: (editor.yview_scroll(-int(event.delta / 120), "units"), "break")[-1])

    def all_tasks(self):
        if hasattr(self, "all_window") and self.all_window.winfo_exists():
            self.all_window.lift()
            self.render_all_tasks()
            return
        self.all_window = new_window(self, tr('所有待办'), (840, 750), minimum=(690, 510), escape=True)
        banner = heading(self.all_window, tr('所有待办'), tr('把每一天的安排，放在一起慢慢理清。'), tr('日程总览'))
        button(banner, tr('+ 添加待办'), lambda: self.open_editor(owner=self.all_window, day=today()), True).place(relx=1, x=-28, y=36, anchor="ne")
        stats = tk.Frame(self.all_window, bg=P["bg"])
        stats.pack(fill="x", padx=28, pady=(0, 17))
        self.overview_stats = {}
        for column, (key, title, color) in enumerate((("today", tr('今天待办'), P["green"]), ("upcoming", tr('未来7天'), P["ink"]), ("overdue", tr('已过期'), P["orange"]))):
            stats.columnconfigure(column, weight=1, uniform="counts")
            card = tk.Frame(stats, bg=P["paper"], padx=18, pady=12)
            card.grid(row=0, column=column, sticky="ew", padx=(0, 10) if column < 2 else 0)
            value = label(card, "0", 23, color, bold=True)
            value.pack(anchor="w")
            label(card, title, 9, P["muted"]).pack(anchor="w", pady=(2, 0))
            self.overview_stats[key] = value
        filters = tk.Frame(self.all_window, bg=P["bg"])
        filters.pack(fill="x", padx=26, pady=(0, 12))
        self.overview_filter, self.overview_limit = "open", 50
        self.overview_filters = {}
        for key, title in (("open", tr('未完成')), ("today", tr('今天')), ("upcoming", tr('未来7天')), ("overdue", tr('已过期')), ("done", tr('已完成'))):
            control = button(filters, title, lambda selected=key: self.filter_tasks(selected))
            control.pack(side="left", padx=(0, 6))
            self.overview_filters[key] = control
        footer = tk.Frame(self.all_window, bg=P["bg"], padx=28, pady=14)
        footer.pack(side="bottom", fill="x")
        button(footer, tr('关闭'), self.all_window.destroy).pack(side="right")
        self.overview_count = label(footer, "", 9, P["muted"])
        self.overview_count.pack(side="left")
        self.all_scroll = ScrollFrame(self.all_window, bg=P["bg"])
        self.all_scroll.pack(fill="both", expand=True, padx=28)
        self.render_all_tasks()

    def filter_tasks(self, key):
        self.overview_filter, self.overview_limit = key, 50
        self.all_scroll.canvas.yview_moveto(0)
        self.render_all_tasks()

    def render_all_tasks(self):
        self.all_scroll.clear()
        records = self.store.tasks()
        current, end = today().isoformat(), (today() + timedelta(days=7)).isoformat()
        open_tasks = [task for task in records if not task["done"]]
        groups = {"open": open_tasks,
                  "today": [task for task in open_tasks if task["day"] == current],
                  "upcoming": [task for task in open_tasks if current < task["day"] <= end],
                  "overdue": [task for task in open_tasks if task["day"] < current],
                  "done": [task for task in records if task["done"]]}
        for key, label_widget in self.overview_stats.items():
            label_widget.configure(text=str(len(groups[key])))
        for key, control in self.overview_filters.items():
            selected = key == self.overview_filter
            control.configure(bg=P["green"] if selected else P["bg"], fg="white" if selected else P["muted"])
        tasks = groups[self.overview_filter]
        if self.overview_filter == "done":
            tasks = sorted(tasks, key=lambda task: task["day"], reverse=True)
        self.overview_count.configure(text=tr('显示 {0} / {1} 件事 · 双击标题可编辑', min(len(tasks), self.overview_limit), len(tasks)))
        if not tasks:
            title = tr('给接下来的日子，留一点期待') if not records else tr('这里暂时没有待办')
            description = tr('从一件小事开始，安排、记录，再慢慢完成。') if not records else tr('试试其他分类，或为今天安排一件新事情。')
            if self.overview_filter == "done":
                title, description = tr('完成的事，会留在这里'), tr('每一个完成的小步骤，都值得被记住。')
            empty_state(self.all_scroll.inner, title, description,
                        lambda: self.open_editor(owner=self.all_window, day=today()), tr('安排第一件事') if not records else tr('+ 添加待办'))
            return
        previous = None
        for task in tasks[:self.overview_limit]:
            if task["day"] != previous:
                day = date.fromisoformat(task["day"])
                line = tk.Frame(self.all_scroll.inner, bg=P["bg"])
                line.pack(fill="x", pady=(12, 9))
                description = tr('今天') if task["day"] == current else day_title(day)
                label(line, description, 11, P["ink"], bold=True).pack(side="left")
                label(line, "  ·  " + tr(WEEK[day.weekday()]) + "  /  " + str(day.year), 9, P["muted"]).pack(side="left")
                if task["day"] < current and not task["done"]:
                    label(line, tr('已过期'), 9, P["orange"]).pack(side="right")
                previous = task["day"]
            self.task_row(self.all_scroll.inner, task, card=True)
        if len(tasks) > self.overview_limit:
            def more():
                self.overview_limit += 50
                self.render_all_tasks()
            button(self.all_scroll.inner, tr('再显示50条'), more).pack(pady=12)

    def backup(self):
        if not self.save_note():
            return
        path = filedialog.asksaveasfilename(parent=self, title=tr('导出完整备份'), initialfile=tr('拾光备份-') + datetime.now(TZ).strftime("%Y%m%d-%H%M") + ".zip", defaultextension=".zip", filetypes=[(tr('ZIP 备份'), "*.zip")])
        if path:
            self.notice(tr('正在后台导出完整备份……'))
            self.features.run(lambda store: store.backup(path), lambda result: self.notice(tr('完整备份已导出（含附件与助手生成文档）')))

    def mousewheel(self, event):
        self.tasks_scroll.wheel(event)
        if hasattr(self, "all_window") and self.all_window.winfo_exists():
            self.all_scroll.wheel(event)

    def tick(self):
        version = self.store.db.execute("PRAGMA data_version").fetchone()[0]
        if version != self.data_version or self.last_today != today():
            self.data_version, self.last_today = version, today()
            if not self.note_dirty and self.store.note(self.selected.isoformat())["version"] != self.note_version:
                self.load_note()
            self.refresh()
        self.clock_job = self.after(30000, self.tick)

    def callback_error(self, kind, value, tb):
        log = self.store.root / "vault" / "desktop-error.log"
        with open(log, "a", encoding="utf-8") as handle:
            handle.write("".join(traceback.format_exception(kind, value, tb)))
        messagebox.showerror(tr('操作没有完成'), str(value) + tr('\n\n当前输入仍会保留，请重试。'), parent=self)

    def close(self):
        if self.features.busy_count:
            self.notice(tr('文件处理尚未结束，请稍候再关闭。'))
            return
        if not self.save_note():
            return
        if self.clock_job:
            self.after_cancel(self.clock_job)
        self.features.close()
        self.store.close()
        self.destroy()


def main():
    default_root = default_data_dir()
    parser = argparse.ArgumentParser(description="拾光离线日历")
    parser.add_argument("--data-dir", default=str(default_root))
    parser.add_argument("--language", choices=list(LANGUAGES), help="Initial language; existing user preference takes priority")
    args = parser.parse_args()
    # A per-folder mutex prevents accidental duplicate editors, without a network port.
    mutex = None
    if sys.platform == "win32":
        import ctypes
        signature = hashlib.sha256(str(Path(args.data_dir).resolve()).casefold().encode("utf-8")).hexdigest()[:24]
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        api.CreateMutexW.restype = ctypes.c_void_p
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = api.CreateMutexW(None, False, "Local\\Shiguang-" + signature)
        if ctypes.get_last_error() == 183:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(tr('拾光已打开'), tr('拾光日历已经在运行，请从任务栏切回应用。'), parent=root)
            root.destroy()
            api.CloseHandle(mutex)
            return
    try:
        app = PlannerApp(args.data_dir, args.language)
        app.mainloop()
    finally:
        if mutex is not None:
            api.CloseHandle(mutex)


if __name__ == "__main__":
    main()
