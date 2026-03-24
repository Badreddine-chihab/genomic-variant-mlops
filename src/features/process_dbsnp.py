import csv
import os
import subprocess


def process_dbsnp(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Erreur : Le fichier {input_path} est introuvable.")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Début extraction CAF depuis {input_path}...")
    print("Traitement de millions de lignes...")

    with subprocess.Popen(['zcat', input_path], stdout=subprocess.PIPE, text=True) as proc, \
         open(output_path, 'w', newline='') as f_out:

        writer = csv.writer(f_out)
        writer.writerow(['CHROM', 'POS', 'REF', 'ALT', 'ALT_FREQ'])

        processed_lines = 0
        kept_lines = 0

        for line in proc.stdout:
            if line.startswith('#'):
                continue

            parts = line.strip().split('\t')
            if len(parts) < 8:
                continue

            chrom = parts[0]
            pos = parts[1]
            ref = parts[3]
            alt_field = parts[4]
            info = parts[7]

            # -----------------------------
            # Extract CAF
            # -----------------------------
            caf_values = None

            for field in info.split(';'):
                if field.startswith('CAF='):
                    caf_values = field.split('=')[1].split(',')
                    break

            if caf_values is None:
                continue

            # Remove missing values
            caf_values = [v for v in caf_values if v != '.']

            if len(caf_values) < 2:
                continue

            try:
                freqs = [float(v) for v in caf_values]
            except:
                continue

            # -----------------------------
            # Handle MULTI-ALLELIC ALT
            # -----------------------------
            alt_alleles = alt_field.split(',')

            # CAF structure:
            # [REF, ALT1, ALT2, ...]
            for i, alt in enumerate(alt_alleles):
                if i + 1 >= len(freqs):
                    continue

                alt_freq = freqs[i + 1]

                writer.writerow([chrom, pos, ref, alt, alt_freq])
                kept_lines += 1

            processed_lines += 1

            if processed_lines % 2_000_000 == 0:
                print(f"{processed_lines} lignes lues | {kept_lines} variants écrits...")

    print(f"✅ Terminé.")
    print(f"Lignes VCF lues: {processed_lines}")
    print(f"Variants utilisables: {kept_lines}")
    print(f"Fichier: {output_path}")


if __name__ == "__main__":
    input_vcf = "data/raw/dbsnp_common.vcf.gz"
    output_csv = "data/processed/dbsnp_frequencies.csv"
    process_dbsnp(input_vcf, output_csv)