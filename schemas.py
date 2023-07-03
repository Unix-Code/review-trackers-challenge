import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date

from flask import jsonify
from flask.json.provider import DefaultJSONProvider


@dataclass
class Author:
    name: str
    location: str


@dataclass
class Review:
    title: str
    content: str
    author: Author
    review_date: str  # yyyy-mm-01
    star_rating: int  # Out of 5
