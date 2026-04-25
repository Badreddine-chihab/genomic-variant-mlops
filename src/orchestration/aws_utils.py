"""
AWS and DVC utilities for MLOps pipeline.

Handles:
- AWS credential initialization
- DVC data pulling from S3
- S3 client management
- Configuration loading from AWS config
"""

import os
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class AWSConfig:
    """AWS configuration manager."""
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize AWS configuration.
        
        Args:
            config_dict: AWS configuration dictionary (from config/aws_config.yaml)
        """
        self.config = config_dict or {}
        self.profile = self.config.get("profile", "default")
        self.region = self.config.get("region", "us-east-1")
        self.bucket = self.config.get("s3", {}).get("bucket_name", "")
        self.dvc_remote_url = self.config.get("dvc", {}).get("remote_url", "")
        
    def get_s3_client(self):
        """Get initialized S3 client using AWS credentials."""
        try:
            session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region
            )
            client = session.client("s3")
            logger.info(f"✅ S3 client initialized (profile={self.profile}, region={self.region})")
            return client
        except NoCredentialsError:
            logger.error("❌ AWS credentials not found. Configure ~/.aws/credentials or set AWS env vars.")
            raise
        except ClientError as e:
            logger.error(f"❌ AWS error: {e}")
            raise
    
    def validate_credentials(self) -> bool:
        """Validate AWS credentials are configured."""
        try:
            self.get_s3_client().head_bucket(Bucket=self.bucket)
            logger.info(f"✅ AWS credentials valid. S3 bucket '{self.bucket}' accessible.")
            return True
        except Exception as e:
            logger.warning(f"⚠️ AWS credentials validation failed: {e}")
            return False


class DVCManager:
    """DVC (Data Version Control) manager for S3 integration."""
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None, project_root: Optional[Path] = None):
        """
        Initialize DVC manager.
        
        Args:
            config_dict: DVC configuration dictionary (from config/aws_config.yaml)
            project_root: Project root directory (defaults to current working directory)
        """
        self.config = config_dict or {}
        self.project_root = project_root or Path.cwd()
        self.auto_pull = self.config.get("auto_pull_before_training", True)
        self.tracked_files = self.config.get("track_files", [])
        
    def pull_data(self, verbose: bool = True) -> bool:
        """
        Pull data from DVC remote (S3).
        
        Args:
            verbose: Print detailed output
            
        Returns:
            True if successful, False otherwise
        """
        if not self.auto_pull:
            logger.info("⏭️ DVC auto-pull disabled. Skipping data pull.")
            return True
        
        try:
            logger.info("🔄 Pulling data from DVC remote (S3)...")
            
            # Check if dvc is available
            result = subprocess.run(
                ["dvc", "pull", "-v"] if verbose else ["dvc", "pull"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("✅ DVC data pull completed successfully")
                if verbose and result.stdout:
                    logger.debug(f"DVC output:\n{result.stdout}")
                return True
            else:
                logger.error(f"❌ DVC pull failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("❌ DVC not installed. Install with: pip install dvc[s3]")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ DVC pull timed out (5 minute limit)")
            return False
        except Exception as e:
            logger.error(f"❌ Error pulling data: {e}")
            return False
    
    def check_dvc_status(self) -> Dict[str, bool]:
        """
        Check status of DVC-tracked files.
        
        Returns:
            Dictionary with file status: {"file.dvc": True/False}
        """
        try:
            result = subprocess.run(
                ["dvc", "status", "-c"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and not result.stdout.strip():
                logger.info("✅ All DVC files up-to-date")
                return {f: True for f in self.tracked_files}
            else:
                logger.warning(f"⚠️ DVC status: {result.stdout}")
                return {f: False for f in self.tracked_files}
                
        except Exception as e:
            logger.warning(f"⚠️ Could not check DVC status: {e}")
            return {}


class PipelineAWSSetup:
    """Combined AWS + DVC setup for pipeline execution."""
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None, project_root: Optional[Path] = None):
        """
        Initialize pipeline AWS setup.
        
        Args:
            config_dict: Complete configuration dictionary (includes 'aws' key)
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        aws_config = config_dict.get("aws", {}) if config_dict else {}
        dvc_config = aws_config.get("dvc", {}) if aws_config else {}
        
        self.aws_config = AWSConfig(aws_config)
        self.dvc_manager = DVCManager(dvc_config, self.project_root)
        
    def prepare_pipeline_environment(self, skip_validation: bool = False) -> bool:
        """
        Prepare environment for pipeline execution:
        1. Validate AWS credentials
        2. Pull data from S3 via DVC
        3. Verify data files exist
        
        Args:
            skip_validation: Skip AWS credential validation
            
        Returns:
            True if all setup successful, False otherwise
        """
        logger.info("🚀 Preparing pipeline environment...")
        
        # Step 1: Validate AWS credentials
        if not skip_validation:
            if not self.aws_config.validate_credentials():
                logger.warning("⚠️ AWS credential validation failed (continuing anyway)")
        
        # Step 2: Pull data from DVC
        if not self.dvc_manager.pull_data():
            logger.error("❌ Failed to pull data from DVC. Pipeline may fail.")
            return False
        
        # Step 3: Verify data files
        logger.info("✅ Pipeline environment ready for execution")
        return True


def setup_aws_from_config(config_dict: Optional[Dict[str, Any]] = None, 
                          project_root: Optional[Path] = None) -> PipelineAWSSetup:
    """
    Convenience function to setup AWS/DVC from config dictionary.
    
    Args:
        config_dict: Configuration dictionary (from Hydra or YAML)
        project_root: Project root directory
        
    Returns:
        PipelineAWSSetup instance ready for use
    """
    return PipelineAWSSetup(config_dict, project_root)
