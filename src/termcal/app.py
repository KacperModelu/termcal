from datetime import date, timedelta
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Input, Static
from termcal.database import init_db
from termcal.services import (
    add_events_from_text,
    delete_events_from_command,
    get_events_in_range,
)


class TermCalApp(App):
    """Interaktywny kalendarz sterowany komendami tekstowymi."""

    TITLE = "termcal — Twój lokalny kalendarz"

    CSS = """
    #view-header {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $boost;
    }
    #calendar-scroll {
        height: 1fr;
        margin: 1 0;
    }
    .week-row {
        height: auto;
        min-height: 10;
        margin-bottom: 1;
    }
    .day-column {
        width: 1fr;
        height: auto;
        min-height: 10;
        border: solid $primary;
        padding: 0 1;
    }
    .day-today {
        border: heavy $accent;
    }
    .day-title {
        text-style: bold;
        color: $accent;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }
    #help-bar {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    #status-bar {
        height: 1;
        color: $success;
        padding: 0 1;

    }
    .day-today {
        border: heavy $accent;
    }
    .day-today .day-title {
        color: #ff8c00;
        border-bottom: solid #ff8c00;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        today = date.today()
        self.current_monday = today - timedelta(days=today.weekday())
        self.weeks_to_show = 1

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="view-header")
        yield VerticalScroll(id="calendar-scroll")
        yield Static(
            "Widoki: sw, sm, s2m, sy  •  Nawigacja: nw, pw, today  •  Usuwanie: del Tytuł /DDMM (/all)  •  q",
            id="help-bar",
        )
        yield Input(placeholder="Wpisz komendę lub wydarzenia po przecinku...")
        yield Static("", id="status-bar")

    def on_mount(self) -> None:
        init_db()
        self.refresh_calendar_view()
        self.query_one(Input).focus()

    def refresh_calendar_view(self) -> None:
        """Dynamicznie buduje siatkę N tygodni wewnątrz VerticalScroll."""
        total_days = self.weeks_to_show * 7
        end_date = self.current_monday + timedelta(days=total_days - 1)

        self.query_one("#view-header", Static).update(
            f"{self.current_monday.strftime('%d.%m.%Y')} – {end_date.strftime('%d.%m.%Y')}  ({self.weeks_to_show} tyg.)"
        )

        events = get_events_in_range(self.current_monday, end_date)
        scroll_container = self.query_one("#calendar-scroll", VerticalScroll)
        scroll_container.remove_children()

        day_names = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
        today = date.today()

        week_rows: list[Horizontal] = []
        for week_idx in range(self.weeks_to_show):
            week_monday = self.current_monday + timedelta(weeks=week_idx)
            day_columns: list[Vertical] = []

            for day_idx in range(7):
                current_day = week_monday + timedelta(days=day_idx)
                day_events = [e for e in events if e.start_time.date() == current_day]

                if not day_events:
                    body_text = "[dim]—[/dim]"
                else:
                    lines: list[str] = []
                    for e in day_events:
                        if e.end_time:
                            time_label = f"{e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')}"
                        else:
                            time_label = "cały dzień"
                        lines.append(f"[bold cyan]{time_label}[/]\n{e.title}")
                    body_text = "\n\n".join(lines)

                col_classes = "day-column day-today" if current_day == today else "day-column"
                day_columns.append(
                    Vertical(
                        Static(f"{day_names[day_idx]} {current_day.strftime('%d.%m')}", classes="day-title"),
                        Static(body_text),
                        classes=col_classes,
                    )
                )

            week_rows.append(Horizontal(*day_columns, classes="week-row"))

        scroll_container.mount(*week_rows)

    def _parse_view_command(self, cmd: str) -> int | None:
        """Rozpoznaje komendy typu sw, s2w, sm, s2m, s3m, sy i zwraca liczbę tygodni."""
        if cmd == "sw":
            return 1
        if cmd == "sm":
            return 4
        if cmd == "sy":
            return 52
        if cmd.startswith("s") and cmd.endswith("w") and cmd[1:-1].isdigit():
            return max(1, int(cmd[1:-1]))
        if cmd.startswith("s") and cmd.endswith("m") and cmd[1:-1].isdigit():
            return max(1, int(cmd[1:-1]) * 4)
        return None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw_text = event.value.strip()
        if not raw_text:
            return

        status = self.query_one("#status-bar", Static)
        cmd = raw_text.lower()
        event.input.value = ""

        # 1. Wyjście
        if cmd in ("q", "quit", "exit"):
            self.exit()
            return

        # 2. Zmiana zakresu widoku (sw, s2w, sm, s2m, s3m, sy...)
        new_weeks = self._parse_view_command(cmd)
        if new_weeks is not None:
            self.weeks_to_show = new_weeks
            self.refresh_calendar_view()
            status.update(f"Widok ustawiony na {new_weeks} tyg.")
            return

        # 3. Nawigacja do przodu / wstecz o bieżący przedział
        if cmd == "nw":
            self.current_monday += timedelta(weeks=self.weeks_to_show)
            self.refresh_calendar_view()
            status.update("Przesunięto widok do przodu.")
            return

        if cmd == "pw":
            self.current_monday -= timedelta(weeks=self.weeks_to_show)
            self.refresh_calendar_view()
            status.update("Przesunięto widok wstecz.")
            return

        if cmd == "today":
            today = date.today()
            self.current_monday = today - timedelta(days=today.weekday())
            self.refresh_calendar_view()
            status.update("Wrócono do dzisiaj.")
            return

        # 3.5 Usuwanie wydarzeń (del ...)
        if cmd == "del" or cmd.startswith("del "):
            try:
                deleted = delete_events_from_command(raw_text)
                self.refresh_calendar_view()
                if deleted == 0:
                    status.update("[yellow]Nie znaleziono pasujących wydarzeń do usunięcia.[/]")
                else:
                    status.update(f"Usunięto {deleted} wydarzeń!")
            except ValueError as err:
                status.update(f"[bold red]Błąd:[/] {err}")
            return

        # 4. Dodawanie wydarzeń po przecinku
        try:
            added = add_events_from_text(raw_text)
            self.refresh_calendar_view()
            status.update(f"Dodano {len(added)} wydarzeń!")
        except ValueError as err:
            status.update(f"[bold red]Błąd:[/] {err}")


if __name__ == "__main__":
    app = TermCalApp()
    app.run()