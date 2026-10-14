"""Search defaults to recent attachments; files open only via explicit buttons."""
from datetime import date
import tkinter as tk
from tkinter import ttk

from chat_keys import ime_composing
from localization import tr
from ui_design import P, FONT, SoftButton, SlimScrollbar, new_window, heading


class SearchBrowser:
    def __init__(self, features):
        self.features = features
        self.top = top = new_window(features.app, tr('搜索日记与文件'), (900, 680))
        top.bind('<Escape>', lambda event: top.destroy())
        heading(top, tr('搜索日记与文件'), tr('默认列出全部附件，由近到远。输入关键词可搜索日记、待办与文件。'))
        row = tk.Frame(top, bg=P['bg'])
        row.pack(fill='x', padx=24, pady=(0, 12))
        self.query = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.query, font=(FONT, 11))
        entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        SoftButton(row, tr('搜索'), self.submit, True).pack(side='right')
        entry.bind('<Return>', lambda event: None if ime_composing(entry) else (self.submit(), 'break')[-1])
        footer = tk.Frame(top, bg=P['bg'], padx=24, pady=14)
        footer.pack(side='bottom', fill='x')
        self.summary = tk.StringVar()
        description = tk.Label(footer, textvariable=self.summary, bg=P['bg'], fg=P['muted'],
                               font=(FONT, 9), anchor='w', justify='left', wraplength=780)
        description.pack(fill='x', pady=(0, 10))
        description.bind('<Configure>', lambda event: description.configure(wraplength=max(120, event.width)))
        actions = tk.Frame(footer, bg=P['bg'])
        actions.pack(fill='x')
        self.open_button = SoftButton(actions, tr('打开文件'), self.open_selected, True, state='disabled')
        self.open_button.pack(side='left')
        self.details = SoftButton(actions, tr('日期与详情'), self.edit_selected, state='disabled')
        self.details.pack(side='left', padx=8)
        self.next = SoftButton(actions, tr('下一页'), lambda: self.page(1))
        self.next.pack(side='right')
        self.prev = SoftButton(actions, tr('上一页'), lambda: self.page(-1))
        self.prev.pack(side='right', padx=8)
        panel = tk.Frame(top, bg=P['paper'])
        panel.pack(fill='both', expand=True, padx=24)
        self.tree = ttk.Treeview(panel, columns=('kind', 'day', 'title'), show='headings', selectmode='browse')
        for key, name, width in (('kind', tr('类型'), 70), ('day', tr('日期'), 140), ('title', tr('内容'), 540)):
            self.tree.heading(key, text=name)
            self.tree.column(key, width=width, minwidth=60, stretch=key == 'title')
        bar = SlimScrollbar(panel, command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        # Selecting or double-clicking a title never opens an external file.
        self.rows, self.revision, self.offset = {}, 0, 0
        self.browsing, self.active_query, self.total = True, '', 0
        self.reload()
        entry.focus_set()

    def selected(self):
        selection = self.tree.selection()
        return self.rows.get(selection[0]) if selection else None

    def select(self, event=None):
        item = self.selected()
        attachment = item and item['kind'] == '附件'
        self.open_button.configure(text=tr('打开文件') if not item or attachment else tr('查看记录'), state='normal' if item else 'disabled')
        self.details.configure(state='normal' if attachment else 'disabled')
        if item:
            self.summary.set(item.get('snippet', ''))

    def open_selected(self):
        item = self.selected()
        if not item:
            return
        if item['kind'] == '附件':
            self.features.open_attachment(item['id'])
            return
        app = self.features.app
        if app.select_day(date.fromisoformat(item['day'])):
            app.switch_tab('tasks' if item['kind'] == '待办' else 'note')
            if item['kind'] == '归档':
                app.show_history()
            else:
                app.lift()

    def edit_selected(self):
        item = self.selected()
        if item and item['kind'] == '附件':
            self.features.edit_attachment(item['id'])

    def show_all(self):
        self.query.set('')
        self.submit()

    def submit(self):
        value = self.query.get().strip()
        self.browsing = value.casefold() in {'', '全部附件', '所有附件', '全部文件', '全部檔案', '所有檔案', 'all files', 'all attachments'}
        self.active_query, self.offset = value, 0
        self.reload()

    def page(self, step):
        if self.browsing:
            self.offset = max(0, self.offset + step * 50)
            self.reload()

    def reload(self):
        self.revision += 1
        number, browsing, offset = self.revision, self.browsing, self.offset
        self.rows.clear()
        self.tree.delete(*self.tree.get_children())
        self.select()
        self.prev.configure(state='disabled')
        self.next.configure(state='disabled')
        self.summary.set(tr('正在检索本机档案……'))
        def current():
            return self.top.winfo_exists() and self.revision == number
        def failure(message):
            if current():
                self.summary.set(message)
        def done(result):
            if not current():
                return
            if browsing:
                values, total = result
                self.total = total
                records = []
                for item in values:
                    spans = [a if a == b else a + ' → ' + b for a, b in item['dates'][:4]]
                    records.append(dict(id=item['id'], kind='附件', day=item['created_at'][:10], title=item['title'],
                                        snippet=item['original_name'] + ' · ' + tr('关联日期：{0}', ' · '.join(spans))))
                self.summary.set(tr('全部附件 · 共 {0} 个 · 按上传时间由近到远 · 第 {1} 页', total, offset // 50 + 1))
                self.prev.configure(state='normal' if offset else 'disabled')
                self.next.configure(state='normal' if offset + 50 < total else 'disabled')
            else:
                records = result
                self.summary.set(tr('找到 {0} 条结果，选中后使用下方按钮查看。', len(records)) if records else tr('没有找到；可以换个描述，或补充附件的备注。'))
            for item in records:
                self.rows[item['id']] = item
                self.tree.insert('', 'end', iid=item['id'], values=(tr(item['kind']), item['day'], item['title']))
        query = self.active_query
        if browsing:
            self.features.run(lambda store: store.attachment_page(offset=offset), done, failure)
        else:
            self.features.run(lambda store: store.search(query), done, failure)
