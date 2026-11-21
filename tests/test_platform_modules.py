"""Direct tests for the platform integration modules.

Each platform is a thin adapter: build a URL, call the remote API, render a
Jinja template. These tests exercise the adapters without the database so a
change to one cannot quietly break the card it feeds.
"""
import copy
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def _app_context(app):
    """The adapters render Jinja templates, which need an app context."""
    with app.app_context():
        yield


class Resp:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload=None, text="", content_type="application/json"):
        self.payload = payload
        self.text = text
        self.headers = {"content-type": content_type}
        self.status_code = 200

    def json(self):
        return self.payload


def _router(routes):
    """Return a requests.get side effect that dispatches on URL suffix."""

    def _get(url, **kwargs):
        for needle, payload in routes.items():
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                # a fresh copy per call: some platforms mutate the payload
                return Resp(copy.deepcopy(payload))
        raise AssertionError(f"unexpected request: {url}")

    return _get


# --------------------------------------------------------------------------- #
# Docker
# --------------------------------------------------------------------------- #
DOCKER_INFO = {
    "Name": "docker1",
    "Containers": 12,
    "ContainersRunning": 10,
    "ContainersPaused": 1,
    "ContainersStopped": 1,
    "Images": 34,
    "Warnings": [],
    "Driver": "overlay2",
    "NCPU": 8,
    "MemTotal": 34359738368,
}


def test_docker_discovers_api_version_and_renders_template():
    from dashmachine.platform import docker as mod

    version_probe = Resp({"message": "client version 1.41 is too new"}, content_type="application/json")
    info = Resp(DOCKER_INFO)

    def _get(url, **kwargs):
        if "/v999/info" in url:
            assert kwargs["timeout"] == 10
            return version_probe
        assert "/v1.41/" in url
        return info

    platform = mod.Platform(
        host="10.0.0.5",
        port=None,
        value_template="{{ name }}|{{ containers_running }}/{{ containers }}|{{ memory }}",
    )
    with patch.object(mod.requests, "get", side_effect=_get):
        result = platform.process()

    assert result == "docker1|10/12|32.0 GB"


def test_docker_text_plain_response_becomes_error():
    from dashmachine.platform import docker as mod

    platform = mod.Platform(
        host="10.0.0.5",
        port=None,
        value_template="error={{ error }}",
    )
    text = Resp(text="API version not supported", content_type="text/plain")
    with patch.object(mod.requests, "get", return_value=text):
        result = platform.process()

    assert "API version not supported" in result
    assert "<div" not in result


def test_docker_custom_card_html():
    from dashmachine.platform import docker as mod

    version_probe = Resp({"message": "client version 1.41 is too new"})
    info = Resp(DOCKER_INFO)

    def _get(url, **kwargs):
        return version_probe if "/v999/" in url else info

    platform = mod.Platform(host="10.0.0.5", port=None, card_type="Custom")
    with patch.object(mod.requests, "get", side_effect=_get):
        result = platform.process()

    assert "docker1" in result
    assert "Running: </span>10" in result
    assert "lock_open" in result  # TLS disabled indicator


def test_docker_connection_failure_is_reported():
    from dashmachine.platform import docker as mod

    platform = mod.Platform(
        host="10.0.0.5", port=None, value_template="{{ error }}"
    )
    with patch.object(mod.requests, "get", side_effect=ConnectionError("refused")):
        result = platform.process()

    assert "refused" in result


def test_docker_requires_host():
    from dashmachine.platform import docker as mod

    assert mod.Platform(value_template="{{ error }}").process() == "host missing"


@pytest.mark.parametrize(
    "tls_mode, expected",
    [
        ("Both", "tls_mode set to Both, and missing tls_ca/tls_cert/tls_key"),
        ("Server", "tls_mode set to Server, and missing tls_ca"),
        ("Bogus", "Invalid tls_mode : Bogus"),
    ],
)
def test_docker_tls_validation(tls_mode, expected):
    from dashmachine.platform import docker as mod

    assert mod.Platform(host="h", tls_mode=tls_mode, value_template="").process() == expected


def test_docker_format_size():
    from dashmachine.platform import docker as mod

    docker = mod.Docker("GET", "http://", "h", None, None, "App", None, None, None, None)
    assert docker.formatSize(512) == "512 "
    assert docker.formatSize(2048) == "2.0 KB"
    assert docker.formatSize(5 * 1024 ** 3) == "5.0 GB"


