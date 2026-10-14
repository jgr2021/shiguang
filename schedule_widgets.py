"""Inline date and time controls shared by tasks and AI drafts."""
from datetime import date, datetime, timedelta
import tkinter as tk

from diary import TZ
from localization import tr, day_title, month_title, get_language
from ui_design import P, FONT, SoftButton, ScrollPane


def current_day():
    return datetime.now(TZ).date()


def calendar_cells(year, month):
    first = date(year, month, 1)
    start = first.toordinal() - first.weekday()
    return [date.fromordinal(n) if 1 <= n <= date.max.toordinal() else None
            for n in range(start, start + 42)]


class PickerPanel(tk.Frame):
    """An anchored layer in the existing window; never changes form geometry."""
    def __init__(self, anchor, on_close):
        self.owner = anchor.winfo_toplevel()
        previous = getattr(self.owner, '_schedule_picker', None)
        if previous:
            previous.close(False)
        super().__init__(self.owner, bg=P['paper'],
                         highlightbackground=P['line'], highlightthickness=1)
        self.scroller = ScrollPane(self, bg=P['paper'])
        self.scroller.pack(fill='both', expand=True)
        self.content = tk.Frame(self.scroller.inner, bg=P['paper'], padx=12, pady=12)
        self.content.pack(fill='x')
        self.anchor, self.on_close = anchor, on_close
        self.closed, self.handlers = False, []
        self.owner._schedule_picker = self
        self.bind('<Return>', lambda event: 'break')

    def show(self):
        self.owner.update_idletasks()
        width = min(max(320, self.content.winfo_reqwidth() + 14), self.owner.winfo_width() - 20)
        height = min(self.content.winfo_reqheight() + 2, self.owner.winfo_height() - 20)
        left = self.anchor.winfo_rootx() - self.owner.winfo_rootx()
        top = self.anchor.winfo_rooty() - self.owner.winfo_rooty()
        x = max(10, min(left, self.owner.winfo_width() - width - 10))
        y = top + self.anchor.winfo_height() + 5
        if y + height > self.owner.winfo_height() - 10:
            y = top - height - 5
        y = max(10, min(y, self.owner.winfo_height() - height - 10))
        self.place(x=x, y=y, width=width, height=height)
        self.lift()
        self.handlers = [('<Button-1>', self.owner.bind('<Button-1>', self.outside, add='+')),
                         ('<Configure>', self.owner.bind('<Configure>', self.resized, add='+')),
                         ('<MouseWheel>', self.owner.bind('<MouseWheel>', self.scroller.wheel, add='+'))]
        def keys(widget):
            widget.bind('<Escape>', lambda event: self.close(), add='+')
            for child in widget.winfo_children():
                keys(child)
        keys(self)
        self.focus_set()

    def outside(self, event):
        widget = str(event.widget)
        if not any(widget == str(parent) or widget.startswith(str(parent) + '.') for parent in (self, self.anchor)):
            self.close(False)

    def resized(self, event):
        if event.widget is self.owner:
            self.close(False)

    def close(self, restore_focus=True):
        if self.closed:
            return 'break'
        self.closed = True
        for sequence, handler in self.handlers:
            try:
                self.owner.unbind(sequence, handler)
            except tk.TclError:
                pass
        if getattr(self.owner, '_schedule_picker', None) is self:
            self.owner._schedule_picker = None
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.on_close()
        if restore_focus and self.anchor.winfo_exists():
            self.anchor.button.focus_set()
        return 'break'


