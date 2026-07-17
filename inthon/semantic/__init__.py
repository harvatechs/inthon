"""INTHON semantic analysis package."""

from .analyzer import AnalysisFailure, SemanticAnalyzer
from .scope import Scope, Symbol

__all__ = ["SemanticAnalyzer", "AnalysisFailure", "Scope", "Symbol"]
