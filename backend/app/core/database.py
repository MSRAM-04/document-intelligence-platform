from app.repositories.document_repository import repo

def init_db() -> None:
    repo.init_db()

def save_result(result: dict) -> None:
    repo.save_result(result)

def list_results() -> list[dict]:
    return repo.list_results()

def get_result(document_name: str) -> dict | None:
    return repo.get_result(document_name)
