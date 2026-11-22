"""Configure a dedicated local WebUI; never print credentials/tokens."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.fixture"))
    parser.add_argument("--webui-url", default="http://127.0.0.1:3000")
    parser.add_argument("--login-script", type=Path, help="Optional private browser login helper; delete after use")
    parser.add_argument("--reports", action="store_true", help="Install Reports library API and native Action (requires Reports image overlay)")
    parser.add_argument("--compose-local", action="store_true", help="Allow the private http://webui:8080 Compose service and live backend")
    args = parser.parse_args()
    config = dotenv_values(args.env_file)
    url = urlparse(args.webui_url)
    local = url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
    compose = args.compose_local and args.webui_url == "http://webui:8080"
    if not (local or compose) or (config.get("RETAIL_MODE") != "fixture" and not args.compose_local):
        parser.error("Bootstrap requires a dedicated local WebUI; Compose live setup needs --compose-local")
    email, password = config["WEBUI_ADMIN_EMAIL"], config["WEBUI_ADMIN_PASSWORD"]
    id = "retail_assessment_pipe"
    experience = json.loads((Path(__file__).parents[1] / "integrations/webui_report_experience.json").read_text())
    form = {"id": id, "name": experience["name"], "content": (Path(__file__).parents[1] / "integrations/openwebui_pipe.py").read_text(),
        "meta": {"description": "Authorized retail analysis via the shared LangGraph backend"}}
    with httpx.Client(base_url=args.webui_url, timeout=90) as client:
        response = client.post("/api/v1/auths/signin", json={"email": email, "password": password})
        if response.status_code != 200:
            response = client.post("/api/v1/auths/signup", json={"name": "Retail Demo", "email": email, "password": password})
        response.raise_for_status()
        auth = response.json()
        if auth.get("role") != "admin":
            raise RuntimeError("The local account is not an administrator")
        client.headers["Authorization"] = "Bearer " + auth["token"]
        existing = client.get("/api/v1/functions/list"); existing.raise_for_status()
        present = next((f for f in existing.json() if f["id"] == id), None)
        endpoint = f"/api/v1/functions/id/{id}/update" if present else "/api/v1/functions/create"
        function = client.post(endpoint, json=form); function.raise_for_status()
        if not function.json()["is_active"]:
            toggled = client.post(f"/api/v1/functions/id/{id}/toggle"); toggled.raise_for_status()
        valves = client.post(f"/api/v1/functions/id/{id}/valves/update",
            json={"API_URL": "http://api:8000", "ADAPTER_SECRET": config["ADAPTER_SECRET"]})
        valves.raise_for_status()
        suggestions = client.post("/api/v1/configs/suggestions", json={"suggestions": experience["suggestions"]})
        suggestions.raise_for_status()
        current = client.get("/api/v1/users/user/settings"); current.raise_for_status()
        preferences = current.json() or {}
        preferences["ui"] = {**(preferences.get("ui") or {}), "collapseCodeBlocks": True}
        updated = client.post("/api/v1/users/user/settings/update", json=preferences)
        updated.raise_for_status()
        if args.reports:
            from install_webui_reports import install
            install(client, Path(__file__).parents[1])
        mapping = json.loads(config.get("WEBUI_USERS_JSON", "{}")); mapping[auth["id"]] = "alice"
        set_key(str(args.env_file), "WEBUI_USERS_JSON", json.dumps(mapping))
        if args.login_script:
            args.login_script.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            script = '''const p = await browser.getPage("main");
await p.goto(URL_VALUE + "/auth");
const result = await p.evaluate(async (credentials) => {
  const response = await fetch("/api/v1/auths/signin", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(credentials)});
  if (!response.ok) return {ok:false,status:response.status};
  const data = await response.json(); localStorage.setItem("token",data.token);
  return {ok:true,role:data.role};
}, CREDENTIALS_VALUE);
if (!result.ok) throw new Error("Fixture sign-in failed: " + result.status);
await p.goto(URL_VALUE);
({authenticated:true,url:p.url()});
'''.replace("URL_VALUE", json.dumps(args.webui_url)).replace("CREDENTIALS_VALUE", json.dumps({"email": email, "password": password}))
            fd = os.open(args.login_script, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as file:
                file.write(script)
        print(json.dumps({"configured": True, "pipe_id": id, "backend_identity": "alice",
            "restart_api_required": True, "credentials": "not displayed"}))


if __name__ == "__main__":
    main()
