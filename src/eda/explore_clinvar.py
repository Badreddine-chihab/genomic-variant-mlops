import gzip
import os

def explore_vcf(file_path, num_lines_to_read=5):
    if not os.path.exists(file_path):
        print(f"Erreur : Le fichier {file_path} n'existe pas.")
        return

    print(f"Analyse du fichier : {file_path}\n")
    
    with gzip.open(file_path, 'rt') as f:
        # 1. Lecture de la ligne d'en-tête des colonnes
        for line in f:
            if line.startswith("#CHROM"):
                print("--- Colonnes du fichier VCF ---")
                print(line.strip())
                break
        
        # 2. Lecture des premières lignes de données
        print(f"\n--- Les {num_lines_to_read} premières variantes ---")
        count = 0
        for line in f:
            if count >= num_lines_to_read:
                break
            print(line.strip())
            count += 1

if __name__ == "__main__":
    vcf_path = "data/raw/clinvar.vcf.gz"
    explore_vcf(vcf_path)