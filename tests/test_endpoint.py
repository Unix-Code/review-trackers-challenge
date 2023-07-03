from http import HTTPStatus

import pytest
import responses
from responses import matchers


class TestEndpoint:
    @pytest.fixture(scope="session")
    def scrape_endpoint(self):
        return "/"

    @pytest.fixture
    def test_url_arg(self):
        return "https://www.lendingtree.com/reviews/business/foobar/123"

    def test_simple_load_success(
        self,
        load_fixture,
        mocked_responses,
        test_client,
        scrape_endpoint,
        test_url_arg,
        mocked_threadpoolexecutor_batch_size,
    ):
        """
        GIVEN a single page of reviews,
        VERIFY that the parsed content of the reviews is returned
        """
        single_page_fixture = load_fixture("single_page")

        # Load response for max page request
        mocked_responses.add(
            responses.GET,
            test_url_arg,
            status=HTTPStatus.OK,
            body=single_page_fixture,
            match=(
                matchers.query_string_matcher(
                    "sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid=999999999999999999"
                ),
            ),
        )

        # Load response for first batch
        for page in range(1, mocked_threadpoolexecutor_batch_size + 1):
            mocked_responses.add(
                responses.GET,
                test_url_arg,
                status=HTTPStatus.OK,
                body=single_page_fixture,
                match=(
                    matchers.query_string_matcher(f"sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid={page}"),
                ),
            )

        expected_data = [
            {
                "author": {"location": "Beaverton, OR", "name": "Anonymous"},
                "content": "Lots of review text.\n                        Some more text.",
                "review_date": "2020-05-01",
                "star_rating": 5,
                "title": "Test Title",
            },
            {
                "author": {"location": "Boston,  MA", "name": "Person"},
                "content": "content #2",
                "review_date": "2021-06-01",
                "star_rating": 4,
                "title": "Test Title 2",
            },
            {
                "author": {"location": "Phoenix, AZ", "name": "John"},
                "content": "text text 3",
                "review_date": "2019-04-01",
                "star_rating": 1,
                "title": "My Title 3!",
            },
        ]

        response = test_client.post(scrape_endpoint, json={"url": test_url_arg})
        assert response.status_code == HTTPStatus.OK

        assert "data" in response.json
        assert response.json["data"] == expected_data

    def test_multi_batch_load(
        self,
        load_fixture,
        mocked_responses,
        mocked_threadpoolexecutor_batch_size,
        test_url_arg,
        test_client,
        scrape_endpoint,
    ):
        multi_page_fixtures = [load_fixture(f"multi_page_{page}") for page in range(1, 5)]

        # Load response for max page request
        mocked_responses.add(
            responses.GET,
            test_url_arg,
            status=HTTPStatus.OK,
            body=multi_page_fixtures[-1],
            match=(
                matchers.query_string_matcher(
                    "sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid=999999999999999999"
                ),
            ),
        )

        # Load response for first batch
        for page in range(mocked_threadpoolexecutor_batch_size):
            # We assume there's the set batch size of 3
            mocked_responses.add(
                responses.GET,
                test_url_arg,
                status=HTTPStatus.OK,
                body=multi_page_fixtures[page],
                match=(
                    matchers.query_string_matcher(
                        f"sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid={page + 1}"
                    ),
                ),
            )

        # Load response for second batch

        for page in range(4 - 1, 4 - 1 + mocked_threadpoolexecutor_batch_size):
            # We assume there's the set batch size of 3
            mocked_responses.add(
                responses.GET,
                test_url_arg,
                status=HTTPStatus.OK,
                body=multi_page_fixtures[-1],
                match=(
                    matchers.query_string_matcher(
                        f"sort=cmV2aWV3c3VibWl0dGVkX2Rlc2M=&pid={page + 1}"
                    ),
                ),
            )

        expected_data = [
            # Page 1
            {
                "author": {"location": "Beaverton, OR", "name": "Anonymous"},
                "content": "Lots of review text.\n                            Some more text.",
                "review_date": "2020-05-01",
                "star_rating": 5,
                "title": "Test Title",
            },
            {
                "author": {"location": "Boston, MA", "name": "Person"},
                "content": "content #2",
                "review_date": "2021-06-01",
                "star_rating": 4,
                "title": "Test Title 2",
            },
            {
                "author": {"location": "Phoenix, AZ", "name": "John"},
                "content": "text text 3",
                "review_date": "2019-04-01",
                "star_rating": 1,
                "title": "My Title 3!",
            },
            # Page 2
            {
                "author": {"location": "Beaverton, OR", "name": "Anonymous"},
                "content": "Lots of review text.\n                            Some more text.",
                "review_date": "2020-05-01",
                "star_rating": 5,
                "title": "Test Title (Page 2)",
            },
            {
                "author": {"location": "Boston, MA", "name": "Person"},
                "content": "content #2",
                "review_date": "2021-06-01",
                "star_rating": 4,
                "title": "Test Title 2 (Page 2)",
            },
            {
                "author": {"location": "Phoenix, AZ", "name": "John"},
                "content": "text text 3",
                "review_date": "2019-04-01",
                "star_rating": 1,
                "title": "My Title 3! (Page 2)",
            },
            # Page 3
            {
                "author": {"location": "Beaverton, OR", "name": "Anonymous"},
                "content": "Lots of review text.\n                            Some more text.",
                "review_date": "2020-05-01",
                "star_rating": 5,
                "title": "Test Title (Page 3)",
            },
            {
                "author": {"location": "Boston, MA", "name": "Person"},
                "content": "content #2",
                "review_date": "2021-06-01",
                "star_rating": 4,
                "title": "Test Title 2 (Page 3)",
            },
            {
                "author": {"location": "Phoenix, AZ", "name": "John"},
                "content": "text text 3",
                "review_date": "2019-04-01",
                "star_rating": 1,
                "title": "My Title 3! (Page 3)",
            },
            # Page 4 (2nd Batch)
            {
                "author": {"location": "Beaverton, OR", "name": "Anonymous"},
                "content": "Lots of review text.\n                            Some more text.",
                "review_date": "2020-05-01",
                "star_rating": 5,
                "title": "Test Title (Next Batch)",
            },
            {
                "author": {"location": "Boston, MA", "name": "Person"},
                "content": "content #2",
                "review_date": "2021-06-01",
                "star_rating": 4,
                "title": "Test Title 2 (Next Batch)",
            },
            {
                "author": {"location": "Phoenix, AZ", "name": "John"},
                "content": "text text 3",
                "review_date": "2019-04-01",
                "star_rating": 1,
                "title": "My Title 3! (Next Batch)",
            },
        ]

        response = test_client.post(scrape_endpoint, json={"url": test_url_arg})
        assert response.status_code == HTTPStatus.OK

        assert "data" in response.json
        assert sorted(response.json["data"], key=lambda r: r["title"]) == sorted(
            expected_data, key=lambda r: r["title"]
        )

    def test_missing_url_arg(self, test_client, scrape_endpoint):
        response = test_client.post(scrape_endpoint, json={})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.parametrize(
        "test_url_arg",
        (
            "https://google.com",
            "https://www.lendingtree.com/reviews/business/foobar/",
            "https://www.lendingtree.com/reviews/business/$invalid%/123",
        ),
    )
    def test_invalid_url_arg(self, test_client, scrape_endpoint, test_url_arg):
        response = test_client.post(scrape_endpoint, json={"url": test_url_arg})
        assert response.status_code == HTTPStatus.BAD_REQUEST
