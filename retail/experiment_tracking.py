"""Explicit offline experiment export; serving telemetry stays metadata-only."""
import hashlib
import json
import math

from .security import safe_output


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def tracking_payload(run_id, sample, result, metadata, capture=False):
    if capture and sample.get("source") != "synthetic":
        raise ValueError("Detailed capture requires explicitly synthetic evidence.")
    scores = {}
    for name, score in result.get("metrics", {}).items():
        if score.get("status") != "measured" or score.get("source") != "ragas":
            continue
        value = score.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid measured score.")
        scores[name] = value
    # Caller metadata is allowlisted: arbitrary dictionaries may contain evidence/secrets.
    facts = {key: metadata[key] for key in (
        "prompt_sha256", "dataset_sha256", "model", "judge_model", "split",
        "family", "metric_contract", "serving_prompt", "evidence_boundary") if key in metadata}
    facts.update(run_id=run_id, case_id=sample["id"], sample_sha256=digest(sample),
                 capture="synthetic" if capture else "metadata_only")
    payload = {"trace_id": digest([run_id, sample["id"]])[:32], "metadata": facts,
               "input": {"case_id": sample["id"], "sample_sha256": digest(sample)},
               "output": {"response_sha256": digest(sample.get("response", ""))}, "scores": scores}
    if capture:
        safe_output(json.dumps(sample))
        payload.update(input={"question": sample["question"], "contexts": sample.get("sql_contexts", [])},
                       output=sample.get("response", ""))
    return payload


def export_case(client, dataset_name, run_id, sample, result, metadata, capture=False):
    payload = tracking_payload(run_id, sample, result, metadata, capture)
    client.create_dataset(name=dataset_name, metadata={"evidence_boundary": "Offline experiment; scores are not overall accuracy."})
    # Content-bound item identity prevents overwriting another dataset revision.
    item = client.create_dataset_item(dataset_name=dataset_name,
        id=digest([dataset_name, sample["id"], metadata.get("dataset_sha256")]),
        input=payload["input"], metadata=payload["metadata"])
    link = client.api.dataset_run_items.create(run_name=run_id, dataset_item_id=item.id,
        trace_id=payload["trace_id"], metadata=payload["metadata"])
    with client.start_as_current_observation(name="retail-evaluation", as_type="evaluator",
            trace_context={"trace_id": payload["trace_id"]}, input=payload["input"],
            output=payload["output"], metadata=payload["metadata"]) as observation:
        # SDK 4.18.0's experiment runner emits these same attributes. v4 reads
        # experiment membership from OTEL; the legacy run-item record alone is
        # insufficient. Kept here to import existing scores without judge calls.
        observation._otel_span.set_attributes({
            "langfuse.experiment.id": link.dataset_run_id,
            "langfuse.experiment.name": run_id,
            "langfuse.experiment.dataset.id": item.dataset_id,
            "langfuse.experiment.item.id": item.id,
            "langfuse.experiment.item.root_observation_id": observation.id,
            "langfuse.environment": "experiment"})
        for name, value in payload["scores"].items():
            client.create_score(trace_id=payload["trace_id"], name=name, value=value,
                score_id=digest([run_id, sample["id"], name]), data_type="NUMERIC",
                metadata={"contract": metadata.get("metric_contract", "ragas-0.4.4-standard-and-separate-sql-aware")})
    client.flush()
    return {"trace_id": payload["trace_id"], "score_count": len(payload["scores"])}
