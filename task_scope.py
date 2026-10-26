"""Date limits for the header's weekly task overview; never changes task data."""
from datetime import timedelta


def overview_bounds(current):
    """Monday–Sunday of this week, plus the two days immediately before today."""
    week_start = current - timedelta(days=current.weekday())
    start = min(week_start, current - timedelta(days=2))
    end = week_start + timedelta(days=6)
    return start.isoformat(), end.isoformat()
