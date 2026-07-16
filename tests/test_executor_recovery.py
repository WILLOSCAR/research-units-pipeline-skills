from __future__ import annotations

from tooling.common import UnitsTable
from tooling.run_state import recover_stale_doing_units


def test_recover_stale_doing_units_resets_first_interrupted_unit_only() -> None:
    table = UnitsTable(
        fieldnames=["unit_id", "status", "depends_on"],
        rows=[
            {"unit_id": "U001", "status": "DONE", "depends_on": ""},
            {"unit_id": "U010", "status": "DOING", "depends_on": "U001"},
            {"unit_id": "U020", "status": "DOING", "depends_on": "U010"},
        ],
    )

    recovered = recover_stale_doing_units(table)

    assert recovered == ["U010"]
    assert [row["status"] for row in table.rows] == ["DONE", "BLOCKED", "DOING"]