# --------------------------------------------------------------------------- #
# Sonarr / Radarr / Lidarr
# --------------------------------------------------------------------------- #
ARR_ROUTES = {
    "/system/status": {"version": "4.0.1"},
    "/wanted/missing/": {"totalRecords": 7},
    "/wanted/cutoff/": {"totalRecords": 3},
    # sonarr/radarr count the queue with len(), lidarr reads totalRecords
    "/queue": [{"id": 1}, {"id": 2}],
    "/movie": [{"id": 1}, {"id": 2}],
    "/diskspace": [
        {"path": "/data", "totalSpace": 4 * 1024 ** 3, "freeSpace": 1024 ** 3}
    ],
}


@pytest.mark.parametrize(
    "module_name, extra, template, expected",
    [
        ("sonarr", {}, "{{ version }} missing={{ wanted_missing }} q={{ queue }} free={{ diskspace[0]['free'] }}", "4.0.1 missing=7 q=2 free=1024.0 MB"),
        ("radarr", {}, "{{ version }} movies={{ movies }} q={{ queue }} free={{ diskspace[0]['free'] }}", "4.0.1 movies=2 q=2 free=1024.0 MB"),
        ("lidarr", {"api_version": "v1"}, "{{ version }} missing={{ wanted_missing }} cutoff={{ wanted_cutoff }} free={{ diskspace[0]['free'] }}", "4.0.1 missing=7 cutoff=3 free=1024.0 MB"),
    ],
)
def test_arr_platforms(module_name, extra, template, expected):
    mod = __import__(f"dashmachine.platform.{module_name}", fromlist=["Platform"])
    routes = dict(ARR_ROUTES)
    if module_name == "lidarr":
        routes["/queue"] = {"totalRecords": 2}
    platform = mod.Platform(
        host="arr.local", port="7878", api_key="k", value_template=template, **extra
    )
    with patch.object(mod.requests, "get", side_effect=_router(routes)) as get:
        result = platform.process()

    assert result == expected
    # every call carries the API key and a timeout
    for call in get.call_args_list:
        assert call.kwargs["headers"] == {"X-Api-Key": "k"}
        assert call.kwargs["timeout"] == 10


@pytest.mark.parametrize("module_name", ["sonarr", "radarr", "lidarr"])
def test_arr_platforms_require_api_key_and_host(module_name):
    mod = __import__(f"dashmachine.platform.{module_name}", fromlist=["Platform"])
    assert mod.Platform(host="h", value_template="").process() == "api_key missing"
    assert mod.Platform(api_key="k", value_template="").process() == "host missing"


@pytest.mark.parametrize("module_name", ["sonarr", "radarr", "lidarr"])
def test_arr_platforms_report_api_error(module_name):
    mod = __import__(f"dashmachine.platform.{module_name}", fromlist=["Platform"])
    platform = mod.Platform(
        host="h", api_key="k", value_template="error={{ error }}"
    )
    with patch.object(
        mod.requests, "get", side_effect=_router({"/system/status": {"error": "Unauthorized"}})
    ):
        assert platform.process() == "error=Unauthorized"


@pytest.mark.parametrize("module_name", ["sonarr", "radarr", "lidarr"])
def test_arr_platforms_report_connection_error(module_name):
    mod = __import__(f"dashmachine.platform.{module_name}", fromlist=["Platform"])
    platform = mod.Platform(
        host="h", api_key="k", value_template="{{ error }}"
    )
    with patch.object(
        mod.requests, "get", side_effect=ConnectionError("no route to host")
    ):
        assert "no route to host" in platform.process()


# --------------------------------------------------------------------------- #
# Tautulli
# --------------------------------------------------------------------------- #
TAUTULLI_ROUTES = {
    "update_check": {
        "response": {"result": "success", "message": "Up to date", "data": {"update": False}}
    },
    "get_activity": {
        "response": {
            "result": "success",
            "data": {
                "stream_count": 3,
                "stream_count_direct_play": 1,
                "stream_count_direct_stream": 1,
                "stream_count_transcode": 1,
                "total_bandwidth": 9000,
                "wan_bandwidth": 4000,
            },
        }
    },
}


