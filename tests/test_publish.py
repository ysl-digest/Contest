from contest_digest import publish


class Resp:
    def __init__(self, data=None):
        self.data = data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_publish_calls(monkeypatch):
    calls = []

    def fake(method):
        def f(url, headers, timeout, json=None):
            calls.append((method, url, json, headers["Authorization"]))
            return Resp({"number": 3, "expires_at": "2027-04-27T00:00:00Z"})
        return f

    monkeypatch.setattr(publish.requests, "post", fake("POST"))
    monkeypatch.setattr(publish.requests, "put", fake("PUT"))
    repo = "yeseo-bot/Contest-Subscribe"
    assert publish.create_issue("t", repo, "제목", "본문", ["digest"]) == 3
    publish.lock_issue("t", repo, 3)
    assert publish.renew_interaction_limit("t", repo) == "2027-04-27T00:00:00Z"
    assert [c[:2] for c in calls] == [
        ("POST", f"https://api.github.com/repos/{repo}/issues"),
        ("PUT", f"https://api.github.com/repos/{repo}/issues/3/lock"),
        ("PUT", f"https://api.github.com/repos/{repo}/interaction-limits"),
    ]
    assert calls[2][2] == {"limit": "collaborators_only", "expiry": "six_months"}
    assert all(c[3] == "Bearer t" for c in calls)
