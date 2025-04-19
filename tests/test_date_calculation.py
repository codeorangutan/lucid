from datetime import datetime, timedelta
import pytest

def calculate_target_date(days_back: int, now: datetime) -> datetime:
    return now - timedelta(days=days_back)

def test_date_calculation_today():
    now = datetime(2025, 4, 19, 12, 0, 0)
    assert calculate_target_date(1, now).date() == datetime(2025, 4, 18).date()
    assert calculate_target_date(7, now).date() == datetime(2025, 4, 12).date()

def test_date_calculation_month_boundary():
    now = datetime(2025, 5, 1, 12, 0, 0)
    assert calculate_target_date(1, now).date() == datetime(2025, 4, 30).date()
    assert calculate_target_date(2, now).date() == datetime(2025, 4, 29).date()

def test_date_calculation_year_boundary():
    now = datetime(2025, 1, 1, 12, 0, 0)
    assert calculate_target_date(1, now).date() == datetime(2024, 12, 31).date()
    assert calculate_target_date(7, now).date() == datetime(2024, 12, 25).date()

if __name__ == "__main__":
    pytest.main([__file__])
