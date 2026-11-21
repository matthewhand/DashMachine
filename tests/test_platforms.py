from unittest.mock import Mock, patch

from dashmachine import db
from dashmachine.main.models import DataSources, DataSourcesArgs
from dashmachine.main.utils import get_data_source


def _data_source(app, platform, **args):
    ds = DataSources(name="test", platform=platform)
    for key, value in args.items():
        ds.args.append(DataSourcesArgs(key=key, value=value))
    db.session.add(ds)
    db.session.commit()
    return ds


def test_curl_json_renders_template(app):
    with app.app_context():
        ds = _data_source(
            app,
            "curl",
            resource="http://example.invalid/ip",
            value_template="IP: {{ value.ip }}",
            response_type="json",
        )
        response = Mock()
        response.json.return_value = {"ip": "10.1.2.3"}
        with patch("dashmachine.platform.curl.requests.get", return_value=response) as get:
            assert get_data_source(ds) == "IP: 10.1.2.3"
            assert get.call_args.kwargs["timeout"] == 10


def test_rest_get_renders_template(app):
    with app.app_context():
        ds = _data_source(
            app,
            "rest",
            resource="http://example.invalid/api",
            value_template="count={{ value['count'] }}",
        )
        response = Mock()
        response.json.return_value = {"count": 4}
        with patch("dashmachine.platform.rest.get", return_value=response):
            assert get_data_source(ds) == "count=4"


def test_curl_failure_is_rendered_not_raised(app):
    with app.app_context():
        ds = _data_source(
            app,
            "curl",
            resource="http://example.invalid/ip",
            value_template="error: {{ value }}",
            response_type="json",
        )
        with patch(
            "dashmachine.platform.curl.requests.get",
            side_effect=ConnectionError("boom"),
        ):
            assert "boom" in get_data_source(ds)


def test_http_status_ok(app):
    with app.app_context():
        ds = _data_source(
            app,
            "http_status",
            resource="http://example.invalid/",
            return_codes="2xx,3xx",
        )
        response = Mock(status_code=200)
        with patch(
            "dashmachine.platform.http_status.Session.send", return_value=response
        ) as send:
            result = get_data_source(ds)
        assert "theme-success-text" in result
        assert send.call_count == 1  # the request must not be sent twice


def test_http_status_failure(app):
    with app.app_context():
        ds = _data_source(
            app,
            "http_status",
            resource="http://example.invalid/",
            return_codes="2xx",
        )
        with patch(
            "dashmachine.platform.http_status.Session.send",
            return_value=Mock(status_code=500),
        ):
            assert "theme-failure-text" in get_data_source(ds)