class DateField(tk.Frame):
    def __init__(self, parent, variable, command=None):
        super().__init__(parent, bg=parent.cget('bg'))
        self.variable, self.command = variable, command
        self.destroying = False
        self.panel = None
        self.button = SoftButton(self, '', self.open, padx=10, pady=8)
        self.button.pack(fill='x')
        self.trace = variable.trace_add('write', self.refresh)
        self.bind('<Destroy>', self.cleanup, add='+')
        self.refresh()

    def refresh(self, *args):
        try:
            value = date.fromisoformat(self.variable.get())
            caption = str(value.year) + ' · ' + day_title(value)
        except ValueError:
            caption = tr('选择日期')
        self.button.configure(text=caption + ('  ▴' if self.panel else '  ▾'))

    def cleanup(self, event):
        if event.widget is self:
            self.destroying = True
            self.variable.trace_remove('write', self.trace)
            if self.panel:
                self.panel.close(False)

    def close(self, event=None):
        if self.panel:
            self.panel.close()
        return 'break'

    def closed(self):
        self.panel = None
        if not self.destroying and self.winfo_exists():
            self.refresh()

    def open(self):
        if self.panel:
            self.close()
            return
        try:
            chosen = date.fromisoformat(self.variable.get())
        except ValueError:
            chosen = current_day()
        self.panel = PickerPanel(self, self.closed)
        panel = self.panel.content
        self.refresh()
        showing = [chosen.year, chosen.month]
        header = tk.Frame(panel, bg=P['paper'])
        header.pack(fill='x', pady=(0, 5))
        caption = tk.Label(header, bg=P['paper'], fg=P['ink'], font=(FONT, 10, 'bold'))
        caption.pack(side='left', expand=True)
        grid = tk.Frame(panel, bg=P['paper'])
        grid.pack(fill='x')
        for col, name in enumerate(('一', '二', '三', '四', '五', '六', '日')):
            grid.columnconfigure(col, weight=1, uniform='days')
            value = ('M', 'T', 'W', 'T', 'F', 'S', 'S')[col] if get_language() == 'en' else name
            tk.Label(grid, text=value, bg=P['paper'], fg=P['muted'], font=(FONT, 8)).grid(row=0, column=col, pady=4)
        buttons = []

        def pick(value):
            self.variable.set(value.isoformat())
            self.close()
            if self.command:
                self.command()

        def render():
            caption.configure(text=month_title(date(*showing, 1)))
            prev.configure(state='disabled' if showing == [1, 1] else 'normal')
            nxt.configure(state='disabled' if showing == [9999, 12] else 'normal')
            for widget in buttons:
                widget.destroy()
            buttons.clear()
            for index, value in enumerate(calendar_cells(*showing)):
                button = SoftButton(grid, str(value.day) if value else '', lambda d=value: pick(d),
                                    bg=P['green'] if value == chosen else P['paper'],
                                    fg='white' if value == chosen else P['ink'] if value and value.month == showing[1] else P['muted'],
                                    font=(FONT, 9), padx=1, pady=4)
                if value is None:
                    button.configure(state='disabled')
                button.grid(row=index // 7 + 1, column=index % 7, sticky='ew', padx=1, pady=1)
                button.native.bind('<Escape>', self.close)
                buttons.append(button)

        def shift(step):
            index = (showing[0] - 1) * 12 + showing[1] - 1 + step
            if 0 <= index < 9999 * 12:
                showing[:] = [index // 12 + 1, index % 12 + 1]
                render()

        prev = SoftButton(header, '‹', lambda: shift(-1), padx=7, pady=2)
        prev.pack(side='left')
        nxt = SoftButton(header, '›', lambda: shift(1), padx=7, pady=2)
        nxt.pack(side='left')
        shortcuts = tk.Frame(panel, bg=P['paper'])
        shortcuts.pack(fill='x', pady=(6, 0))
        for title, command in ((tr('今天'), lambda: pick(current_day())),
                               (tr('明天'), lambda: pick(current_day() + timedelta(days=1))),
                               (tr('收起'), self.close)):
            SoftButton(shortcuts, title, command, font=(FONT, 9), padx=7, pady=4).pack(side='left', padx=1)
        render()
        self.panel.show()


class TimeField(tk.Frame):
    """One time button with a clock picker layered inside the current window."""
    def __init__(self, parent, variable, command=None):
        super().__init__(parent, bg=parent.cget('bg'))
        self.variable, self.command = variable, command
        self.destroying = False
        value = variable.get()
        self.hour, self.minute = map(int, value.split(':')) if value else (9, 0)
        self.all_day = tk.BooleanVar(value=not value)
        self.panel = None
        self.button = SoftButton(self, '', self.open, padx=12, pady=8)
        self.button.pack(fill='x')
        self.bind('<Destroy>', self.cleanup, add='+')
        self.paint()

    def paint(self):
        value = tr('全天') if self.all_day.get() else f'{self.hour:02}:{self.minute:02}'
        self.button.configure(text=value + ('  ▴' if self.panel else '  ▾'))

    def cleanup(self, event):
        if event.widget is self:
            self.destroying = True
            if self.panel:
                self.panel.close(False)

    def closed(self):
        self.panel = None
        if not self.destroying and self.winfo_exists():
            self.paint()

    def reset(self):
        if self.panel:
            self.panel.close(False)
        self.hour, self.minute = 9, 0
        self.all_day.set(True)
        self.update_value()

    def update_value(self):
        self.variable.set('' if self.all_day.get() else f'{self.hour:02}:{self.minute:02}')
        self.paint()
        if self.command:
            self.command()

    def open(self):
        if self.panel:
            self.panel.close()
            return
        self.panel = PickerPanel(self, self.closed)
        popup, body = self.panel, self.panel.content
        selected, part = [self.hour, self.minute], [0]
        preview = tk.Label(body, text='', bg=P['paper'], fg=P['green'], font=(FONT, 22, 'bold'))
        preview.pack(fill='x', pady=(0, 6))
        tabs = tk.Frame(body, bg=P['paper'])
        tabs.pack(fill='x', pady=(0, 8))
        grid = tk.Frame(body, bg=P['paper'])
        grid.pack(fill='x')
        for col in range(6):
            grid.columnconfigure(col, weight=1, uniform='clock')
        choices = []
        def commit(all_day=False):
            self.hour, self.minute = selected
            self.all_day.set(all_day)
            popup.close()
            self.update_value()

        def render():
            preview.configure(text=f'{selected[0]:02}:{selected[1]:02}')
            hours.configure(bg=P['pale'] if part[0] == 0 else P['paper'])
            minutes.configure(bg=P['pale'] if part[0] == 1 else P['paper'])
            for widget in choices:
                widget.destroy()
            choices.clear()
            values = range(24) if part[0] == 0 else range(0, 60, 5)
            for index, value in enumerate(values):
                active = selected[part[0]] == value
                control = SoftButton(grid, f'{value:02}', lambda n=value: pick(n),
                                     bg=P['green'] if active else P['soft'], fg='white' if active else P['ink'],
                                     font=(FONT, 10), padx=4, pady=5)
                control.grid(row=index // 6, column=index % 6, sticky='ew', padx=2, pady=2)
                control.native.bind('<Escape>', lambda event: popup.close())
                choices.append(control)

        def pick(value):
            selected[part[0]] = value
            if part[0] == 0:
                part[0] = 1
                render()
            else:
                commit()

        def switch(value):
            part[0] = value
            render()

        def fine(step):
            total = (selected[0] * 60 + selected[1] + step) % (24 * 60)
            selected[:] = [total // 60, total % 60]
            part[0] = 1
            render()

        hours = SoftButton(tabs, tr('小时'), lambda: switch(0), padx=10, pady=5)
        hours.pack(side='left', fill='x', expand=True)
        minutes = SoftButton(tabs, tr('分钟'), lambda: switch(1), padx=10, pady=5)
        minutes.pack(side='left', fill='x', expand=True)
        fine_row = tk.Frame(body, bg=P['paper'])
        fine_row.pack(fill='x', pady=(8, 0))
        SoftButton(fine_row, '−', lambda: fine(-1), padx=10, pady=4).pack(side='left')
        tk.Label(fine_row, text=tr('微调 1 分钟'), bg=P['paper'], fg=P['muted'], font=(FONT, 9)).pack(side='left', expand=True)
        SoftButton(fine_row, '+', lambda: fine(1), padx=10, pady=4).pack(side='right')
        footer = tk.Frame(body, bg=P['paper'])
        footer.pack(fill='x', pady=(10, 0))
        SoftButton(footer, tr('全天'), lambda: commit(True), padx=12, pady=5).pack(side='left')
        SoftButton(footer, tr('确定'), commit, True, padx=12, pady=5).pack(side='right')
        SoftButton(footer, tr('取消'), popup.close, padx=10, pady=5).pack(side='right', padx=6)
        render()
        self.paint()
        popup.show()
