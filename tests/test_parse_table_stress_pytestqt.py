from gui.main_window import ACUSimulator


def make_record(i: int):
    return {
        "timestamp": f"12:00:00.{i:03d}",
        "address": f"127.0.0.{i}:10000",
        "device_type": "DUMMY",
        "data_length": 4,
        "parsed_data": {"val": i},
    }


def test_parse_table_stress(qtbot):
    win = ACUSimulator(enable_dialogs=False)
    qtbot.addWidget(win)

    # simulate many parse results quickly
    count = 300
    for i in range(count):
        win._on_parse_result(make_record(i))

    # wait until some rows have been added (buffer drained incrementally)
    qtbot.waitUntil(
        lambda: getattr(win, "parse_table", None) is not None
        and win.parse_table.rowCount() >= 100,
        timeout=5000,
    )

    assert win.parse_table.rowCount() >= 100

    # cleanup
    win.close()
