import uuid
from datetime import date, datetime, time
from sqlmodel import select
from termcal.database import get_session
from termcal.models import Event
from termcal.parser import _parse_date, _parse_time, parse_batch_input


def add_event(title: str, start_time: datetime, end_time: datetime | None = None) -> Event:
    """Tworzy nowe wydarzenie i zapisuje je w bazie SQLite."""
    event = Event(title=title, start_time=start_time, end_time=end_time)
    with get_session() as session:
        session.add(event)
        session.commit()
        session.refresh(event)
    return event


def add_events_from_text(raw_text: str) -> list[Event]:
    """Parsuje tekst po przecinkach i zapisuje wszystkie wydarzenia w bazie."""
    created_events: list[Event] = []

    with get_session() as session:
        for chunk in raw_text.split(","):
            if not chunk.strip():
                continue
            parsed_items = parse_batch_input(chunk)
            series_id = str(uuid.uuid4()) if len(parsed_items) > 1 else None

            for title, start_dt, end_dt in parsed_items:
                event = Event(
                    title=title,
                    start_time=start_dt,
                    end_time=end_dt,
                    series_id=series_id,
                )
                session.add(event)
                created_events.append(event)

        session.commit()
        for event in created_events:
            session.refresh(event)

    return created_events


def delete_events_from_command(raw_cmd: str) -> int:
    """
    Obsługuje komendy usuwania:
    - del Tytuł /DDMM           -> usuwa pojedyncze wydarzenie z tego dnia
    - del Tytuł /DDMM/all       -> usuwa to wydarzenie ORAZ wszystkie powtórzenia z tej serii
    - del Tytuł /DDMM/18:30     -> usuwa konkretne wydarzenie o danej godzinie
    - del /DDMM                 -> usuwa wszystkie wydarzenia z podanego dnia
    """
    body = raw_cmd[3:].strip()
    if not body:
        raise ValueError("Podaj co usunąć, np.: del Zuzanna /2611 lub del Zuzanna /2611/all")

    parts = [p.strip() for p in body.split("/") if p.strip()]
    delete_series = False

    if parts and parts[-1].lower() == "all":
        delete_series = True
        parts.pop()

    if not parts:
        raise ValueError("Brakuje daty w komendzie del.")

    if body.startswith("/"):
        title_filter: str | None = None
        date_token = parts[0]
        extra_tokens = parts[1:]
    else:
        if len(parts) < 2:
            raise ValueError("Użyj formatu: del Tytuł /DDMM (opcjonalnie /all)")
        title_filter = parts[0].lower()
        date_token = parts[1]
        extra_tokens = parts[2:]

    target_date = _parse_date(date_token).date()
    time_filter: tuple[int, int] | None = None
    if extra_tokens:
        start_part = extra_tokens[0].split("-")[0]
        time_filter = _parse_time(start_part)

    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    with get_session() as session:
        statement = select(Event).where(Event.start_time >= day_start, Event.start_time <= day_end)
        candidates = list(session.exec(statement).all())

        matched: list[Event] = []
        for ev in candidates:
            if title_filter and ev.title.lower() != title_filter:
                continue
            if time_filter and (ev.start_time.hour, ev.start_time.minute) != time_filter:
                continue
            matched.append(ev)

        if not matched:
            return 0

        to_delete: list[Event] = list(matched)
        if delete_series:
            series_ids = {ev.series_id for ev in matched if ev.series_id is not None}
            if series_ids:
                series_stmt = select(Event).where(Event.series_id.in_(series_ids))  # type: ignore[union-attr]
                to_delete = list(session.exec(series_stmt).all())

        seen_ids: set[int] = set()
        deleted_count = 0
        for ev in to_delete:
            if ev.id is not None and ev.id not in seen_ids:
                seen_ids.add(ev.id)
                session.delete(ev)
                deleted_count += 1

        session.commit()
        return deleted_count


def get_events_in_range(start_date: date, end_date: date) -> list[Event]:
    """Pobiera wydarzenia z bazy od start_date (00:00) do end_date (23:59:59)."""
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    with get_session() as session:
        statement = (
            select(Event)
            .where(Event.start_time >= start_dt, Event.start_time <= end_dt)
            .order_by(Event.start_time)
        )
        return list(session.exec(statement).all())


def get_all_events() -> list[Event]:
    """Pobiera wszystkie wydarzenia z bazy posortowane po dacie."""
    with get_session() as session:
        statement = select(Event).order_by(Event.start_time)
        return list(session.exec(statement).all())