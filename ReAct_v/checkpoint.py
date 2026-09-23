import json
from pathlib import Path

CHECKPOINT_DIR = Path("./checkpoint")

CHECKPOINT_DIR.mkdir(
    exist_ok=True
)

class CheckpointStore:
    def save(self, task_id, status):
        data = {
            "task_id": task_id,
            "step": status.step,
            "status": status.status,
            "max_steps": status.max_steps,
            "messages": status.messages,
            "pending_results": status.pending_results,
            "last_message": (
                status.last_message.model_dump()
                if status.last_message is not None
                else
                None
                )
        }

        path = CHECKPOINT_DIR / f"{task_id}.json"

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

    def load(self, task_id):
        path = CHECKPOINT_DIR / f"{task_id}.json"

        if not path.exists():
            return None

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return data
    
    def delete(self, task_id):
        path = CHECKPOINT_DIR / f"{task_id}.json"

        if path.exists():
            path.unlink()

    def list_all(self):
        records = []
        for path in CHECKPOINT_DIR.glob("*.json"):
            try:
                data = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            data["_updated_at"] = path.stat().st_mtime
            records.append(data)
        records.sort(
            key=lambda item: item["_updated_at"],
            reverse=True,
        )
        return records