def test_tautulli_activity():
    from dashmachine.platform import tautulli as mod

    platform = mod.Platform(
        host="tautulli.local",
        port="8181",
        api_key="k",
        value_template="{{ stream_count }}:{{ stream_count_transcode }}:{{ update_message }}",
    )
    with patch.object(mod.requests, "get", side_effect=_router(TAUTULLI_ROUTES)):
        assert platform.process() == "3:1:Up to date"


def test_tautulli_api_error():
    from dashmachine.platform import tautulli as mod

    platform = mod.Platform(host="h", api_key="bad", value_template="{{ error }}")
    routes = {"update_check": {"response": {"result": "error", "message": "Invalid apikey"}}}
    with patch.object(mod.requests, "get", side_effect=_router(routes)):
        assert platform.process() == "Invalid apikey"


def test_tautulli_requires_credentials():
    from dashmachine.platform import tautulli as mod

    assert mod.Platform(host="h", value_template="").process() == "api_key missing"
    assert mod.Platform(api_key="k", value_template="").process() == "host missing"


# --------------------------------------------------------------------------- #
# Healthchecks
# --------------------------------------------------------------------------- #
def test_healthchecks_counts_statuses():
    from dashmachine.platform import healthchecks as mod

    payload = {
        "checks": [
            {"status": "up"},
            {"status": "up"},
            {"status": "grace"},
            {"status": "paused"},
        ]
    }
    platform = mod.Platform(
        host="hc.local",
        api_key="k",
        value_template="{{ status }} {{ count_checks }}/{{ count_up }}/{{ count_grace }}/{{ count_paused }}",
    )
    with patch.object(mod.requests, "get", side_effect=_router({"/api/v1/checks/": payload})):
        assert platform.process() == "grace 4/2/1/1"


def test_healthchecks_status_down_wins():
    from dashmachine.platform import healthchecks as mod

    payload = {"checks": [{"status": "down"}, {"status": "grace"}]}
    platform = mod.Platform(host="h", api_key="k", value_template="{{ status }}")
    with patch.object(mod.requests, "get", side_effect=_router({"/api/v1/checks/": payload})):
        assert platform.process() == "down"


def test_healthchecks_requires_credentials():
    from dashmachine.platform import healthchecks as mod

    assert mod.Platform(host="h", value_template="").process() == "api_key missing"
    assert mod.Platform(api_key="k", value_template="").process() == "host missing"


# --------------------------------------------------------------------------- #
# Plex
# --------------------------------------------------------------------------- #
def test_plex_sessions_and_libraries():
    from dashmachine.platform import plex as mod

    routes = {
        "/status/sessions": {"MediaContainer": {"size": 2}},
        "/transcode/sessions": {"MediaContainer": {"size": 1}},
        "/library/sections": {"MediaContainer": {"size": 5}},
    }
    platform = mod.Platform(
        host="http://plex.local:32400",
        token="tok",
        value_template="{{ sessions }}/{{ transcodes }}/{{ libraries }}",
    )
    with patch.object(mod.requests, "get", side_effect=_router(routes)):
        assert platform.process() == "2/1/5"


def test_plex_without_token_refuses_to_start():
    from dashmachine.platform import plex as mod

    with pytest.raises(SystemExit):
        mod.Platform(host="http://plex.local:32400", value_template="")


# --------------------------------------------------------------------------- #
# Pi-hole
# --------------------------------------------------------------------------- #
PIHOLE_SUMMARY = {
    "status": "enabled",
    "domains_being_blocked": 100000,
    "dns_queries_today": 5000,
    "ads_blocked_today": 500,
    "ads_percentage_today": 10.0,
    "unique_domains": 900,
    "queries_forwarded": 3000,
    "queries_cached": 1500,
    "clients_ever_seen": 20,
    "unique_clients": 12,
    "dns_queries_all_types": 6000,
    "gravity_last_updated": {"relative": {"days": 2}},
}


def test_pihole_summary():
    from dashmachine.platform import pihole as mod

    with patch.object(mod.requests, "get", side_effect=_router({"summary": PIHOLE_SUMMARY})):
        platform = mod.Platform(
            host="10.0.0.2",
            value_template="{{ status }} {{ blocked }}/{{ queries }} {{ ads_percentage }}",
        )
        assert platform.process() == "enabled 500/5000 10.0"


