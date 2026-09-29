"""Sync a config to skilltest-project on <branch>; exit 0 if SignalFlag accepts it. `sync_check.py <config> <branch>`."""
import sys
from pathlib import Path
from signalflag.sdk.auth import DeviceCodeClient
from signalflag.sdk.bff_client import metrics
from signalflag.sdk.client.api.projects import list_projects

PROJECT = "skilltest-project"


def project_id(client) -> str:
    token = None
    while True:
        page = list_projects.sync(client=client, **({"page_token": token} if token else {}))
        hit = next((str(p.project_id) for p in page.projects if p.name == PROJECT), None)
        if hit or not page.next_page_token:
            return hit or sys.exit(f"project {PROJECT!r} not found")
        token = page.next_page_token


if __name__ == "__main__":
    config = Path(sys.argv[1])
    client = DeviceCodeClient()
    metrics.sync_config(client, project_id(client), sys.argv[2], config_path=str(config),
                        templates_path=str(config.parent / "templates"))
    print("accepted")
