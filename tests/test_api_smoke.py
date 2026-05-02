import asyncio
import importlib
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd


class DummyModel:
    def predict(self, df):
        return np.array([0])

    def predict_proba(self, df):
        return np.array([[0.82, 0.18]])


class DummyXGBModel(DummyModel):
    pass


class DummyUploadFile:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def load_api_module():
    sys.modules.pop("src.api.main", None)
    sys.modules.pop("src.api", None)

    with patch("mlflow.pyfunc.load_model", return_value=DummyModel()), patch(
        "mlflow.xgboost.load_model", return_value=DummyXGBModel()
    ):
        return importlib.import_module("src.api.main")


def test_health_and_predict_smoke():
    api = load_api_module()

    health = api.health()
    assert health["model_status"] == "loaded"

    pred = api.predict_enhanced(api.VariantInput(chrom="11", pos="209271", ref="C", alt="A"))
    assert pred.status == "success"
    assert pred.prediction == 0
    assert 0.0 <= pred.probability <= 1.0
    assert 0.0 <= pred.confidence_score <= 1.0


def test_vcf_upload_and_batch_predict_smoke():
    api = load_api_module()

    vcf = (
        b"##fileformat=VCFv4.2\n"
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        b"11\t209271\t.\tC\tA,T\t.\tPASS\t.\n"
        b"1\t12345\t.\tA\tG\t.\tPASS\t.\n"
    )

    upload = asyncio.run(api.upload_vcf(DummyUploadFile("sample.vcf", vcf), limit=10))
    assert upload.found is True
    assert upload.total_records == 3

    feature_df = pd.DataFrame(
        [
            {
                "#chr": "11",
                "pos(1-based)": 209271,
                "ref": "C",
                "alt": "A",
                "SIFT_score": 0.1,
                "Polyphen2_HVAR_score": 0.2,
                "CADD_phred": 23.0,
                "gnomAD_exomes_AF": 0.0001,
            }
        ]
    )

    def fake_fetch(chrom, pos, ref, alt):
        if str(chrom) == "11" and str(pos) == "209271" and ref == "C" and alt == "A":
            return feature_df
        return pd.DataFrame()

    with patch("src.ui.scripts.bridge.fetch_features_from_s3", side_effect=fake_fetch):
        batch = api.vcf_batch_predict(
            api.VCFBatchPredictRequest(
                records=[
                    api.VCFVariantInput(chrom="11", pos="209271", ref="C", alt="A"),
                    api.VCFVariantInput(chrom="1", pos="12345", ref="A", alt="G"),
                ],
                max_records=10,
            )
        )

    assert batch.status == "success"
    assert batch.processed == 2
    assert batch.predicted == 1
    assert batch.not_found == 1
    assert batch.failed == 0

    first = batch.results[0]
    assert first.status == "predicted"
    assert first.label == "BENIGN"
    assert 0.0 <= first.probability <= 1.0
