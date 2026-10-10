"""Shared point-and-click date and time fields for tasks and AI drafts."""
from datetime import date, datetime, timedelta
import tkinter as tk

from diary import TZ
from localization import tr, day_title, month_title
from ui_design import P, FONT, SoftButton, new_window


def current_day():
    return datetime.now(TZ).date()


def calendar_cells(year, month):
    first = date(year, month, 1)
    start = first.toordinal() - first.weekday()
    return [date.fromordinal(n) if 1 <= n <= date.max.toordinal() else None
            for n in range(start, start + 42)]


class DateField(tk.Frame):
    def __init__(self, parent, variable, command=None):
        super().__init__(parent, bg=parent.cget('bg'))
        self.variable, self.command = variable, command
        self.popup = None
        self.button = SoftButton(self, '', self.open, padx=12, pady=8)
        self.button.pack(fill='x')
        self.trace = variable.trace_add('write', self.refresh)
        self.bind('<Destroy>', self.cleanup, add='+')
        self.refresh()

    def refresh(self, *args):
        try:
            value = date.fromisoformat(self.variable.get())
            text = str(value.year) + ' · ' + day_title(value)
        except ValueError:
            text = tr('选择日期')
        self.button.configure(text=text + '  ▾')

    def cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove('write', self.trace)

    def open(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.lift()
            return
        owner = self.winfo_toplevel()
        previous_grab = owner.grab_current()
        try:
            chosen = date.fromisoformat(self.variable.get())
        except ValueError:
            chosen = current_day()
        top = self.popup = new_window(owner, tr('选择日期'), (400, 432), minimum=(380, 410))
        top.resizable(False, False)
        showing = [chosen.year, chosen.month]

        def close(event=None):
            top.destroy()
            self.popup = None
            if previous_grab and previous_grab.winfo_exists():
                previous_grab.grab_set()
            if self.winfo_exists():
                self.button.focus_set()
            return 'break'

        def pick(value):
            self.variable.set(value.isoformat())
            close()
            if self.command:
                self.command()

        body = tk.Frame(top, bg=P['paper'], padx=18, pady=16)
        body.pack(fill='both', expand=True, padx=12, pady=12)
        header = tk.Frame(body, bg=P['paper'])
        header.pack(fill='x', pady=(0, 8))
        caption = tk.Label(header, text='', bg=P['paper'], fg=P['ink'], font=(FONT, 12, 'bold'))
        caption.pack(side='left', expand=True)
        grid = tk.Frame(body, bg=P['paper'])
        grid.pack(fill='both', expand=True)
        for col, text in enumerate(('一', '二', '三', '四', '五', '六', '日')):
            grid.columnconfigure(col, weight=1, uniform='days')
            tk.Label(grid, text=tr('周' + text), font=(FONT, 9), bg=P['paper'], fg=P['muted']).grid(row=0, column=col, pady=(0, 6))
        buttons = []

        def render():
            caption.configure(text=month_title(date(*showing, 1)))
            prev.configure(state='disabled' if showing == [1, 1] else 'normal')
            nxt.configure(state='disabled' if showing == [9999, 12] else 'normal')
            for b in buttons:
                b.destroy()
            buttons.clear()
            for i, value in enumerate(calendar_cells(*showing)):
                selected = value == chosen
                b = SoftButton(grid, str(value.day) if value else '', lambda d=value: pick(d),
                               bg=P['green'] if selected else P['pale'] if value == current_day() else P['paper'],
                               fg='white' if selected else P['ink'] if value and value.month == showing[1] else P['muted'],
                               font=(FONT, 10), padx=0, pady=6)
                if value is None:
                    b.configure(state='disabled')
                b.grid(row=i // 7 + 1, column=i % 7, sticky='nsew', padx=1, pady=1)
                grid.rowconfigure(i // 7 + 1, weight=1)
                buttons.append(b)

        def shift(step):
            index = (showing[0] - 1) * 12 + showing[1] - 1 + step
            if 0 <= index < 9999 * 12:
                showing[:] = [index // 12 + 1, index % 12 + 1]
                render()

        prev = SoftButton(header, '‹', lambda: shift(-1), padx=10, pady=3)
        prev.pack(side='left', padx=(0, 5))
        nxt = SoftButton(header, '›', lambda: shift(1), padx=10, pady=3)
        nxt.pack(side='left')
        shortcuts = tk.Frame(body, bg=P['paper'])
        shortcuts.pack(fill='x', pady=(12, 0))
        SoftButton(shortcuts, tr('今天'), lambda: pick(current_day()), padx=12, pady=6).pack(side='left')
        SoftButton(shortcuts, tr('明天'), lambda: pick(current_day() + timedelta(days=1)), padx=12, pady=6).pack(side='left', padx=8)
        SoftButton(shortcuts, tr('取消'), close, padx=12, pady=6).pack(side='right')
        top.protocol('WM_DELETE_WINDOW', close)
        top.bind('<Escape>', close)
        top.bind('<Control-Return>', lambda e: 'break')
        render()
        def focus():
            if top.winfo_exists():
                top.grab_set()
                buttons[next(i for i,d in enumerate(calendar_cells(*showing)) if d == chosen)].native.focus_set()
        top.after_idle(focus)


class TimeField(tk.Frame):
    """A compact field opening a clock panel; no formatting or long dropdowns."""
    def __init__(self, parent, variable, command=None):
        super().__init__(parent, bg=parent.cget('bg'))
        self.variable, self.command = variable, command
        value = variable.get()
        hour, minute = value.split(':') if value else ('09', '00')
        self.all_day = tk.BooleanVar(value=not value)
        self.hour, self.minute = int(hour), int(minute)
        self.popup = None
        tk.Checkbutton(self, text=tr('全天'), variable=self.all_day, command=self.update_value,
                       bg=self.cget('bg'), activebackground=self.cget('bg'), fg=P['ink'],
                       font=(FONT, 10), padx=0).pack(side='left', padx=(0, 10))
        self.button = SoftButton(self, '', self.open, padx=14, pady=8)
        self.button.pack(side='left', fill='x', expand=True)
        self.paint()

    def paint(self):
        self.button.configure(text=(tr('选择时间') if self.all_day.get() else f'{self.hour:02}:{self.minute:02}') + '  ▾')

    def update_value(self, event=None):
        self.variable.set('' if self.all_day.get() else f'{self.hour:02}:{self.minute:02}')
        self.paint()
        if self.command:
            self.command()

    def open(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.lift()
            return
        owner = self.winfo_toplevel()
        previous_grab = owner.grab_current()
        top = self.popup = new_window(owner, tr('选择时间'), (420, 530), minimum=(400, 510))
        top.resizable(False, False)
        selected = [self.hour, self.minute]

        def close(event=None):
            top.destroy()
            self.popup = None
            if previous_grab and previous_grab.winfo_exists():
                previous_grab.grab_set()
            if self.winfo_exists():
                self.button.native.focus_set()
            return 'break'

        def confirm(event=None):
            self.hour, self.minute = selected
            self.all_day.set(False)
            self.update_value()
            return close()

        footer = tk.Frame(top, bg=P['bg'], padx=22, pady=14)
        footer.pack(side='bottom', fill='x')
        SoftButton(footer, tr('确定'), confirm, True).pack(side='right')
        SoftButton(footer, tr('取消'), close).pack(side='right', padx=10)
        body = tk.Frame(top, bg=P['paper'], padx=20, pady=14)
        body.pack(fill='both', expand=True, padx=14, pady=(14, 0))
        preview = tk.Label(body, font=(FONT, 26, 'bold'), fg=P['green'], bg=P['paper'])
        preview.pack(fill='x', pady=(0, 12))
        choices = []

        def paint():
            preview.configure(text=f'{selected[0]:02}:{selected[1]:02}')
            for button, part, value in choices:
                active = selected[part] == value
                button.configure(bg=P['green'] if active else P['soft'], fg='white' if active else P['ink'])

        def choose(part, value):
            selected[part] = value
            paint()

        for part, title, values in ((0, tr('小时'), range(24)), (1, tr('分钟'), range(0, 60, 5))):
            tk.Label(body, text=title, font=(FONT, 9), bg=P['paper'], fg=P['muted']).pack(anchor='w', pady=(6, 4))
            grid = tk.Frame(body, bg=P['paper'])
            grid.pack(fill='x')
            for col in range(6):
                grid.columnconfigure(col, weight=1, uniform='clock')
            for i, value in enumerate(values):
                button = SoftButton(grid, f'{value:02}', lambda p=part, v=value: choose(p, v), padx=5, pady=5)
                button.grid(row=i // 6, column=i % 6, sticky='ew', padx=2, pady=2)
                choices.append((button, part, value))
        fine = tk.Frame(body, bg=P['paper'])
        fine.pack(fill='x', pady=(10, 0))
        SoftButton(fine, '−', lambda: choose(1, (selected[1] - 1) % 60), padx=14, pady=4).pack(side='left')
        tk.Label(fine, text=tr('微调 1 分钟'), font=(FONT, 9), bg=P['paper'], fg=P['muted']).pack(side='left', expand=True)
        SoftButton(fine, '+', lambda: choose(1, (selected[1] + 1) % 60), padx=14, pady=4).pack(side='right')
        paint()
        top.protocol('WM_DELETE_WINDOW', close)
        top.bind('<Escape>', close)
        top.bind('<Control-Return>', confirm)
        def focus():
            if top.winfo_exists():
                top.grab_set()
                choices[selected[0]][0].native.focus_set()
        top.after_idle(focus)
