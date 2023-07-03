from dataclasses import asdict

import pytest
from bs4 import BeautifulSoup

from errors import UnprocessableReviewError
from scraper import ReviewParser


class TestParser:
    @pytest.mark.parametrize(
        "field",
        # See FieldSelectors enum
        ("author_text", "text_content", "review_date", "star_rating"),
    )
    def test_missing_field(self, load_fixture, field):
        test_content = load_fixture(f"review_missing_{field}")

        with pytest.raises(
            UnprocessableReviewError, match=f"Couldn't find {field.upper()} element"
        ):
            ReviewParser(BeautifulSoup(test_content)).parse()

    @pytest.mark.parametrize(
        "star_rating_text",
        ("   notANum of 5", "some random text", "5 butnottherest", "5 of 5"),
    )
    def test_invalid_star_rating(self, load_fixture, star_rating_text):
        test_content = load_fixture(f"review_dynamic_star_rating")
        test_content = test_content.format(test_star_rating=star_rating_text)
        with pytest.raises(
            UnprocessableReviewError, match="Couldn't parse star rating text content"
        ):
            ReviewParser(BeautifulSoup(test_content)).parse()

    @pytest.mark.parametrize(
        "star_rating_text,expected_value",
        (
            ("\n \t  (5 of 5)  \n", 5),
            ("(4 of 5)", 4),
            ("(3 of 5)", 3),
            ("(2 of 5)", 2),
            ("(1 of 5)", 1),
            ("(0 of 5)", 0),
        ),
    )
    def test_valid_star_rating(self, load_fixture, star_rating_text, expected_value):
        test_content = load_fixture(f"review_dynamic_star_rating")
        test_content = test_content.format(test_star_rating=star_rating_text)
        assert ReviewParser(BeautifulSoup(test_content)).star_rating == expected_value

    @pytest.mark.parametrize(
        "author_text",
        ("NoComma from Beaverton OR", "some random text"),
    )
    def test_invalid_author_text(self, load_fixture, author_text):
        test_content = load_fixture(f"review_dynamic_author_text")
        test_content = test_content.format(test_author_text=author_text)
        with pytest.raises(UnprocessableReviewError, match="Couldn't parse author text content"):
            ReviewParser(BeautifulSoup(test_content)).parse()

    @pytest.mark.parametrize(
        "author_text,expected_value",
        (
            ("Anonymous from Beaverton, OR", {"name": "Anonymous", "location": "Beaverton, OR"}),
            (
                "\n  Some'Name from Boston,  MA  \n  ",
                {"name": "Some'Name", "location": "Boston,  MA"},
            ),
            (
                "\n  Some  Name from Brookline,  MA  \n  ",
                {"name": "Some  Name", "location": "Brookline,  MA"},
            ),
        ),
    )
    def test_valid_author(self, load_fixture, author_text, expected_value):
        test_content = load_fixture(f"review_dynamic_author_text")
        test_content = test_content.format(test_author_text=author_text)
        assert asdict(ReviewParser(BeautifulSoup(test_content)).author) == expected_value

    @pytest.mark.parametrize(
        "review_date",
        ("somerandomtext", "Reviewed in June", "Reviewed in 2021", "Verbed in June 2021"),
    )
    def test_invalid_review_date(self, load_fixture, review_date):
        test_content = load_fixture(f"review_dynamic_review_date")
        test_content = test_content.format(test_review_date=review_date)
        with pytest.raises(
            UnprocessableReviewError, match="Couldn't parse review date text content"
        ):
            ReviewParser(BeautifulSoup(test_content)).parse()

    def test_invalid_review_date_invalid_month(self, load_fixture):
        test_content = load_fixture(f"review_dynamic_review_date")
        test_content = test_content.format(test_review_date="Reviewed in NotAMonth 2021")
        with pytest.raises(
            UnprocessableReviewError,
            match="Couldn't parse valid month from review date text content",
        ):
            ReviewParser(BeautifulSoup(test_content)).parse()

    @pytest.mark.parametrize(
        "review_date_text,expected_value",
        (
            ("\n  \n  Reviewed in June 2021  \n ", "2021-06-01"),
            (" \n  Reviewed in August 2016  \n ", "2016-08-01"),
            ("   Reviewed in September 2012   ", "2012-09-01"),
        ),
    )
    def test_valid_review_date(self, load_fixture, review_date_text, expected_value):
        test_content = load_fixture(f"review_dynamic_review_date")
        test_content = test_content.format(test_review_date=review_date_text)
        assert ReviewParser(BeautifulSoup(test_content)).review_date == expected_value
