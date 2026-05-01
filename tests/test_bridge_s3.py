import pytest
from src.ui.scripts.bridge import get_s3_connection, fetch_features_from_s3 # Chemin mis à jour
from unittest.mock import patch, MagicMock

def test_get_s3_connection_local():
    with patch.dict('os.environ', {}, clear=True):
        with patch('duckdb.connect') as mock_connect:
            con = get_s3_connection()
            mock_connect.return_value.execute.assert_any_call("CALL load_aws_credentials();")

def test_fetch_features_error_handling():
    # CORRECTION ICI : Le chemin complet doit être utilisé pour le mock
    with patch('src.ui.scripts.bridge.get_s3_connection') as mock_conn:
        mock_conn.side_effect = Exception("S3 Connection Timeout")
        result = fetch_features_from_s3("1", 12345, "C", "A")
        assert result is None