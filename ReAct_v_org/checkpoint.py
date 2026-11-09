import json
import os
import re
import tempfile
from builtins import FileNotFoundError
from pathlib import Path


DEFAULT_CHECKPOINT_DIR = Path(__file__).parent / "checkpoint"

class CheckpointStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else DEFAULT_CHECKPOINT_DIR
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r"[\w.-]{1,100}", task_id, re.UNICODE):
            raise ValueError("非法 task_id，只允许字母、数字、下划线、短横线和点")
        return self.directory / f"{task_id}.json"

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

        path = self._path(task_id)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.stem}.",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(data, temp_file, ensure_ascii=False, indent=4)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def load(self, task_id):
        path = self._path(task_id)

        if not path.exists():
            return None

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return data
    
    def delete(self, task_id):
        path = self._path(task_id)

        if path.exists():
            path.unlink()

    def list_all(self):
        records = []
        for path in self.directory.glob("*.json"):
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
