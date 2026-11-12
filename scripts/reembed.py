"""Re-embed every passage in a database with another embedding model, in place.

    QANOUN_EMBED_MODEL=gemini-embedding-001 uv run --project pipeline python scripts/reembed.py \\
        --db-url postgresql://qanoun:qanoun@localhost:5433/qanoun_gemini

Used to build the database behind the live demo, whose API embeds questions with Gemini's API
instead of loading BGE-M3. Point it at a copy (`createdb -T qanoun qanoun_gemini`), not at the
database your local API uses. Vectors are cached in data/processed/embeddings as they arrive,
so an interrupted run resumes where it stopped. The model must have the column's dimension.
"""

import argparse
import os
from pathlib import Path

from qanoun_pipeline import load_db
from qanoun_pipeline.embed import Embedder, spec_for


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-url", required=True)
    args = parser.parse_args()

    spec = spec_for(os.environ.get("QANOUN_EMBED_MODEL"))
    embedder = Embedder(spec, cache_dir=Path("data/processed/embeddings"))
    with load_db.connect(args.db_url) as conn:
        dim = load_db.embedding_dim(conn)
        if dim != spec.dim:
            raise SystemExit(f"column is {dim}-dim, {spec.name} gives {spec.dim}")
        rows = conn.execute("SELECT id, text FROM chunks ORDER BY id").fetchall()
        print(f"{len(rows):,} passages → {spec.name}", flush=True)
        vectors = embedder.encode_passages([text for _, text in rows])
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE chunks SET embedding = %s WHERE id = %s",
                [(vector, chunk_id) for (chunk_id, _), vector in zip(rows, vectors, strict=True)],
            )
        conn.commit()
    print(f"updated {len(rows):,} embeddings", flush=True)


if __name__ == "__main__":
    main()
