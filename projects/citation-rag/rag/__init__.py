"""citation-rag: retrieval that cites its sources and refuses to guess.

Public API:
    from rag import Retriever, answer, load_corpus
"""
from .retriever import Retriever, Chunk
from .answer import answer, Answer
from .corpus import load_corpus

__all__ = ["Retriever", "Chunk", "answer", "Answer", "load_corpus"]
