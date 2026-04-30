import duckdb
import os

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL aws; LOAD aws;")
con.execute("CALL load_aws_credentials(); SET s3_region='us-east-1';")

# On définit les deux cibles qui posent problème
MAPPING_FAIL = {
    'X': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/06/006a6c2acd1c12bd22176585e61d17', 
    'M': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/11/12e866bbcf966dd799b6a2e83264c3', 
    '13': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/1b/898c0347f2387c4a431104660c06c9', 
    '19': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/ad/c6c94f7a460c702c89590238e6b679', 
    '15': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/26/0d3eae763987a50b3261631f0c7a28', 
    '22': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/39/f0e78519753875037bc1d06d97ecfe', 
    '2': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/3c/352d401e3a12c7d40b95448b546b32', 
    '3': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/3e/346647857379e5faa7b4f2d8eb8805', 
    '5': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/4e/40326c5d761a4c2d87728b4062041d', 
    '7': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/57/bf0c91c959bc0fd2cf9946942e050c', 
    '6': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/5e/51df49c0ac258d71d43d184aeebd9d', 
    '18': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/74/8b0977d98b19e46cfe4f215ccccbc2', 
    '9': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/7c/dfd2a6e0dd913cc24c21a15e2e0de7', 
    '1': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/7c/f341441e284b741b49df0060e39581', 
    '11': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/7f/d169692b38dea54b286c02f79888d0', 
    '4': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/82/a6c577c9c81f7252e34e4c8532d87f', 
    '12': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/83/374250a8148b30cf03c10ca7091f05', 
    '17': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/97/efbbb33bc12a793242e0b88e87f088', 
    '10': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/9a/1d9d9fecd78b72903b79883a0037db', 
    '14': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/9b/3cb62336e4a718140c8107e7f06fa6', 
    '21': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/9e/1a3583042f7f843246f85fd2e5d01e', 
    '8': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/b5/86b9627382851168fd4c2a5bd6d44a', 
    'Y': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/c9/5984e34b0beca4caae2945971f50cc', 
    '20': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/ce/06b2fcdf4881b30c71c4a0f86972f4', 
    '16': 's3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/files/md5/f9/12a863185a166691429ce2835e3b9b'
}

for chrom, s3_source in MAPPING_FAIL.items():
    print(f"\n🚀 Traitement forcé du Chromosome {chrom}...")
    
    local_csv = f"chr{chrom}_tmp.csv.gz"
    local_parquet = f"chr{chrom}.parquet"
    s3_dest = f"s3://aws-s3-bucket-pfa-genomic-classification/data/parquet/chr={chrom}/data.parquet"

    try:
        # 1. Téléchargement via AWS CLI (très robuste)
        print(f"📥 Téléchargement de la source S3...")
        os.system(f"aws s3 cp {s3_source} {local_csv}")

        # 2. Conversion locale avec DuckDB
        print(f"⚙️ Conversion CSV -> Parquet...")
        con.execute(f"""
            COPY (
                SELECT * FROM read_csv_auto('{local_csv}', 
                    compression='gzip', sep='\t', header=True, 
                    all_varchar=True, nullstr='.')
            ) TO '{local_parquet}' (FORMAT 'PARQUET');
        """)

        # 3. Upload vers le nouveau stockage partitionné
        print(f"📤 Upload du résultat vers S3...")
        os.system(f"aws s3 cp {local_parquet} {s3_dest}")

        # 4. Nettoyage
        if os.path.exists(local_csv): os.remove(local_csv)
        if os.path.exists(local_parquet): os.remove(local_parquet)
        
        print(f"✅ Chromosome {chrom} terminé avec succès !")

    except Exception as e:
        print(f"❌ Erreur critique sur Chromosome {chrom} : {e}")

print("\n✨ Si tout est passé, ton Feature Store est enfin COMPLET !")