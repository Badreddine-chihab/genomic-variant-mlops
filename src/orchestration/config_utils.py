import logging
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from omegaconf import OmegaConf, DictConfig

logger = logging.getLogger(__name__)

# --- 1. ENREGISTREMENT DU TAG PERSONNALISÉ ---
def load_config_constructor(loader, node):
    """
    Déclenché quand YAML voit '!load_config'.
    Charge le sous-fichier et l'insère dans la config parente.
    """
    value = loader.construct_scalar(node)
    # On récupère le dossier où se trouve le fichier config actuel
    # loader.name contient le chemin du fichier en cours de lecture
    config_dir = Path(loader.name).parent
    target_path = config_dir / value
    
    if not target_path.exists():
        raise FileNotFoundError(f"❌ Sous-config introuvable : {target_path}")
    
    # On lit le sous-fichier
    with open(target_path, 'r') as f:
        return yaml.safe_load(f)

# On dit à PyYAML d'utiliser notre fonction pour !load_config
yaml.SafeLoader.add_constructor('!load_config', load_config_constructor)

# --- 2. CLASSE DE GESTION ---
class ConfigManager:
    def __init__(self, config_path: Optional[str] = None, project_root: Optional[Path] = None):
        self.project_root = project_root or self._find_project_root()
        self.config = self._load_config(config_path)
        
    def _find_project_root(self) -> Path:
        """Trouve la racine du projet (là où se trouve le dossier config/)"""
        current = Path.cwd().resolve()
        # On remonte jusqu'à trouver le dossier 'config'
        for parent in [current] + list(current.parents):
            if (parent / "config").exists():
                return parent
        return current
    
    def _load_config(self, config_path: Optional[str]) -> DictConfig:
        """Charge la config en utilisant yaml d'abord, puis OmegaConf."""
        if config_path:
            path = Path(config_path)
            if not path.is_absolute():
                path = self.project_root / path
        else:
            path = self.project_root / "config" / "config.yaml"
        
        if not path.exists():
            logger.warning(f"⚠️ Config non trouvée à {path}")
            return OmegaConf.create({})

        logger.info(f"📂 Chargement de la configuration : {path}")

        # --- LA CORRECTION EST ICI ---
        # Au lieu de OmegaConf.load(), on utilise yaml.safe_load()
        with open(path, 'r') as f:
            # PyYAML va appeler load_config_constructor quand il verra !load_config
            raw_dict = yaml.safe_load(f)
            # On transforme le dictionnaire Python en objet OmegaConf
            return OmegaConf.create(raw_dict)
        # -----------------------------

    def get_path(self, path_key: str, as_absolute: bool = True) -> Path:
        value = OmegaConf.select(self.config, path_key)
        if value is None:
            raise ValueError(f"Clé de chemin introuvable : {path_key}")
        path = Path(value)
        if as_absolute and not path.is_absolute():
            path = self.project_root / path
        return path

    def get(self, key: str, default: Any = None) -> Any:
        return OmegaConf.select(self.config, key, default=default)

    def set_logging(self, level: str = "INFO"):
        log_level = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

def setup_mlflow(config: DictConfig):
    import mlflow
    uri = config.get("mlflow.tracking_uri", "sqlite:///mlflow.db")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(config.get("mlflow.experiment_name", "genomic_pfa"))