"""Readable attachment cards and a date-independent local file library."""
import tkinter as tk


from localization import tr

from ui_design import P, FONT, ScrollPane, SoftButton


def caption(parent, value, color=None, size=10):
    label = tk.Label(parent, text=value, anchor='w', justify='left', bg=parent.cget('bg'),
                     fg=color or P['ink'], font=(FONT, size), wraplength=240)
    label.pack(fill='x', pady=3)
    label.bind('<Configure>', lambda event: label.configure(wraplength=max(80, event.width)))
    return label


class AttachmentCards(ScrollPane):
    def __init__(self, parent, features):
        super().__init__(parent, bg=P['paper'], bind_wheel=True)
        self.features = features
        self.rows, self.cards = [], {}
        self.visible = 0
        self.more = None

    def show(self, rows):
        self.clear()
        self.canvas.yview_moveto(0)
        self.rows, self.cards, self.visible, self.more = list(rows), {}, 0, None
        if not rows:
            caption(self.inner, tr('这一天没有附件'), P['muted'])
        self.add_more()

    def add_more(self):
        if self.more:
            self.more.destroy()
            self.more = None
        for item in self.rows[self.visible:self.visible + 30]:
            identifier = item['id']
            card = tk.Frame(self.inner, bg=P['soft'], padx=12, pady=10)
            card.pack(fill='x', pady=(0, 9))
            self.cards[identifier] = card
            caption(card, item['title'], P['ink'], 11)
            size = f"{item['size'] / 1048576:.1f} MB" if item['size'] >= 1048576 else f"{max(1, item['size'] // 1024)} KB"
            detail = size + (' · ' + item['tags'] if item['tags'] else '')
            caption(card, detail, P['muted'], 9)
            if item['original_name'] != item['title']:
                caption(card, item['original_name'], P['muted'], 9)
            if 'dates' in item:
                spans = [a if a == b else a + ' → ' + b for a, b in item['dates'][:3]]
                caption(card, tr('关联日期：{0}', ' · '.join(spans)) + (tr('等 {0} 段', len(item['dates'])) if len(item['dates']) > 3 else ''), P['muted'], 9)
            controls = tk.Frame(card, bg=P['soft'])
            controls.pack(fill='x', pady=(7, 0))
            SoftButton(controls, tr('打开文件'), lambda key=identifier: self.features.open_attachment(key),
                       True, padx=10, pady=6).pack(side='left')
            SoftButton(controls, tr('日期与详情'), lambda key=identifier: self.features.edit_attachment(key),
                       padx=10, pady=6).pack(side='left', padx=(7, 0))
        self.visible = min(len(self.rows), self.visible + 30)
        if self.visible < len(self.rows):
            self.more = SoftButton(self.inner, tr('继续显示'), self.add_more)
            self.more.pack(fill='x', pady=8)

    def reveal(self, identifier):
        while identifier not in self.cards and self.visible < len(self.rows):
            self.add_more()
        card = self.cards.get(identifier)
        if card:
            card.configure(highlightthickness=1, highlightbackground=P['green'])
            self.update_idletasks()
            height = max(1, self.inner.winfo_reqheight())
            self.canvas.yview_moveto(card.winfo_y() / height)


