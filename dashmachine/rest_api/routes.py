"""Small JSON API."""
from flask import Blueprint, jsonify

from dashmachine.version import version

rest_api = Blueprint("rest_api", __name__)


@rest_api.route("/api/version", methods=["GET"])
def api_version():
    return jsonify({"Version": version})
