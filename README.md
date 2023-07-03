# LendingTree Review Scraper

## Limitations
This was done in a single day as a take-home code challenge for ReviewTrackers.
Subsequently, there are certain limitations in the "scraping" as implemented.

1. IP-blocking causes pages of results to be skipped
   1. This is mentioned in comments next to relevant code, but it seems that LendingTree will
      (at least temporarily) block IP's that send too many requests too quickly. This obviously
      includes the scraper service.
   2. Current Handling:
      1. At the moment, the handling of this scenario is limited to a brute retry of a url variation 
         with a different sort that may not be blocked (see related comments). In this scenario,
         blank pages are skipped (unless the "last"/"max" page is undeterminable, i.e. if it is
         itself blocked, in which case, we stop fetching pages after the first blocked/blank one in 
         order to ensure a stop condition).
   3. Possible solutions include:
      1. Use a proxy with a rotating IP address. This is a zero-code-change option.
      2. This hasn't been tested, but likely LendingTree will be more lenient if an authenticated 
         session is used, rather than an anonymous one. There's already a common `Session` set up
         for all scraping requests. If the login flow is performed with the same session, then
         the cookies can be reused for later requests
      3. Less Ideal: Scrape slower. The scraper could be tuned to be within 
         the limits of LendingTree's rate-limiting.
2. Longer requests than a normal maximum request window (30sec) are possible.
   1. This is mentioned in comments next to relevant code, but if this service's response latency,
      resource utilization, etc need to be improved from this implementation, it's recommended to
      be refactored into an async task (ie using Celery to handle the tasks)
