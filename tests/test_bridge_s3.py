import pytest
from src.bridge import get_s3_connection, fetch_features_from_s3
from unittest.mock import patch, MagicMock

def test_get_s3_connection_local():
    """Vérifie que la connexion bascule en mode local si les variables d'env sont absentes."""
    with patch.dict('os.environ', {}, clear=True):
        with patch('duckdb.connect') as mock_connect:
            con = get_s3_connection()
            # Vérifie qu'on tente de charger les credentials AWS locaux
            mock_connect.return_value.execute.assert_any_call("CALL load_aws_credentials();")

def test_fetch_features_error_handling():
    """Vérifie que la fonction gère proprement les erreurs de connexion S3."""
    with patch('src.bridge.get_s3_connection') as mock_conn:
        mock_conn.side_effect = Exception("S3 Connection Timeout")
        result = fetch_features_from_s3("1", 12345, "C", "A")
        assert result is None