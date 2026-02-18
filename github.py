import argparse
import csv
import getpass
import sys
from pathlib import Path

import requests


def get_repositories(token: str):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    url = "https://api.github.com/user/repos?per_page=100"
    repos = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error fetching repositories:", response.status_code, response.text)
            return None
        data = response.json()
        repos.extend(data)
        url = response.links.get("next", {}).get("url")
    return repos


def write_sheet(repos, sheet_path: Path):
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    with sheet_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = ["full_name", "visibility", "delete"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for repo in repos:
            writer.writerow(
                {
                    "full_name": repo["full_name"],
                    "visibility": "private" if repo.get("private") else "public",
                    "delete": "No",
                }
            )
    print(f"Wrote {len(repos)} repositories to {sheet_path}. Mark rows with Yes to delete.")


def load_deletion_list(sheet_path: Path):
    if not sheet_path.exists():
        print(f"Sheet not found: {sheet_path}")
        return []
    with sheet_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        to_delete = []
        for row in reader:
            flag = (row.get("delete") or "").strip().lower()
            if flag in {"yes", "y", "true", "1"}:
                full_name = (row.get("full_name") or "").strip()
                if full_name:
                    to_delete.append(full_name)
        return to_delete


def delete_repositories(full_names, token: str):
    if not full_names:
        print("Nothing marked for deletion.")
        return
    print("Selected repositories to delete:")
    for full_name in full_names:
        print(f" - {full_name}")
    confirm = input("Type DELETE to permanently delete the above repositories: ").strip()
    if confirm != "DELETE":
        print("Aborted.")
        return
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    for full_name in full_names:
        if "/" not in full_name:
            print(f"Skipping invalid full_name: {full_name}")
            continue
        owner, name = full_name.split("/", 1)
        url = f"https://api.github.com/repos/{owner}/{name}"
        resp = requests.delete(url, headers=headers)
        if resp.status_code == 204:
            print(f"Deleted: {full_name}")
        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            print(f"Failed to delete {full_name}: {resp.status_code} {err}")


def parse_args():
    parser = argparse.ArgumentParser(description="Manage GitHub repository deletions.")
    sub = parser.add_subparsers(dest="command", required=True)

    export_cmd = sub.add_parser("export", help="Write repositories to a CSV sheet.")
    export_cmd.add_argument("sheet", type=Path, help="Path to CSV sheet to create/update.")

    apply_cmd = sub.add_parser("apply", help="Delete repositories marked Yes in the sheet.")
    apply_cmd.add_argument("sheet", type=Path, help="Path to CSV sheet to read.")

    return parser.parse_args()


def main():
    args = parse_args()
    token = getpass.getpass("Enter your GitHub Personal Access Token: ")
    if not token:
        print("A token is required.")
        sys.exit(1)

    if args.command == "export":
        repos = get_repositories(token)
        if repos is None:
            sys.exit(1)
        write_sheet(repos, args.sheet)
    elif args.command == "apply":
        full_names = load_deletion_list(args.sheet)
        delete_repositories(full_names, token)


if __name__ == "__main__":
    main()