def test_pihole_authenticated_refresh_fetches_extra_endpoints():
    from dashmachine.platform import pihole as mod

    routes = {
        "summary": PIHOLE_SUMMARY,
        "getQuerySources": {"top_sources": {"a": 1}},
        "getForwardDestinations": {"forward_destinations": {}},
        "getQueryTypes": {"querytypes": {"A": 1}},
    }
    with patch.object(mod.requests, "get", side_effect=_router(routes)) as get:
        platform = mod.Platform(host="10.0.0.2", value_template="{{ status }}")
        platform.pihole.authenticate("secret")
        assert platform.process() == "enabled"

    authenticated = [c.args[0] for c in get.call_args_list if "getQuerySources" in c.args[0]]
    token = mod.Auth("secret").token
    assert "auth=" + token in authenticated[0]
    assert platform.pihole.top_devices == {"a": 1}
    assert platform.pihole.query_types == {"A": 1}


def test_pihole_helpers_require_authentication():
    from dashmachine.platform import pihole as mod

    with patch.object(mod.requests, "get", side_effect=_router({"summary": PIHOLE_SUMMARY})):
        pihole = mod.PiHole("10.0.0.2")

    for call in (lambda: pihole.refreshTop(5), pihole.getAllQueries, pihole.enable, lambda: pihole.disable(60)):
        with pytest.raises(SystemExit):
            call()


def test_pihole_other_queries():
    from dashmachine.platform import pihole as mod

    routes = {
        "summary": PIHOLE_SUMMARY,
        "overTimeData10mins": {"domains_over_time": {"1": 2}, "ads_over_time": {"1": 1}},
        "versions": {"core": {"local": {"version": "v5"}}},
        "topItems": {"top_queries": {"x": 2}, "top_ads": {"y": 1}},
        "getAllQueries": {"data": [["1", "2"]]},
        "getDBfilesize": {"filesize": "2048"},
        "?enable": {},
        "?disable": {},
    }
    with patch.object(mod.requests, "get", side_effect=_router(routes)):
        pihole = mod.PiHole("10.0.0.2")
        pihole.authenticate("secret")
        assert pihole.getGraphData() == {"domains": {"1": 2}, "ads": {"1": 1}}
        assert pihole.getVersion()["core"]["local"]["version"] == "v5"
        assert pihole.getAllQueries() == [["1", "2"]]
        assert pihole.getDBfilesize() == 2048.0
        pihole.refreshTop(5)
        assert pihole.top_queries == {"x": 2}
        pihole.enable()
        pihole.disable(60)


def test_pihole_add_and_sub_post_credentials():
    from dashmachine.platform import pihole as mod

    with patch.object(mod.requests, "get", side_effect=_router({"summary": PIHOLE_SUMMARY})):
        pihole = mod.PiHole("10.0.0.2")
    pihole.authenticate("secret")

    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    with patch.object(mod.requests, "session", return_value=session), patch.object(
        mod, "_post", return_value=Resp(text="ok")
    ) as post:
        pihole.add("white", "example.com")
        pihole.sub("black", "ads.example.com")

    assert [c.kwargs["data"] for c in post.call_args_list] == [
        {"list": "white", "domain": "example.com", "pw": "secret"},
        {"list": "black", "domain": "ads.example.com", "pw": "secret"},
    ]


# --------------------------------------------------------------------------- #
# Weather
# --------------------------------------------------------------------------- #
WEATHER = {
    "title": "Belfast",
    "consolidated_weather": [
        {
            "the_temp": 10.0,
            "min_temp": 8.0,
            "max_temp": 12.0,
            "weather_state_abbr": "c",
            "weather_state_name": "Clear",
            "wind_direction_compass": "N",
            "wind_speed": 10.0,
            "humidity": 70,
            "air_pressure": 1013.0,
            "visibility": 8.0,
            "predictability": 80,
        }
    ],
}


def test_weather_metric():
    from dashmachine.platform import weather as mod

    with patch.object(mod.requests, "get", return_value=Resp(WEATHER)) as get:
        result = mod.Platform(woeid=123).process()

    assert "Belfast" in result
    assert "10.0&deg;" in result
    assert "kph" in result
    assert get.call_args.kwargs["timeout"] == 10


def test_weather_imperial_conversions():
    from dashmachine.platform import weather as mod

    with patch.object(mod.requests, "get", return_value=Resp(WEATHER)):
        result = mod.Platform(
            temp_unit="f",
            wind_speed_unit="mph",
            air_pressure_unit="inHg",
            visibility_unit="mi",
        ).process()

    assert "50.0&deg;" in result          # 10C -> 50F
    assert "16.0 mph" in result           # 10 kph -> 16.09 mph (floored)
    assert "29.9 inHg" in result          # 1013 mbar -> 29.91
    assert "4.9 mi" in result             # 8 km -> 4.97 (floored)


