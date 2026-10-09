"""Editable, explicit confirmation for AI-generated calendar drafts."""
from datetime import date
import tkinter as tk
from tkinter import ttk
from calendar_plans import get_plan, pending_plans, apply_plan, dismiss_plan, update_plan
from diary import require
from localization import tr
from ui_design import P, FONT, SoftButton, ScrollPane, new_window, heading, empty_state


class PlanReview:
    def __init__(self, features, identifier):
        self.features, self.store, self.identifier = features, features.app.store, identifier
        plan = get_plan(self.store, identifier)
        require(plan['status'] == 'pending', tr('这份草案已关闭，请重新生成。'))
        self.top = top = new_window(features.app, tr('确认日程草案'), (880, 770), minimum=(740, 540))
        heading(top, tr('把想法安排进日历'), tr('可以改日期、时间和内容。只写入勾选项；未勾选项不加入日历。'), tr('日程草稿'))
        footer = tk.Frame(top, bg=P['bg'], padx=24, pady=16)
        footer.pack(side='bottom', fill='x')
        self.status = tk.StringVar(value=tr('尚未写入日历。时间留空表示全天事项。'))
        tk.Label(footer, textvariable=self.status, font=(FONT, 10), fg=P['green'], bg=P['bg'], wraplength=780, justify='left', anchor='w').pack(fill='x', pady=(0, 12))
        buttons = tk.Frame(footer, bg=P['bg'])
        buttons.pack(fill='x')
        SoftButton(buttons, tr('保存草稿，稍后确认'), self.later).pack(side='left')
        self.confirm = SoftButton(buttons, tr('确认写入日历'), self.apply, True)
        self.confirm.pack(side='right')
        SoftButton(buttons, tr('放弃草案'), self.dismiss).pack(side='right', padx=10)
        pane = ScrollPane(top, bg=P['bg'], bind_wheel=True)
        pane.pack(fill='both', expand=True, padx=24)
        self.rows = []
        for i, task in enumerate(plan['tasks']):
            box = tk.Frame(pane.inner, bg=P['paper'], padx=18, pady=14, highlightbackground=P['line'], highlightthickness=1)
            box.pack(fill='x', pady=(0, 12))
            active, priority = tk.BooleanVar(value=True), tk.BooleanVar(value=bool(task['priority']))
            values = {k: tk.StringVar(value=task[k]) for k in ('day', 'at_time', 'title')}
            line = tk.Frame(box, bg=P['paper'])
            line.pack(fill='x')
            tk.Checkbutton(line, text=tr('加入日历'), variable=active, bg=P['paper'], fg=P['green'], font=(FONT, 10), command=self.summary).pack(side='left')
            tk.Checkbutton(line, text=tr('重要'), variable=priority, bg=P['paper'], font=(FONT, 10)).pack(side='right')
            ttk.Entry(box, textvariable=values['title'], font=(FONT, 12)).pack(fill='x', pady=(8, 10))
            details = tk.Frame(box, bg=P['paper'])
            details.pack(fill='x')
            for key, title, width in (('day', tr('日期'), 14), ('at_time', tr('时间（可留空）'), 10)):
                tk.Label(details, text=title, bg=P['paper'], fg=P['muted'], font=(FONT, 9)).pack(side='left', padx=(0, 8))
                entry = ttk.Entry(details, textvariable=values[key], width=width, font=(FONT, 10))
                entry.pack(side='left', padx=(0, 18))
                entry.bind('<FocusOut>', lambda event: self.summary())
            tk.Label(box, text=tr('备注'), bg=P['paper'], fg=P['muted'], font=(FONT, 9), anchor='w').pack(fill='x', pady=(10, 4))
            notes = tk.Text(box, height=2, font=(FONT, 10), wrap='word', relief='flat', bg=P['bg'], padx=8, pady=6)
            notes.insert('1.0', task['notes'])
            notes.pack(fill='x')
            self.rows.append((active, priority, values, notes))
        top.protocol('WM_DELETE_WINDOW', self.later)
        self.summary()

    def collect(self, selected=True):
        return [dict(day=v['day'].get(), title=v['title'].get(), at_time=v['at_time'].get(), priority=int(priority.get()), notes=notes.get('1.0', 'end-1c'))
                for active, priority, v, notes in self.rows if active.get() or not selected]

    def summary(self):
        chosen = self.collect()
        self.confirm.configure(state='normal' if chosen else 'disabled')
        existing = self.store.tasks()
        seen, overlaps = set(), 0
        for task in chosen:
            key = (task['day'].strip(), task['at_time'].strip())
            if key[1] and (key in seen or any((r['day'], r['at_time']) == key and not r['done'] for r in existing)):
                overlaps += 1
            seen.add(key)
        self.status.set(tr('已选择 {0} 条，确认前不会写入。', len(chosen)) + (tr('其中 {0} 条与已有安排或草案时间相同，请先核对。', overlaps) if overlaps else ''))

    def later(self):
        try:
            update_plan(self.store, self.identifier, self.collect(False))
            self.top.destroy()
        except Exception as error:
            self.status.set(str(error))

    def dismiss(self):
        dismiss_plan(self.store, self.identifier)
        self.top.destroy()
        self.features.refresh_plans()

    def apply(self):
        self.confirm.configure(state='disabled')
        try:
            result = apply_plan(self.store, self.identifier, self.collect())
            message = tr('已写入 {0} 条待办；跳过 {1} 条相同日期、时间和标题的重复项。', len(result['created_ids']), result['skipped'])
            self.store.add_chat('assistant', message)
            if self.features.chat_window and self.features.chat_window.winfo_exists():
                self.features.chat_append(tr('日历'), message)
            self.top.destroy()
            if result['created_ids']:
                task = self.store.task(result['created_ids'][0])
                self.features.app.select_day(date.fromisoformat(task['day']))
                self.features.app.switch_tab('tasks')
            self.features.app.refresh()
            self.features.app.notice(message)
            self.features.refresh_plans()
        except Exception as error:
            self.status.set(str(error))
            self.confirm.configure(state='normal')


