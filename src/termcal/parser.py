import calendar
from datetime import date, datetime, timedelta


def _parse_date(date_str: str) -> datetime:
    """Parsuje datę w formacie DDMM (auto-rok) lub DDMMYY (dokładny rok)."""
    if len(date_str) == 4 and date_str.isdigit():
        today = date.today()
        day = int(date_str[:2])
        month = int(date_str[2:])
        year = today.year

        candidate = date(year, month, day)
        if candidate < today:
            year += 1

        return datetime(year, month, day)

    if len(date_str) == 6 and date_str.isdigit():
        return datetime.strptime(date_str, "%d%m%y")

    raise ValueError(
        f"Niepoprawna data '{date_str}'. Użyj DDMM (np. 1501) lub DDMMYY (np. 181126)."
    )


def _parse_time(time_str: str) -> tuple[int, int]:
    """Zamienia tekst '9' lub '18:30' na parę (godzina, minuta)."""
    if ":" in time_str:
        hour_str, minute_str = time_str.split(":", maxsplit=1)
        return int(hour_str), int(minute_str)
    return int(time_str), 0


def _add_months(dt: datetime, months: int) -> datetime:
    """Dodaje N miesięcy do daty, pilnując końca miesiąca (np. 31.01 + 1m -> 28.02)."""
    total_months = dt.month - 1 + months
    target_year = dt.year + total_months // 12
    target_month = total_months % 12 + 1
    max_day = calendar.monthrange(target_year, target_month)[1]
    return dt.replace(year=target_year, month=target_month, day=min(dt.day, max_day))


def _parse_recurrence(token: str) -> tuple[str, int, int] | None:
    """
    Rozpoznaje reguły cykliczności:
    - 'w' -> ('w', interwał=1, liczba_wystąpień=52)
    - 'w2' -> ('w', interwał=2, liczba_wystąpień=26)
    - 'm' lub '1m' -> ('m', interwał=1, liczba_wystąpień=12)
    - '2m' -> ('m', interwał=2, liczba_wystąpień=6)
    - 'y' -> ('y', interwał=1, liczba_wystąpień=5)
    """
    t = token.lower()

    if t == "w":
        return ("w", 1, 52)
    if t.startswith("w") and t[1:].isdigit():
        step = max(1, int(t[1:]))
        return ("w", step, max(1, 52 // step))

    if t == "m":
        return ("m", 1, 12)
    if t.endswith("m") and t[:-1].isdigit():
        step = max(1, int(t[:-1]))
        return ("m", step, max(1, 12 // step))

    if t == "y":
        return ("y", 1, 5)

    return None


def parse_single_entry(raw_entry: str) -> list[tuple[str, datetime, datetime | None]]:
    """Parsuje pojedynczy wpis wraz z opcjonalną cyklicznością (/w, /w2, /1m, /y)."""
    parts = [part.strip() for part in raw_entry.split("/") if part.strip()]
    if len(parts) < 2:
        raise ValueError(
            f"Niepoprawny format wpisu: '{raw_entry}'. Użyj: Tytuł /DDMM lub /DDMMYY"
        )

    title = parts[0]
    base_date = _parse_date(parts[1])

    start_dt = base_date.replace(hour=0, minute=0)
    end_dt: datetime | None = None
    recurrence: tuple[str, int, int] = ("w", 1, 1)

    for extra in parts[2:]:
        rec = _parse_recurrence(extra)
        if rec is not None:
            recurrence = rec
        elif "-" in extra:
            start_str, end_str = extra.split("-", maxsplit=1)
            sh, sm = _parse_time(start_str)
            eh, em = _parse_time(end_str)
            start_dt = base_date.replace(hour=sh, minute=sm)
            end_dt = base_date.replace(hour=eh, minute=em)

    unit, step, count = recurrence
    events: list[tuple[str, datetime, datetime | None]] = []

    for idx in range(count):
        if unit == "w":
            offset = timedelta(weeks=idx * step)
            occ_start = start_dt + offset
            occ_end = (end_dt + offset) if end_dt else None
        elif unit == "m":
            occ_start = _add_months(start_dt, idx * step)
            occ_end = _add_months(end_dt, idx * step) if end_dt else None
        else:
            occ_start = _add_months(start_dt, idx * step * 12)
            occ_end = _add_months(end_dt, idx * step * 12) if end_dt else None

        events.append((title, occ_start, occ_end))

    return events


def parse_batch_input(raw_text: str) -> list[tuple[str, datetime, datetime | None]]:
    """Dzieli tekst po przecinkach i parsuje wszystkie wydarzenia naraz."""
    all_parsed: list[tuple[str, datetime, datetime | None]] = []
    for chunk in raw_text.split(","):
        if chunk.strip():
            all_parsed.extend(parse_single_entry(chunk))
    return all_parsed