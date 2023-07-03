import calendar
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from enum import Enum
from http import HTTPStatus
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from errors import CommunicationError, UnprocessableReviewError
from schemas import Author, Review

logger = logging.getLogger(__name__)


class ReviewParser:
    # Something akin to this: "... (<num> of 5) stars ..."
    STAR_RATING_PATTERN = re.compile(r"\s*\((?P<stars>\d) of \d\)\s*stars\s*")

    # Something akin to this: "... <name> from <location> ..."
    #                         "    {Bruno} from {Fort Worth,  TX}    "
    AUTHOR_PATTERN = re.compile(r"\s*(?P<name>\S+) +from +(?P<location>[a-zA-Z ]+, +[A-Z]{2})\s*")

    # Something akin to this: "... Reviewed in February 2018 ..."
    REVIEW_DATE_PATTERN = re.compile(r"\s*Reviewed in (?P<month>[a-zA-Z]+) (?P<year>\d{4})\s*")

    class FieldSelectors(Enum):
        STAR_RATING = ".numRec"
        TEXT_CONTENT = ".reviewText"
        TITLE = ".reviewTitle"
        AUTHOR_TEXT = ".consumerName"
        REVIEW_DATE = ".consumerReviewDate"

    def __init__(self, raw_review_content: Tag):
        self.raw_review_content = raw_review_content

    def _find_review_field_elem(self, field_selector: FieldSelectors) -> Tag:
        elem = self.raw_review_content.select_one(field_selector.value)
        if elem is None:
            raise UnprocessableReviewError(f"Couldn't find {field_selector.name} element")
        return elem

    @property
    def star_rating(self) -> int:
        star_rating_elem = self._find_review_field_elem(self.FieldSelectors.STAR_RATING)
        star_rating_match = re.fullmatch(self.STAR_RATING_PATTERN, star_rating_elem.text)
        star_rating = star_rating_match.group(1) if star_rating_match is not None else None
        if star_rating is None:
            raise UnprocessableReviewError("Couldn't parse star rating text content")

        return int(star_rating)  # can assume valid integer due to regex

    @property
    def text_content(self) -> str:
        content_elem = self._find_review_field_elem(self.FieldSelectors.TEXT_CONTENT)
        return content_elem.text.strip()

    @property
    def title(self) -> str:
        title_elem = self._find_review_field_elem(self.FieldSelectors.TITLE)
        return title_elem.text.strip()

    @property
    def author(self) -> Author:
        author_elem = self._find_review_field_elem(self.FieldSelectors.AUTHOR_TEXT)
        author_match = re.fullmatch(self.AUTHOR_PATTERN, author_elem.text)
        author_match_groups = author_match.groups() if author_match is not None else tuple()
        if len(author_match_groups) != 2:
            raise UnprocessableReviewError("Couldn't parse author text content")
        name, location = author_match_groups
        return Author(name=name, location=location)

    @property
    def review_date(self) -> str:
        review_date_elem = self._find_review_field_elem(self.FieldSelectors.REVIEW_DATE)
        review_date_match = re.fullmatch(self.REVIEW_DATE_PATTERN, review_date_elem.text)
        review_date_match_groups = (
            review_date_match.groups() if review_date_match is not None else tuple()
        )

        if len(review_date_match_groups) != 2:
            raise UnprocessableReviewError("Couldn't parse review date text content")

        month, year = review_date_match_groups

        try:
            # Skip first month_name element to avoid empty string
            # https://docs.python.org/3/library/calendar.html#calendar.month_name
            month_num = calendar.month_name[1:].index(month) + 1
        except ValueError:
            raise UnprocessableReviewError(
                "Couldn't parse valid month from review date text content"
            )

        return date(year=int(year), month=month_num, day=1).isoformat()

    def parse(self) -> Review:
        return Review(
            title=self.title,
            content=self.text_content,
            author=self.author,
            review_date=self.review_date,
            star_rating=self.star_rating,
        )