def test_weather_failure_renders_error_card():
    from dashmachine.platform import weather as mod

    with patch.object(mod.requests, "get", side_effect=TimeoutError("slow")):
        result = mod.Platform().process()

    assert "Check your config" in result
    assert "slow" in result


# --------------------------------------------------------------------------- #
# Ping / curl / rest / deluge / transmission
# --------------------------------------------------------------------------- #
def test_ping_up_and_down():
    from dashmachine.platform import ping as mod

    with patch.object(mod.subprocess, "call", return_value=0) as call:
        assert "theme-success-text" in mod.Platform(resource="10.0.0.1").process()
        assert call.call_args.args[0] == ["ping", "-c", "1", "10.0.0.1"]

    with patch.object(mod.subprocess, "call", return_value=1):
        assert "theme-failure-text" in mod.Platform(resource="10.0.0.1").process()


def test_curl_plain_response():
    from dashmachine.platform import curl as mod

    with patch.object(mod.requests, "get", return_value=Resp(text="hello")) as get:
        result = mod.Platform(resource="http://x/", value_template="v={{ value }}").process()

    assert result == "v=hello"
    assert get.call_args.kwargs["timeout"] == 10


def test_rest_post_sends_payload():
    from dashmachine.platform import rest as mod

    with patch.object(mod, "post", return_value="ok") as post:
        result = mod.Platform(
            resource="http://x/",
            method="POST",
            payload="{'a': 1}",
            value_template="v={{ value }}",
        ).process()

    assert result == "v=ok"
    assert post.call_args.kwargs["data"] == {"a": 1}
    assert post.call_args.kwargs["timeout"] == 10


@pytest.mark.parametrize("authentication, auth_class", [("digest", "HTTPDigestAuth"), ("basic", "HTTPBasicAuth")])
def test_rest_authentication(authentication, auth_class):
    from dashmachine.platform import rest as mod

    response = Mock()
    response.json.return_value = {"ok": True}
    with patch.object(mod, "get", return_value=response) as get:
        mod.Platform(
            resource="http://x/",
            authentication=authentication,
            username="u",
            password="p",
            value_template="",
        ).process()

    assert get.call_args.kwargs["auth"].__class__ is getattr(mod, auth_class)


def test_rest_headers_are_parsed_from_json():
    from dashmachine.platform import rest as mod

    response = Mock()
    response.json.return_value = {}
    with patch.object(mod, "get", return_value=response) as get:
        mod.Platform(
            resource="http://x/",
            headers='{"X-Test": "1"}',
            value_template="",
        ).process()

    assert get.call_args.kwargs["headers"] == {"X-Test": "1"}


def test_deluge_stats_render():
    from dashmachine.platform import deluge as mod

    session = Mock()
    session.post.return_value = Mock(
        json=Mock(return_value={"result": {"stats": {"download_rate": 2048, "upload_rate": 512}}})
    )
    with patch.object(mod.requests, "Session", return_value=session):
        platform = mod.Platform(
            resource="http://deluge/json",
            password="secret",
            value_template="{{ download_rate }}/{{ upload_rate }}",
        )
        assert platform.process() == "2048/512"

    # the password is sent once, during login, then discarded
    assert session.post.call_args_list[0].kwargs["json"]["params"] == ["secret"]
    assert platform.password is None


def test_transmission_session_stats():
    from dashmachine.platform import transmission as mod

    fields = {
        "downloadSpeed": Mock(value=100),
        "uploadSpeed": Mock(value=50),
        "activeTorrentCount": Mock(value=2),
    }
    client = Mock()
    client.get_torrents.return_value = [1, 2, 3]
    client.session_stats.return_value = Mock(_fields=fields)
    with patch.object(mod.transmissionrpc, "Client", return_value=client) as ctor:
        platform = mod.Platform(
            host="10.0.0.3",
            user="u",
            password="p",
            value_template="{{ downloadSpeed }}/{{ uploadSpeed }}/{{ activeTorrentCount }}",
        )
        assert platform.process() == "100/50/2"

    ctor.assert_called_once_with("10.0.0.3", port=9091, user="u", password="p")
