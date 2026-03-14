import csv
import os
import subprocess

def process_clinvar(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Erreur : Le fichier {input_path} est introuvable.")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Début de l'extraction des features depuis {input_path} via zcat...")
    
    # Utilisation de subprocess pour appeler zcat (décompression native Linux)
    # text=True permet de lire les données directement sous forme de chaînes de caractères
    with subprocess.Popen(['zcat', input_path], stdout=subprocess.PIPE, text=True) as proc, \
         open(output_path, 'w', newline='') as f_out:
        
        writer = csv.writer(f_out)
        writer.writerow(['CHROM', 'POS', 'REF', 'ALT', 'Is_InDel', 'Is_Frameshift', 'CLNSIG'])
        
        processed_lines = 0
        
        # On lit directement la sortie standard (stdout) du processus zcat
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
            
            clnsig = "Unknown"
            for field in info.split(';'):
                if field.startswith('CLNSIG='):
                    clnsig = field.split('=')[1]
                    break
            
            is_indel = int(len(ref) != len(alt))
            is_frameshift = 0
            if is_indel:
                is_frameshift = int(abs(len(ref) - len(alt)) % 3 != 0)
            
            writer.writerow([chrom, pos, ref, alt, is_indel, is_frameshift, clnsig])
            processed_lines += 1
            
            if processed_lines % 500000 == 0:
                print(f"{processed_lines} variants traités...")
                
    print(f"Terminé. Total : {processed_lines} variants. Fichier sauvegardé sous : {output_path}")

if __name__ == "__main__":
    input_vcf = "data/raw/clinvar.vcf.gz"
    output_csv = "data/processed/clinvar_cleaned.csv"
    process_clinvar(input_vcf, output_csv)