import csv
import os
import subprocess

def process_dbsnp(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Erreur : Le fichier {input_path} est introuvable.")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Début de l'extraction des fréquences (CAF) depuis {input_path} via zcat...")
    print("Cette opération va parcourir des millions de lignes, merci de patienter...")
    
    with subprocess.Popen(['zcat', input_path], stdout=subprocess.PIPE, text=True) as proc, \
         open(output_path, 'w', newline='') as f_out:
        
        writer = csv.writer(f_out)
        # On garde uniquement les clés de jointure et notre précieuse feature
        writer.writerow(['CHROM', 'POS', 'REF', 'ALT', 'ALT_FREQ'])
        
        processed_lines = 0
        
        for line in proc.stdout:
            if line.startswith('#'):
                continue
            
            parts = line.strip().split('\t')
            if len(parts) < 8:
                continue
                
            chrom = parts[0]
            pos = parts[1]
            ref = parts[3]
            alt = parts[4]
            info = parts[7]
            
            alt_freq = "0.0" # Valeur par défaut si introuvable
            
            # Recherche de la balise CAF= dans la colonne INFO
            for field in info.split(';'):
                if field.startswith('CAF='):
                    caf_values = field.split('=')[1].split(',')
                    # On sécurise l'extraction : on veut la 2ème valeur (ALT), si elle existe et n'est pas un point '.'
                    if len(caf_values) > 1 and caf_values[1] != '.':
                        alt_freq = caf_values[1]
                    break
            
            writer.writerow([chrom, pos, ref, alt, alt_freq])
            
            processed_lines += 1
            if processed_lines % 2000000 == 0:
                print(f"{processed_lines} variants dbSNP traités...")

    print(f"Terminé. Total : {processed_lines} variants. Fichier sauvegardé sous : {output_path}")

if __name__ == "__main__":
    input_vcf = "data/raw/dbsnp_common.vcf.gz"
    output_csv = "data/processed/dbsnp_frequencies.csv"
    process_dbsnp(input_vcf, output_csv)