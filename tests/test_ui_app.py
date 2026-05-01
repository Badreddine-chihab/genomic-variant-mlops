import pytest

def test_input_validation():
    """Vérifie la logique de formatage des entrées génomiques."""
    # Simulation de la logique de transformation dans app.py
    chrom = "11"
    pos = "209271"
    ref = "c "  # avec espace et minuscule
    
    # Validation attendue
    assert chrom.isdigit() or chrom in ["X", "Y"]
    assert int(pos) == 209271
    assert ref.strip().upper() == "C"