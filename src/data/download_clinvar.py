import os
import subprocess

def download_clinvar():
    url = "ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
    output_dir = "data/raw"
    output_path = os.path.join(output_dir, "clinvar.vcf.gz")

    os.makedirs(output_dir, exist_ok=True)

    # Si le fichier existe déjà, on vérifie s'il est complet ou on laisse wget gérer avec -c
    print(f"Téléchargement de ClinVar via wget depuis : {url}")
    
    # -c : continue le téléchargement si interrompu
    # -N : ne télécharge que si le fichier sur le serveur est plus récent
    command = ["wget", "-c", "-N", url, "-O", output_path]
    
    try:
        subprocess.run(command, check=True)
        print(f"Succès : ClinVar est prêt dans {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du téléchargement : {e}")

if __name__ == "__main__":
    download_clinvar()