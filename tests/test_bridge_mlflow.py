import pytest
import os
from src.bridge import predict_variant
from unittest.mock import patch

@patch('mlflow.pyfunc.load_model')
@patch('mlflow.set_tracking_uri')
def test_predict_variant_uri(mock_set_uri, mock_load):
    """Vérifie que le tracking URI pointe bien vers le service Docker 'mlflow'."""
    with patch.dict('os.environ', {'MLFLOW_TRACKING_URI': 'http://mlflow:5000'}):
        import pandas as pd
        df_dummy = pd.DataFrame({'test': [1]})
        
        predict_variant(df_dummy)
        
        # Vérifie que l'URI utilisé est celui du réseau interne Docker
        mock_set_uri.assert_called_with("http://mlflow:5000")