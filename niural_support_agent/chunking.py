"""Split the product guide at Markdown section boundaries."""

from hashlib import sha256
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter
from pydantic import BaseModel, ConfigDict


GUIDE_PATH = Path(__file__).resolve().parents[1] / "mock_api" / "PRODUCT_GUIDE.md"


class GuideChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str
    source: str
    section: str
    heading_path: str
    text: str

    @property
    def embedding_text(self) -> str:
        return f"{self.heading_path}\n\n{self.text}"


def chunk_product_guide(path: Path = GUIDE_PATH) -> list[GuideChunk]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "part"), ("##", "section")],
        strip_headers=False,
    )
    documents = splitter.split_text(path.read_text(encoding="utf-8"))
    chunks = []
    for document in documents:
        headings = [document.metadata[key] for key in ("part", "section")
                    if key in document.metadata]
        heading_path = " > ".join(headings) or "Introduction"
        identifier = sha256(f"{path.name}:{heading_path}".encode("utf-8")).hexdigest()[:16]
        chunks.append(GuideChunk(
            section_id=f"guide-{identifier}",
            source=path.name,
            section=headings[-1] if headings else "Introduction",
            heading_path=heading_path,
            text=document.page_content,
        ))
    if len({chunk.section_id for chunk in chunks}) != len(chunks):
        raise ValueError("Duplicate heading paths; section IDs must be unique")
    return chunks


if __name__ == "__main__":
    chunks = chunk_product_guide()
    print(f"{len(chunks)} sections")
    for chunk in chunks:
        print(f"{chunk.section_id} | {len(chunk.text):4} chars | {chunk.heading_path}")
