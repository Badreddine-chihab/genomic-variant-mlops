@st.cache_resource
def load_production_model():
    # 1. Utilise le NOM EXACT défini dans manager.py
    model_name = "GenomicVariantModel" 
    
    # 2. Utilise l'ALIAS avec le symbole '@' (méthode moderne)
    model_alias = "Production"
    
    try:
        # Construction de l'URI pour un Alias : models:/NOM@ALIAS
        model_uri = f"models:/{model_name}@{model_alias}"
        
        logger.info(f"📡 Tentative de chargement du modèle : {model_uri}")
        return mlflow.pyfunc.load_model(model_uri)
    except Exception as e:
        st.error(f"❌ Erreur de registre : {e}")
        # On garde le fallback local au cas où
        return None