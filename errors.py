class CommunicationError(Exception):
    """Error communicating with resource to scrape (ie LendingTree)"""

    pass


class UnprocessableReviewError(Exception):
    """Error parsing a review"""

    pass


class InvalidScrapeURLError(Exception):
    """Error parsing URL argument (to scrape)"""

    pass
