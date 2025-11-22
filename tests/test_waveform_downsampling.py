import pytest

from data_buffer import DataBuffer


def test_average_interval_simple():
    db = DataBuffer(max_points=1000)
    t0 = 1000.0
    # push 10 timestamps at 0.2s intervals
    for i in range(10):
        ts = t0 + i * 0.2
        db.add_data_points({"s1": i}, timestamp=ts)

    avg = db.average_interval(recent=5)
    assert abs(avg - 0.2) < 1e-6


@pytest.mark.parametrize(
    "sampling_interval, total_points, window_seconds, max_points",
    [
        (1.0, 100, 20.0, 1000),  # low freq, small window
        (0.1, 2000, 200.0, 1000),  # medium freq, large window -> should downsample
        (0.01, 5000, 60.0, 1000),  # high freq, medium window -> heavy downsample
        (0.5, 400, 100.0, 800),  # moderate freq, custom max_points
    ],
)
def test_get_window_indices_parametrized(
    sampling_interval, total_points, window_seconds, max_points
):
    """Parameterized test exercising get_window_indices across rates and windows.

    Asserts:
    - returned indices are not empty when there is data
    - last index equals the latest appended point
    - length of returned indices <= max_points
    - indices are strictly increasing
    """
    db = DataBuffer(max_points=max(5000, total_points + 10))
    t0 = 1000.0
    # generate timestamps at the given interval
    for i in range(total_points):
        ts = t0 + i * float(sampling_interval)
        db.add_data_points({"s1": i}, timestamp=ts)

    indices = db.get_window_indices(
        window_seconds=window_seconds, max_points=max_points
    )
    assert indices, "indices should not be empty"
    # latest appended index
    assert indices[-1] == total_points - 1
    assert len(indices) <= max_points
    assert all(indices[i] < indices[i + 1] for i in range(len(indices) - 1))
