"""Required CLI; all product operations go through the same HTTP API as WebUI."""
import argparse
import json
import os
import sys
import httpx


def main():
    parser = argparse.ArgumentParser(description="Retail analysis CLI")
    parser.add_argument("--url", default=os.getenv("RETAIL_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.getenv("RETAIL_API_TOKEN", ""), help="Prefer RETAIL_API_TOKEN to shell history")
    parser.add_argument("--conversation", default=None)
    parser.add_argument("--json", action="store_true", help="Print structured final responses")
    parser.add_argument("--once", metavar="QUESTION", help="Run a single turn")
    args = parser.parse_args()
    if not args.token:
        parser.error("Set RETAIL_API_TOKEN to a configured application token")
    conversation = args.conversation
    with httpx.Client(base_url=args.url, headers={"Authorization": f"Bearer {args.token}"}, timeout=150) as client:
        def turn(message):
            nonlocal conversation
            with client.stream("POST", "/chat/stream", json={"message": message, "conversation_id": conversation}) as response:
                if response.status_code != 200:
                    response.read()
                    print("Request rejected: " + str(response.status_code), file=sys.stderr)
                    return False
                event_type, data = "", []
                for line in response.iter_lines():
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        event = json.loads("\n".join(data))
                        data = []
                        if event_type == "progress":
                            print(f"[{event['stage']}: {event.get('outcome', 'running')}]", file=sys.stderr)
                        elif event_type == "error":
                            print(event["detail"], file=sys.stderr)
                            return False
                        elif event_type == "result":
                            conversation = event["conversation_id"]
                            print(json.dumps(event, indent=2) if args.json else event["answer"])
                            print(f"Conversation: {conversation} | trace: {event['trace_id']} | {event['mode']}", file=sys.stderr)
                            return True
            print("Connection ended before a final response; check saved state before retrying.", file=sys.stderr)
            return False

        try:
            if args.once is not None:
                if not turn(args.once):
                    raise SystemExit(1)
                return
            print("Retail chat. /quit exits; /confirm ID or /cancel ID handles a deletion preview.")
            while True:
                question = input("you> ").strip()
                if question in {"/quit", "/exit"}:
                    break
                if question:
                    turn(question)
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
        except httpx.HTTPError:
            print("API unavailable or timed out. Check the service and saved state before retrying.", file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
