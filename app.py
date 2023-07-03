from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

from scraper import LendingTreeScraper

app = Flask(__name__)


@app.post("/")
def scrape_for_reviews():
    req_body = request.json
    if "url" not in req_body:
        raise BadRequest(description="URL to scrape argument is missing")

    scraper = LendingTreeScraper()  # Potentially override values with env vars/app config
    try:
        business_name_slug, business_id = scraper.parse_url_args(req_body["url"])
    except ValueError:
        raise BadRequest(description="URL to scrape argument is not valid")

    reviews = scraper.collect_all_reviews(business_name_slug, business_id)

    return jsonify({"data": reviews})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # Potentially override values with env vars/app config
