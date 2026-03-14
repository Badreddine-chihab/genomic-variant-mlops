import os
import subprocess

def download_dbsnp_common():
    # URL du fichier des variants communs pour l'assemblage GRCh38
    url = "ftp://ftp.ncbi.nlm.nih.gov/snp/organisms/human_9606_b151_GRCh38p7/VCF/common_all_20180418.vcf.gz"
    output_dir = "data/raw"
    output_path = os.path.join(output_dir, "dbsnp_common.vcf.gz")

    os.makedirs(output_dir, exist_ok=True)

    print(f"Lancement du téléchargement de dbSNP (Common) depuis : {url}")
    print("Ce fichier pèse environ 1.5 Go. Le processus peut prendre du temps...")
    
    # Appel de wget via subprocess
    command = ["wget", "-c", url, "-O", output_path]
    
    try:
        subprocess.run(command, check=True)
        print(f"\nSuccès : Fichier sauvegardé sous {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"\nErreur lors du téléchargement : {e}")

if __name__ == "__main__":
    download_dbsnp_common()