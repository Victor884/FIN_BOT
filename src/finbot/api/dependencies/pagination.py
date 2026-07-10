from datetime import date, timedelta

from fastapi import Query


def date_range(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> tuple[date, date]:
    today = date.today()
    resolved_start = start_date or today.replace(day=1)
    resolved_end = end_date or today
    if resolved_start > resolved_end:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="start_date must be before end_date")
    if (resolved_end - resolved_start) > timedelta(days=730):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="date range is too large")
    return resolved_start, resolved_end
