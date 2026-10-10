import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attachment_widgets import LinkedDatePicker, merge_spans, split_tags

class DateInteractions(unittest.TestCase):
    def picker(self, spans=()):
        picker = object.__new__(LinkedDatePicker)
        picker.spans = merge_spans(spans)
        picker.mode = 'days'
        picker.anchor = None
        picker.month = date(2026, 10, 1)
        picker.render = lambda: None
        return picker

    def test_multi_day_toggle(self):
        p = self.picker([['2026-10-10', '2026-10-10']])
        p.choose(date(2026,10,12)); p.choose(date(2026,10,10))
        self.assertEqual(p.values(), [['2026-10-12','2026-10-12']])

    def test_remove_day_splits_range(self):
        p = self.picker([['2026-10-10', '2026-10-15']])
        p.choose(date(2026,10,12))
        self.assertEqual(p.values(), [['2026-10-10','2026-10-11'], ['2026-10-13','2026-10-15']])

    def test_cross_month_and_year_range(self):
        p = self.picker()
        p.set_mode('range'); p.choose(date(2026,12,30)); p.choose(date(2027,1,3))
        self.assertEqual(p.values(), [['2026-12-30','2027-01-03']])

    def test_reverse_range(self):
        p = self.picker()
        p.set_mode('range'); p.choose(date(2026,10,15)); p.choose(date(2026,10,11))
        self.assertEqual(p.values(), [['2026-10-11','2026-10-15']])

    def test_merge_overlap_and_neighbors(self):
        p = self.picker([['2026-10-10','2026-10-12'], ['2026-10-12','2026-10-14'], ['2026-10-15','2026-10-16']])
        self.assertEqual(p.values(), [['2026-10-10','2026-10-16']])

    def test_pending_range_cannot_save(self):
        p = self.picker([['2026-10-10','2026-10-10']])
        p.set_mode('range'); p.choose(date(2026,10,12))
        with self.assertRaises(ValueError): p.values()

    def test_empty_selection_cannot_save(self):
        p = self.picker([['2026-10-10','2026-10-10']])
        p.choose(date(2026,10,10))
        with self.assertRaises(ValueError): p.values()

    def test_year_limits(self):
        p = self.picker([['0001-01-01','9999-12-31']])
        p.choose(date.min); p.choose(date.max)
        self.assertEqual(p.values(), [['0001-01-02','9999-12-30']])

    def test_month_shortcut_and_remove(self):
        p = self.picker(); p.month = date(2028,2,1)
        p.shortcut('month')
        self.assertEqual(p.values(), [['2028-02-01','2028-02-29']])
        p.remove(date(2028,2,1), date(2028,2,29))
        self.assertEqual(p.spans, [])

    def test_tag_compatibility(self):
        self.assertEqual(split_tags('学习，生活; research notes、学习'), ['学习','生活','research notes'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
