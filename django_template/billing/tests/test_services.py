from datetime import datetime

from django.test import SimpleTestCase

from django_template.billing.models import Price
from django_template.billing.services import _add_interval


class PriceIntervalTests(SimpleTestCase):
    def test_days(self):
        start = datetime(2026, 1, 1, 12, 0)
        self.assertEqual(_add_interval(start, Price.Interval.DAY, 1), datetime(2026, 1, 2, 12, 0))

    def test_weeks(self):
        start = datetime(2026, 1, 1, 12, 0)
        self.assertEqual(_add_interval(start, Price.Interval.WEEK, 1), datetime(2026, 1, 8, 12, 0))

    def test_month_clamps_end_of_month(self):
        start = datetime(2026, 1, 31, 12, 0)
        self.assertEqual(_add_interval(start, Price.Interval.MONTH, 1), datetime(2026, 2, 28, 12, 0))

    def test_year_clamps_leap_day(self):
        start = datetime(2028, 2, 29, 12, 0)
        self.assertEqual(_add_interval(start, Price.Interval.YEAR, 1), datetime(2029, 2, 28, 12, 0))
