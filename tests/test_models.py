"""Unit tests (UT): models and validation helpers tested in isolation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.models import (MAX_CENTS, ValidationError, clean_category,
                                    format_money, parse_date, parse_month, to_cents)


class ToCentsTests(unittest.TestCase):
    def test_ut01_whole_and_decimal_amounts(self):
        """UT-01 to_cents converts whole and decimal amounts exactly"""
        self.assertEqual(to_cents("5"), 500)
        self.assertEqual(to_cents("12.50"), 1250)
        self.assertEqual(to_cents(19.99), 1999)

    def test_ut02_no_float_drift(self):
        """UT-02 to_cents avoids floating point drift (0.10 + 0.20 == 0.30)"""
        self.assertEqual(to_cents("0.10") + to_cents("0.20"), to_cents("0.30"))

    def test_ut03_rejects_non_numeric(self):
        """UT-03 to_cents rejects non-numeric text"""
        for bad in ("abc", "", "   ", "1,5", "12abc", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                to_cents(bad)

    def test_ut04_rejects_zero_negative_nan_inf(self):
        """UT-04 to_cents rejects zero, negative, NaN and infinity"""
        for bad in ("0", "-1", "-0.01", "NaN", "inf", "-inf"):
            with self.assertRaises(ValidationError, msg=bad):
                to_cents(bad)

    def test_ut05_boundaries(self):
        """UT-05 to_cents accepts the smallest and largest valid amounts"""
        self.assertEqual(to_cents("0.01"), 1)
        self.assertEqual(to_cents(MAX_CENTS / 100), MAX_CENTS)

    def test_ut06_rejects_too_small_and_too_large(self):
        """UT-06 to_cents rejects values below 0.01 and above the maximum"""
        for bad in ("0.004", "0.0000001", "1e400", "99999999999999999999", "10000000000.01"):
            with self.assertRaises(ValidationError, msg=bad):
                to_cents(bad)


class DateAndMonthTests(unittest.TestCase):
    def test_ut07_valid_dates(self):
        """UT-07 parse_date accepts valid ISO dates including leap day"""
        self.assertEqual(parse_date("2026-10-01"), "2026-10-01")
        self.assertEqual(parse_date("2028-02-29"), "2028-02-29")

    def test_ut08_invalid_dates(self):
        """UT-08 parse_date rejects impossible and malformed dates"""
        for bad in ("2026-13-01", "2026-02-30", "2027-02-29", "01/10/2026", "", "abc", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                parse_date(bad)

    def test_ut09_valid_month(self):
        """UT-09 parse_month returns (year, month)"""
        self.assertEqual(parse_month("2026-10"), (2026, 10))
        self.assertEqual(parse_month("2026-01"), (2026, 1))

    def test_ut10_invalid_month(self):
        """UT-10 parse_month rejects bad months and formats"""
        for bad in ("abc", "2026-13", "2026-00", "2026", "26-10", "2026-10-01", "", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                parse_month(bad)


class CategoryAndFormatTests(unittest.TestCase):
    def test_ut11_category_normalised(self):
        """UT-11 clean_category trims and lowercases"""
        self.assertEqual(clean_category("  Food "), "food")

    def test_ut12_category_invalid(self):
        """UT-12 clean_category rejects empty and over-long names"""
        for bad in ("", "   ", None, "x" * 31):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                clean_category(bad)
        self.assertEqual(clean_category("x" * 30), "x" * 30)

    def test_ut13_format_money(self):
        """UT-13 format_money shows two decimals and thousands separators"""
        self.assertEqual(format_money(5), "0.05")
        self.assertEqual(format_money(123456789), "1,234,567.89")


if __name__ == "__main__":
    unittest.main()