class LendingTreeScraper:
    """An HTML Scraper to parse review content from LendingTree business profile pages"""

    HOSTNAME = "www.lendingtree.com"

    URL_PATH_REGEX_PATTERN = re.compile(
        r"\/reviews\/business\/(?P<business_name>[a-zA-Z0-9-]+)\/(?P<business_id>[0-9]+)\/?"
    )

    URL_ARG_PATTERN = (
        "https://{hostname}/reviews/business/{{business_name_slug}}/{{business_id}}{{query_params}}"
    ).format(hostname=HOSTNAME)

    PAGINATION_PARAM = "pid"
    SORT_PARAM = "sort"
    MOST_RECENT_SORT = "cmV2aWV3c3VibWl0dGVkX2Rlc2M="

    REVIEW_SECTION_SELECTOR = ".mainReviews"
    CURRENT_PAGE_NUMBER_SELECTOR = ".pageNum .page-link"

    def __init__(self, request_timeout_sec: int = 15):
        self.req_session = requests.Session()
        self.request_timeout_sec = request_timeout_sec

    def _parse_page_number_from_page_content(self, page: BeautifulSoup) -> Optional[int]:
        page_number_elem = page.select_one(self.CURRENT_PAGE_NUMBER_SELECTOR)
        if page_number_elem is None:
            return None

        try:
            return int(page_number_elem.text)
        except ValueError:
            return None

    def _collect_page_of_reviews_with_loaded_page(
        self, business_name_slug: str, business_id: int, page_num: int
    ) -> tuple[list[Review], int]:
        # We manually construct the query params, as LendTree is sensitive to the order of the
        # query params and there being an unencoded "=" at the end of the sort arg
        query_params = (
            f"?{self.SORT_PARAM}={self.MOST_RECENT_SORT}&{self.PAGINATION_PARAM}={page_num}"
        )

        request_url = self.URL_ARG_PATTERN.format(
            business_name_slug=business_name_slug,
            business_id=business_id,
            query_params=query_params,
        )

        response = self.req_session.get(
            request_url,
        )

        if response.status_code != HTTPStatus.OK:
            # TODO: Handle response in error
            raise CommunicationError(response)

        soup = BeautifulSoup(response.text, "lxml")

        loaded_page = self._parse_page_number_from_page_content(soup)

        return (
            [
                ReviewParser(raw_review_content).parse()
                for raw_review_content in soup.select(self.REVIEW_SECTION_SELECTOR)
            ]
            # Note: LendingTree will clamp page numbers to the maximum available page,
            #       so when we request a page number beyond the bounds of total pages,
            #       return an empty list. We can also assume that in other strange cases,
            #       we can assume that an unparsed current page number, means no results.
            if loaded_page == page_num else [],
            loaded_page,
        )

    def collect_page_of_reviews(
        self, business_name_slug: str, business_id: int, page_num: int
    ) -> list[Review]:
        return self._collect_page_of_reviews_with_loaded_page(
            business_name_slug, business_id, page_num
        )[0]

    def collect_all_reviews(self, business_name_slug: str, business_id: int):
        result = []
        finished = False
        current_batch = 0
        max_page = None
        # Lending Tree performs server-side rendering, thus having no nicely accessible API to hit
        # with structured requests and that will report pagination information.
        # Instead, we will be performing some scraping.
        with ThreadPoolExecutor() as executor:
            # Note: The concurrent model chosen was a ThreadPoolExecutor, however async non-blocking
            #       io on top of asyncio can be used instead. If the latency of this server or
            #       the speed of the concurrent scraping with the ThreadPoolExecutor isn't meeting
            #       expectations, this functionality should be moved to an async task.
            batch_size = executor._max_workers

            # Since LendingTree will clamp to the max page when requesting a page that's greater,
            # we perform an initial request with an absurdly large page number to retrieve the max
            page_result, loaded_page = self._collect_page_of_reviews_with_loaded_page(
                business_name_slug, business_id, 999999999999999999
            )
            result.extend(page_result)
            max_page = loaded_page
            if max_page is None:
                # NOTE: There are certain strange pages that are within
                # the min and max pages but will still load as containing 0 reviews
                # and with an un-parseable page number.
                # (e.g. .../ondeck/51886298?sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid=39 )
                logger.warning(
                    "Unable to load maximum page. Will be collecting only up to first 'empty' page"
                )

            while not finished:
                # Note: There can be enough pages to scrape where this operation no longer makes
                #       sense for the lifetime of a request to the server and should instead
                #       be performed as an async task.

                batch_page_offset = batch_size * current_batch
                batch_requests = {
                    executor.submit(
                        self._collect_page_of_reviews_with_loaded_page,
                        business_name_slug,
                        business_id,
                        page_num,
                    ): page_num
                    for page_num in range(batch_page_offset + 1, batch_page_offset + batch_size + 1)
                }

                for future in as_completed(batch_requests, timeout=self.request_timeout_sec):
                    requested_page = batch_requests[future]
                    page_result, loaded_page = future.result()
                    result.extend(page_result)
                    if (
                        not finished
                        # We're trying to be as robust as possible with this scraper.
                        # In case the actual max page is broken/"empty", we'll continue until
                        # we hit the first broken/"empty" page, even if it's not in fact the last
                        and (max_page is None and requested_page != loaded_page)
                        or (requested_page == max_page)
                    ):
                        # Note: LendingTree clamps page numbers, so we know we've passed the final
                        #       page within this batch
                        finished = True

                current_batch += 1
        return result

    def parse_url_args(self, url: str) -> tuple[str, int]:
        """
        Given full URL, parse (business_name_slug, business_id)

        :raises ValueError: if url args could not successfully be parsed
        """
        invalid_url_msg = "Invalid input url for scraping"

        parsed_url = urlparse(url)
        if parsed_url.hostname != self.HOSTNAME:
            raise ValueError(f"{invalid_url_msg}: Invalid hostname")

        url_args_match = re.fullmatch(self.URL_PATH_REGEX_PATTERN, parsed_url.path)
        url_args = url_args_match.groups() if url_args_match is not None else tuple()

        if len(url_args) != 2:
            raise ValueError(
                f"{invalid_url_msg}: Missing or invalid url args (business_slug_name, business_id)"
            )

        return url_args
