"""Local operator CLI. No public endpoint can publish trusted configuration."""
import argparse
import json
from pathlib import Path
from .config import settings
from .store import Store
from .governance import Governance
from .knowledge import Knowledge
from .providers import embeddings_for
from .golden import load_demo_corpus, DEFAULT_CORPUS


def main():
    parser = argparse.ArgumentParser(description="Retail operator tools (requires database access)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("index", help="Embed published examples using the configured provider")
    demo = commands.add_parser("load-demo", help="Explicitly import synthetic demonstration trios")
    demo.add_argument("--file", type=Path, default=DEFAULT_CORPUS)
    candidate = commands.add_parser("candidate", help="Create a candidate from reviewed feedback")
    candidate.add_argument("--source-user", required=True)
    candidate.add_argument("--feedback-id", required=True)
    candidate.add_argument("--file", required=True, help="JSON trio file")
    review = commands.add_parser("review", help="Run expected-row cases and publish only if they pass")
    review.add_argument("--candidate", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--cases", required=True, help="JSON list of name/user/expected_rows")
    persona = commands.add_parser("persona", help="Publish presentation tone for the next turn")
    persona.add_argument("--file", required=True, help="UTF-8 plain text tone")
    persona.add_argument("--reviewer", required=True)
    args = parser.parse_args()
    config = settings(); store = Store(config.database_url); governance = Governance(config, store)
    if args.command == "index":
        try:
            config.validate_embeddings()
        except ValueError as error:
            parser.error(str(error))
        embedder = embeddings_for(config)
        if embedder is None:
            parser.error("Indexing requires an enabled embedding provider")
        result = Knowledge(store, embedder, privacy_secret=config.label_secret).index()
    elif args.command == "load-demo":
        result = load_demo_corpus(store, args.file)
    elif args.command == "candidate":
        result = {"candidate_id": governance.candidate(args.source_user, args.feedback_id, json.loads(Path(args.file).read_text()))}
    elif args.command == "review":
        result = governance.review(args.candidate, args.reviewer, json.loads(Path(args.cases).read_text()))
    else:
        result = governance.persona(Path(args.file).read_text(), args.reviewer)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
