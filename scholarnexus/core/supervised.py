"""可选的轻量监督校准器。

只允许在开发集拟合，模型文件记录特征、均值、标准差和逻辑回归参数；线上只做
一次矩阵乘法。没有模型文件时，主链路继续使用零标注混合校准，不会失效。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Sequence

import numpy as np


FEATURES = ("rrf", "graph", "constraint", "l1", "l2", "l3",
            "channels", "citation_log", "recency")


def feature_matrix(cands: Sequence, current_year: int = 2026) -> np.ndarray:
    rows = []
    for cand in cands:
        paper = cand.paper
        rows.append([
            float(cand.s_rrf or 0.0), float(cand.s_graph or 0.0),
            float(cand.s_constraint or 0.0), float(cand.s_l1 or 0.0),
            float(cand.s_l2 if cand.s_l2 is not None else cand.s_l1 or 0.0),
            float(cand.s_l3 if cand.s_l3 is not None else cand.s_l2
                  if cand.s_l2 is not None else cand.s_l1 or 0.0),
            float(min(len(cand.channels), 8)) / 8.0,
            math.log1p(max(int(paper.citation_count or 0), 0)) / 10.0,
            max(0.0, min(1.0, 1.0 - (current_year - int(paper.year or current_year)) / 15.0)),
        ])
    return np.asarray(rows, dtype=np.float64)


@dataclass
class FeatureCalibrator:
    coef: np.ndarray
    intercept: float
    mean: np.ndarray
    scale: np.ndarray
    blend: float = 0.65
    source: str = ""

    @classmethod
    def load(cls, path: str) -> "FeatureCalibrator | None":
        if not path or not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as stream:
            data: Dict[str, Any] = json.load(stream)
        if tuple(data.get("features") or ()) != FEATURES:
            raise ValueError("监督校准器特征版本不兼容")
        coef = np.asarray(data["coef"], dtype=np.float64)
        mean = np.asarray(data.get("mean", [0.0] * len(FEATURES)), dtype=np.float64)
        scale = np.asarray(data.get("scale", [1.0] * len(FEATURES)), dtype=np.float64)
        if len(coef) != len(FEATURES):
            raise ValueError("监督校准器参数长度错误")
        return cls(coef=coef, intercept=float(data.get("intercept", 0.0)),
                   mean=mean, scale=np.maximum(scale, 1e-8),
                   blend=float(data.get("blend", 0.65)), source=path)

    def predict(self, cands: Sequence, current_year: int = 2026) -> np.ndarray:
        x = feature_matrix(cands, current_year)
        z = ((x - self.mean) / self.scale) @ self.coef + self.intercept
        z = np.clip(z, -40.0, 40.0)
        return 1.0 / (1.0 + np.exp(-z))

    def combine(self, unsupervised: np.ndarray, cands: Sequence,
                current_year: int = 2026) -> np.ndarray:
        supervised = self.predict(cands, current_year)
        weight = min(max(self.blend, 0.0), 1.0)
        return np.clip(weight * supervised + (1.0 - weight) * unsupervised,
                       1e-4, 1 - 1e-4)
