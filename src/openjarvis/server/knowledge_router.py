"""Exact-source indexing through an explicit local preview and approval."""

from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from openjarvis.core.paths import get_config_dir
from openjarvis.memory.scoped_index import ScopedIndex
from openjarvis.server.control_router import _system, is_loopback_url, local_browser
from openjarvis.tools.storage.embeddings import OllamaEmbedder

router = APIRouter(
    prefix="/v1/control/knowledge", dependencies=[Depends(local_browser)]
)


def owned_index(request):
    if not is_loopback_url(request.app.state.config.engine.ollama.host):
        raise HTTPException(409, "Private embeddings require a loopback endpoint")
    docs = Path.cwd() / "docs"
    sources = {
        "runbook": docs / "EHSAN_PRACTICAL_WORKFLOWS.md",
        "control-desk": docs / "EHSAN_CONTROL_DESK.md",
        "architecture": docs / "EHSAN_CONTROL_PLANE_ARCHITECTURE.md",
    }
    digest = None
    try:
        with httpx.Client(trust_env=False, timeout=2) as client:
            tags = client.get(
                request.app.state.config.engine.ollama.host.rstrip("/") + "/api/tags"
            ).json()
        digest = next(
            (
                model["digest"]
                for model in tags.get("models", [])
                if model.get("name") == "nomic-embed-text:latest"
            ),
            None,
        )
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return ScopedIndex(
        get_config_dir(),
        sources,
        OllamaEmbedder(
            base_url=request.app.state.config.engine.ollama.host,
            batch_size=4,
            max_parallel=1,
        ),
        model_digest=digest,
    )


class Selection(BaseModel):
    sources: list[str] = Field(min_length=1, max_length=20)
    preview_sha256: str = ""
    approved: bool = False


@router.get("")
def status(request: Request):
    index = owned_index(request)
    return {
        "sources": [
            {"id": name, "name": path.name} for name, path in index.sources.items()
        ],
        **index.status(),
    }


@router.post("/preview")
def preview(body: Selection, request: Request):
    try:
        return owned_index(request).preview(body.sources)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/index")
def index_sources(body: Selection, request: Request):
    if not body.approved:
        raise HTTPException(403, "Review the exact source preview before indexing")
    system = _system(request)
    with request.app.state._control_chat_lock:
        try:
            index = owned_index(request)
            if not index.model_digest:
                raise ValueError(
                    "Installed nomic metadata is unavailable; no download attempted"
                )
            return index.index(body.sources, body.preview_sha256, system.memory_backend)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except Exception:
            raise HTTPException(
                503,
                "Local indexing did not complete; check Ollama and local status. "
                "No model was downloaded.",
            ) from None
