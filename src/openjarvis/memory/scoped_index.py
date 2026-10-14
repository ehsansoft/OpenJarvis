"""Reviewed source preview and rebuildable vectors beside existing FTS memory."""

import hashlib
import json
import os
from pathlib import Path

from openjarvis.core.integration_secrets import SECRET_KEYS
from openjarvis.security.file_policy import is_sensitive_file
from openjarvis.security.file_utils import secure_write_json
from openjarvis.tools.storage._stubs import RetrievalResult
from openjarvis.tools.storage.hybrid import reciprocal_rank_fusion


class ScopedIndex:
    def __init__(self, root, sources, embedder, model_digest=None):
        self.path = Path(root) / "derived" / "scoped-vectors.json"
        self.sources = sources
        self.embedder = embedder
        self.model_digest = model_digest

    def preview(self, selected):
        if (
            not selected
            or len(selected) > 20
            or any(name not in self.sources for name in selected)
        ):
            raise ValueError("Select approved document IDs")
        rows = []
        for name in sorted(set(selected)):
            path = Path(self.sources[name])
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > 250_000
                or is_sensitive_file(path)
            ):
                raise ValueError("Source is missing, linked, sensitive or too large")
            text = path.read_text(encoding="utf-8-sig")
            if any(
                value and len(value) >= 8 and value in text
                for key in SECRET_KEYS.values()
                if (value := os.environ.get(key))
            ):
                raise ValueError("Source includes a configured secret")
            digest = hashlib.sha256(text.encode()).hexdigest()
            rows.append(
                {
                    "id": name,
                    "path": str(path.resolve()),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        return {
            "sources": rows,
            "preview_sha256": digest,
            "privacy": "local/private",
            "writes": (
                "Selected sources replace their existing FTS chunks; derived "
                "vectors are rebuildable. No project registry or schema migra"
                "tion."
            ),
        }

    def status(self):
        if not self.path.exists():
            return {"indexed": False, "mode": "lexical"}
        data = self._read()
        fresh = data.get("model_digest") == self.model_digest and all(
            name in self.sources
            and Path(self.sources[name]).is_file()
            and hashlib.sha256(
                Path(self.sources[name]).read_text(encoding="utf-8-sig").encode()
            ).hexdigest()
            == digest
            for name, digest in data["source_hashes"].items()
        )
        return {
            "indexed": True,
            "fresh": fresh,
            "chunks": len(data["chunks"]),
            "mode": "hybrid" if fresh else "lexical: stale vectors",
        }

    def _read(self):
        if self.path.is_symlink() or self.path.stat().st_size > 5_000_000:
            raise ValueError("Invalid derived index")
        return json.loads(self.path.read_text())

    def index(self, selected, approved_hash, backend):
        preview = self.preview(selected)
        if approved_hash != preview["preview_sha256"]:
            raise ValueError("Sources changed; review a fresh preview")
        by_source = {}
        chunks = []
        for source in preview["sources"]:
            path = Path(source["path"])
            text = path.read_text(encoding="utf-8-sig")
            # A character ceiling also bounds code-heavy/Persian embedding input.
            parts = [text[i : i + 1400] for i in range(0, len(text), 1400)]
            docs = [
                (
                    part,
                    {"index": i, "sha256": hashlib.sha256(part.encode()).hexdigest()},
                )
                for i, part in enumerate(parts)
            ]
            by_source[str(path)] = docs
            chunks.extend((str(path), content, meta) for content, meta in docs)
        if len(chunks) > 100:
            raise ValueError("Pilot exceeds 100 chunks; select fewer documents")
        vectors = self.embedder.embed_documents(
            [content for _, content, _ in chunks]
        ).tolist()
        if (
            not vectors
            or len(vectors) != len(chunks)
            or any(len(v) != 768 for v in vectors)
        ):
            raise ValueError("Expected installed nomic 768-dimensional vectors")
        ids = []
        for source, docs in by_source.items():
            ids.extend(backend.replace_source(source, docs))
        rows = [
            {
                "id": doc_id,
                "source": source,
                "content": content,
                "metadata": meta,
                "vector": vector,
            }
            for doc_id, (source, content, meta), vector in zip(ids, chunks, vectors)
        ]
        # Derived content duplicates only the explicitly approved FTS subset.
        secure_write_json(
            self.path,
            {
                "model": "nomic-embed-text",
                "model_digest": self.model_digest,
                "source_hashes": {r["id"]: r["sha256"] for r in preview["sources"]},
                "chunks": rows,
            },
        )
        return self.status()

    def retrieve(self, query, sparse, top_k=3):
        lexical = sparse.retrieve(query, top_k=top_k * 2)
        if not self.path.exists() or not self.status().get("fresh"):
            return lexical[:top_k]
        try:
            import numpy as np

            data = self._read()
            rows = data["chunks"]
            q = self.embedder.embed_queries([query]).reshape(-1)
            matrix = np.asarray([r["vector"] for r in rows], dtype=np.float32)
            scores = matrix @ q
            dense = [
                RetrievalResult(
                    content=rows[i]["content"],
                    score=float(scores[i]),
                    source=rows[i]["source"],
                    metadata=rows[i]["metadata"],
                )
                for i in np.argsort(scores)[::-1][: top_k * 2]
                if scores[i] >= 0.35
            ]
            return reciprocal_rank_fusion([lexical, dense])[:top_k]
        except Exception:
            return lexical[:top_k]


class ScopedSearch:
    def __init__(self, backend, index):
        self.backend = backend
        self.index = index

    def retrieve(self, query, *, top_k=3, **kwargs):
        return self.index.retrieve(query, self.backend, top_k)
