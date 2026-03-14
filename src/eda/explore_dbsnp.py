import subprocess
import os

def explore_dbsnp(file_path, num_lines_to_read=5):
    if not os.path.exists(file_path):
        print(f"Erreur : Le fichier {file_path} n'existe pas.")
        return

    print(f"Analyse du fichier : {file_path}\n")
    
    command = ['zcat', file_path]
    
    try:
        with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as proc:
            # Recherche de l'en-tête des colonnes
            for line in proc.stdout:
                if line.startswith("#CHROM"):
                    print("--- Colonnes du fichier dbSNP ---")
                    print(line.strip())
                    break
            
            # Affichage des premières lignes de données
            print(f"\n--- Les {num_lines_to_read} premières variantes ---")
            count = 0
            for line in proc.stdout:
                if count >= num_lines_to_read:
                    proc.terminate() # Arrêt propre du processus zcat
                    break
                print(line.strip())
                count += 1
                
    except Exception as e:
        print(f"Erreur lors de l'exécution : {e}")

if __name__ == "__main__":
    vcf_path = "data/raw/dbsnp_common.vcf.gz"
    explore_dbsnp(vcf_path)