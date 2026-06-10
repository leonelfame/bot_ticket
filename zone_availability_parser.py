import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


GONEXT_RE = re.compile(r"gonextstep\('([^']+)'\s*,\s*'([^']+)'")


@dataclass(frozen=True)
class ZoneAvailability:
    flow: str
    code: str
    label: str
    availability: str
    available_count: int | None

    @property
    def is_available(self) -> bool:
        if self.available_count is not None:
            return self.available_count > 0
        return self.availability.lower() == "available"


class ZoneAvailabilityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[ZoneAvailability] = []
        self._current_flow = ""
        self._current_code = ""
        self._in_target_row = False
        self._in_cell = False
        self._cell_text: list[str] = []
        self._cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "tr":
            match = GONEXT_RE.search(attr_map.get("onclick", ""))
            if match:
                self._current_flow = match.group(1)
                self._current_code = match.group(2)
                self._in_target_row = True
                self._cells = []
        elif self._in_target_row and tag == "td":
            self._in_cell = True
            self._cell_text = []

    def handle_data(self, data: str) -> None:
        if self._in_target_row and self._in_cell:
            text = " ".join(data.split())
            if text:
                self._cell_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._in_target_row and tag == "td":
            self._cells.append(" ".join(self._cell_text).strip())
            self._in_cell = False
            self._cell_text = []
        elif self._in_target_row and tag == "tr":
            label = self._cells[0] if self._cells else self._current_code
            availability = self._cells[1] if len(self._cells) > 1 else ""
            self.rows.append(
                ZoneAvailability(
                    flow=self._current_flow,
                    code=self._current_code,
                    label=label,
                    availability=availability,
                    available_count=parse_available_count(availability),
                )
            )
            self._current_flow = ""
            self._current_code = ""
            self._in_target_row = False
            self._cells = []


def parse_available_count(value: str) -> int | None:
    cleaned = value.strip().replace(",", "")
    return int(cleaned) if cleaned.isdigit() else None


def parse_zone_availability_html(html: str) -> list[ZoneAvailability]:
    parser = ZoneAvailabilityParser()
    parser.feed(html)
    return parser.rows


def parse_zone_availability_file(path: str | Path) -> list[ZoneAvailability]:
    return parse_zone_availability_html(Path(path).read_text(encoding="utf-8"))


def summarize_zones(zones: list[ZoneAvailability]) -> dict[str, int]:
    available = sum(1 for zone in zones if zone.is_available)
    return {
        "total": len(zones),
        "available": available,
        "sold_out": len(zones) - available,
    }
