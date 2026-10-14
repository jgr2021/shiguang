"""Offline mainland China holiday arrangements, transcribed from official notices.

Source: State Council General Office, 国办发明电〔2025〕7号, 2025-11-04.
Checked 2026-10-11. Rest ranges include weekends and adjusted days off; they do
not claim that every day in a range is itself a statutory festival date.
Years not present here have no inferred rest or make-up work schedules.
"""
from datetime import date, timedelta
from localization import tr

SOURCE_URL = 'https://www.gov.cn/zhengce/zhengceku/202511/content_7047091.htm'
SUPPORTED_YEARS = (2026,)
_ARRANGEMENTS = (
    ('元旦', '2026-01-01', '2026-01-03', ('2026-01-04',)),
    ('春节', '2026-02-15', '2026-02-23', ('2026-02-14', '2026-02-28')),
    ('清明', '2026-04-04', '2026-04-06', ()),
    ('劳动节', '2026-05-01', '2026-05-05', ('2026-05-09',)),
    ('端午', '2026-06-19', '2026-06-21', ()),
    ('中秋', '2026-09-25', '2026-09-27', ()),
    ('国庆', '2026-10-01', '2026-10-07', ('2026-09-20', '2026-10-10')),
)
_DAYS = {}
for _name, _start, _end, _workdays in _ARRANGEMENTS:
    _first, _last = date.fromisoformat(_start), date.fromisoformat(_end)
    for _offset in range((_last - _first).days + 1):
        _DAYS[_first + timedelta(days=_offset)] = (_name, 'rest')
    for _value in _workdays:
        _DAYS[date.fromisoformat(_value)] = (_name, 'work')


def holiday_info(day):
    arrangement = _DAYS.get(day)
    if arrangement:
        name, status = arrangement
        marker = tr('休') if status == 'rest' else tr('班')
        return {'status': status, 'marker': marker,
                'label': tr(name) + '·' + marker,
                'description': tr('{0}假期 · 放假/调休', tr(name)) if status == 'rest' else tr('{0}调休 · 补班', tr(name))}
    # Fixed-date festival names are useful even without a published yearly plan.
    name = {(1, 1): '元旦', (5, 1): '劳动节', (10, 1): '国庆'}.get((day.month, day.day))
    if name:
        return {'status': 'festival', 'marker': '', 'label': tr(name),
                'description': tr(name) + ' · ' + tr('该年放假调休安排尚未收录')}
    return None
