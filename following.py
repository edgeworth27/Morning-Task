"""Read an X account's following list; never changes briefing sources or follows."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode

from briefing import BriefingError, HTTP, UTC, iso, report_error, require


def lookup(http, token, handle):
    handle = handle.removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise BriefingError("Invalid X username")
    profile = http.request("GET", f"https://api.x.com/2/users/by/username/{handle}", token=token)
    if profile.get("errors") or not profile.get("data", {}).get("id"):
        raise BriefingError("X could not resolve the requested account")
    user = profile["data"]
    if not str(user["id"]).isdigit():
        raise BriefingError("X returned an invalid user ID")
    accounts, seen_tokens = {}, set()
    params = {"max_results": 1000}
    while True:
        result = http.request("GET", f"https://api.x.com/2/users/{user['id']}/following?" + urlencode(params), token=token)
        if result.get("errors"):
            raise BriefingError("X following lookup returned partial errors; no complete-list claim is possible")
        for account in result.get("data", []):
            if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", account.get("username", "")):
                raise BriefingError("X returned an invalid account username")
            accounts[account["id"]] = {k: account[k] for k in ("id", "username", "name")}
        next_token = result.get("meta", {}).get("next_token")
        if not next_token:
            return {"account": user, "retrieved_at": iso(datetime.now(UTC)), "complete": True,
                    "count": len(accounts), "following": list(accounts.values())}
        if next_token in seen_tokens:
            raise BriefingError("X repeated a following-list pagination token")
        seen_tokens.add(next_token)
        params["pagination_token"] = next_token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handle")
    args = parser.parse_args()
    try:
        result = lookup(HTTP(), require("X_BEARER_TOKEN"), args.handle)
        Path("out").mkdir(exist_ok=True)
        Path("out/following.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        message = f"Following lookup complete: @{result['account']['username']} follows {result['count']} API-visible accounts."
        sample = "Sample: " + ", ".join("@" + a["username"] for a in result["following"][:20])
        print(message)
        print(sample)
        if os.getenv("GITHUB_ACTIONS") == "true":
            print("::notice::" + message)
            print("::notice::" + sample)
    except (BriefingError, ValueError, KeyError, TypeError) as exc:
        report_error(f"Following lookup failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
