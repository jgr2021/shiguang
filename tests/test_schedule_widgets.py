"""Calendar/time logic, without creating UI windows or using personal data."""
import ast
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schedule_widgets import calendar_cells, TimeField
from translations import ENGLISH, TRADITIONAL


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class ScheduleFields(unittest.TestCase):
    def test_month_includes_leap_day(self):
        cells = calendar_cells(2028, 2)
        self.assertEqual(len(cells), 42)
        self.assertIn(date(2028, 2, 29), cells)
        self.assertEqual(cells[0].weekday(), 0)

    def test_year_limits(self):
        self.assertIn(date.min, calendar_cells(1, 1))
        self.assertIn(date.max, calendar_cells(9999, 12))
        self.assertIn(None, calendar_cells(9999, 12))

    def test_year_transition(self):
        self.assertIn(date(2027, 1, 1), calendar_cells(2026, 12))

    def field(self, hour, minute):
        field = object.__new__(TimeField)
        field.hour, field.minute = hour, minute
        field.all_day, field.variable = Value(False), Value('')
        field.paint = lambda: None
        field.command = None
        return field

    def test_exact_minute_preserved(self):
        f = self.field(14, 31)
        f.update_value()
        self.assertEqual(f.variable.get(), '14:31')

    def test_all_day_remembers_previous_time(self):
        f = self.field(23, 59)
        f.all_day.set(True); f.update_value()
        self.assertEqual(f.variable.get(), '')
        f.all_day.set(False); f.update_value()
        self.assertEqual(f.variable.get(), '23:59')

    def test_midnight(self):
        f = self.field(0, 0)
        f.update_value()
        self.assertEqual(f.variable.get(), '00:00')

    def test_all_new_labels_translated(self):
        for name in ('schedule_widgets.py', 'attachment_widgets.py'):
            tree = ast.parse((ROOT / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr' and node.args and isinstance(node.args[0], ast.Constant):
                    for catalog in (ENGLISH, TRADITIONAL):
                        self.assertIn(node.args[0].value, catalog)


if __name__ == '__main__': unittest.main()
