import pandas as pd
import os

def clean_and_split_clinvar(input_csv, output_train_csv, output_vus_csv):
    print(f"Chargement des données depuis {input_csv}...")
    df = pd.read_csv(input_csv)
    
    # Définition des règles de mapping
    pathogenic_labels = ['Pathogenic', 'Likely_pathogenic', 'Pathogenic/Likely_pathogenic']
    benign_labels = ['Benign', 'Likely_benign', 'Benign/Likely_benign']
    
    print("Filtrage et encodage binaire des labels...")
    
    # Création du dataset d'entraînement (données avec label clair)
    df_train = df[df['CLNSIG'].isin(pathogenic_labels + benign_labels)].copy()
    
    # Création de la cible binaire (1 = Pathogène, 0 = Bénin)
    df_train['Target'] = df_train['CLNSIG'].apply(lambda x: 1 if x in pathogenic_labels else 0)
    
    # Suppression de l'ancienne colonne texte
    df_train = df_train.drop(columns=['CLNSIG'])
    
    # Isolation des VUS pour l'inférence future
    df_vus = df[df['CLNSIG'] == 'Uncertain_significance'].copy()
    
    # Sauvegarde des datasets
    os.makedirs(os.path.dirname(output_train_csv), exist_ok=True)
    df_train.to_csv(output_train_csv, index=False)
    df_vus.to_csv(output_vus_csv, index=False)
    
    print("-" * 40)
    print(f"Dataset d'entraînement généré : {len(df_train)} variants.")
    print(f"  -> Pathogènes (1) : {len(df_train[df_train['Target'] == 1])}")
    print(f"  -> Bénins (0) : {len(df_train[df_train['Target'] == 0])}")
    print(f"Dataset des VUS isolé : {len(df_vus)} variants.")
    print("-" * 40)
    print(f"Fichiers sauvegardés : \n- {output_train_csv}\n- {output_vus_csv}")

if __name__ == "__main__":
    input_file = "data/processed/clinvar_cleaned.csv"
    train_file = "data/processed/training_base.csv"
    vus_file = "data/processed/vus_to_predict.csv"
    
    clean_and_split_clinvar(input_file, train_file, vus_file)