def open_plan(features, identifier):
    reviews = getattr(features, 'plan_reviews', {})
    existing = reviews.get(identifier)
    if existing and existing.top.winfo_exists():
        existing.top.lift()
        return existing
    review = PlanReview(features, identifier)
    reviews[identifier] = review
    features.plan_reviews = reviews
    return review


def show_plans(features):
    old = getattr(features, 'plans_window', None)
    if old and old.winfo_exists():
        old.destroy()
    top = features.plans_window = new_window(features.app, tr('日程草稿'), (780, 590))
    heading(top, tr('待确认的日程'), tr('草稿保存在本机，重开软件后可以继续处理。'), tr('拾光助手'))
    pane = ScrollPane(top, bg=P['bg'], bind_wheel=True)
    pane.pack(fill='both', expand=True, padx=24, pady=(0, 24))
    rows = pending_plans(features.app.store)
    if not rows:
        empty_state(pane.inner, tr('还没有日程草稿'), tr('在拾光助手里点击「帮我安排日程」，说出想做的事和日期。'))
    for row in rows:
        box = tk.Frame(pane.inner, bg=P['paper'], padx=18, pady=16)
        box.pack(fill='x', pady=(0, 12))
        tk.Label(box, text=row['question'][:200], font=(FONT, 11), bg=P['paper'], fg=P['ink'], wraplength=620, justify='left', anchor='w').pack(fill='x')
        tk.Label(box, text=row['created_at'][:16].replace('T', ' '), font=(FONT, 9), bg=P['paper'], fg=P['muted']).pack(anchor='w', pady=6)
        SoftButton(box, tr('查看并编辑'), lambda i=row['id']: (top.destroy(), open_plan(features, i))).pack(anchor='e')
