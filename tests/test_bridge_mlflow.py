import pytest
import os
from src.ui.scripts.bridge import predict_variant # Chemin mis à jour
from unittest.mock import patch

@patch('mlflow.pyfunc.load_model')
@patch('mlflow.set_tracking_uri')
def test_predict_variant_uri(mock_set_uri, mock_load):
    with patch.dict('os.environ', {'MLFLOW_TRACKING_URI': 'http://mlflow:5000'}):
        import pandas as pd
        df_dummy = pd.DataFrame({'test': [1]})
        
        predict_variant(df_dummy)
        mock_set_uri.assert_called_with("http://mlflow:5000")