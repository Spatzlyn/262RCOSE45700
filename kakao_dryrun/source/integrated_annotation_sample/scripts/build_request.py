#!/usr/bin/env python3
"""Build a multimodal chat-style request locally; --send is explicitly opt-in.

The payload uses a common messages/image_url interface. Check the selected
server's interface and supported model before sending; no vendor is assumed.
Only the selected input image, task specification, prompt and output schema
are read. Source annotations and reference labels are never loaded here.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def resolve_output(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Model identifier understood by your server")
    parser.add_argument("--item-id", default="sample_front_001")
    parser.add_argument("--out", default="runs/request.json")
    parser.add_argument("--send", action="store_true", help="Actually send the image to the explicit endpoint")
    parser.add_argument("--endpoint", help="Full chat-compatible HTTP endpoint, including its request path")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    items = [json.loads(line) for line in (ROOT / "data/items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [item for item in items if item["item_id"] == args.item_id]
    if len(selected) != 1:
        parser.error("item_id must select exactly one item")
    item = selected[0]
    image_path = (ROOT / item["image_path"]).resolve()
    if not image_path.is_relative_to((ROOT / "images").resolve()) or image_path.suffix.lower() != ".png":
        parser.error("Only a PNG inside this package's images directory can be sent")
    # Whitelist input fields; annotations or accidental extra metadata in items
    # cannot enter the request through generic dictionary serialization.
    task = {key: item[key] for key in ("item_id", "view", "intent", "task", "input_type")}
    for key in ("evaluation_area_definition", "available_evidence", "question"):
        if key in item:
            task[key] = item[key]
    schema = json.loads((ROOT / "schema/prediction.schema.json").read_text(encoding="utf-8"))
    prompt = (ROOT / "prompts/system.txt").read_text(encoding="utf-8")
    task_text = "Return one JSON object for this task.\n" + json.dumps(task, ensure_ascii=False)
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": prompt + "\n\nOutput JSON Schema:\n" + json.dumps(schema, ensure_ascii=False)},
            {"role": "user", "content": [
                {"type": "text", "text": task_text},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")}},
            ]},
        ],
    }
    output = resolve_output(args.out)
    save_json(output, payload)
    if not args.send:
        print(json.dumps({"request_file": str(output), "sent": False, "item_id": args.item_id}, ensure_ascii=False))
        return
    if not args.endpoint:
        parser.error("--send requires --endpoint; no default external service is used")
    url = urllib.parse.urlparse(args.endpoint)
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
        parser.error("Use HTTPS, or HTTP only for a loopback model server")
    if url.username or url.password:
        parser.error("Do not put credentials in the endpoint URL; use API_KEY")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("API_KEY")
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(args.endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    # Explicit endpoint only: prevent redirects from forwarding an image/key.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=args.timeout) as response:
        raw = json.load(response)
    raw_path = output.parent / "response.raw.json"
    save_json(raw_path, raw)
    try:
        content = raw["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        content = content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        prediction = json.loads(content)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f"Response saved to {raw_path}; could not extract JSON prediction. Check server format.") from exc
    prediction_path = output.parent / "prediction.json"
    save_json(prediction_path, prediction)
    print(json.dumps({"request_file": str(output), "sent": True, "raw_response": str(raw_path), "prediction": str(prediction_path), "validation": "not_yet_run"}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"HTTP request failed (status {exc.code}); no retry was performed.", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
