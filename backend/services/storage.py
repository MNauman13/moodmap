import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class R2StorageService:
    """ Cloudflare R2 storage service (S3-compatible) """

    def __init__(self):
        self.bucket_name = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "moodmap-audio")
        self.client = boto3.client(
            "s3",
            endpoint_url = os.getenv("CLOUDFLARE_R2_ENDPOINT"),
            aws_access_key_id = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
            aws_secret_access_key = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
            config = Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )

    # 10 MB hard cap on audio uploads
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024

    def generate_upload_presigned_url(
            self,
            user_id: str,
            file_extension: str = "webm",
            expires_in: int = 300,  # 5 minutes
    ) -> dict:
        """
        Generate a presigned URL for direct browser → R2 upload.
        The Conditions list enforces a 10 MB max — R2 will reject
        any upload whose Content-Length falls outside the range.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        object_key = f"users/{user_id}/{timestamp}_{unique_id}.{file_extension}"

        try:
            presigned = self.client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_key,
                Fields={"Content-Type": f"audio/{file_extension}"},
                Conditions=[
                    {"Content-Type": f"audio/{file_extension}"},
                    ["content-length-range", 1, self.MAX_UPLOAD_BYTES],
                ],
                ExpiresIn=expires_in,
            )
            return {
                "upload_url": presigned["url"],
                "fields": presigned["fields"],
                "object_key": object_key,
                "expires_in": expires_in,
                "max_bytes": self.MAX_UPLOAD_BYTES,
            }
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            raise

    
    def generate_download_presigned_url(
        self,
        object_key: str,
        expires_in: int = 3600,  # 1 hour
    ) -> Optional[str]:
        """ Generate a presigned URL for reading/downloading an audio file """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned download URL: {e}")
            return None
        

    def delete_object(self, object_key:str) -> bool:
        """ Delete an audio file from R2 """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete object {object_key}: {e}")
            return False
        

    def object_exists(self, object_key: str) -> bool:
        """ Check if an object exists in R2. """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False

    def get_object_metadata(self, object_key: str) -> Optional[dict]:
        """Return {content_type, content_length} from R2's HEAD, or None if missing.

        Used at journal-create time to verify the upload actually matches the
        size + MIME policy enforced on the presigned URL — defense in depth
        against leaked or replayed URLs.
        """
        try:
            head = self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return {
                "content_type": head.get("ContentType", ""),
                "content_length": int(head.get("ContentLength", 0)),
            }
        except ClientError:
            return None
        

    def get_audio_stream(self, object_key: str):
        """ Stream audio bytes for ML inference (used by Celery workers) """
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to stream audio {object_key}: {e}")
            return None
        

# Singleton instance
r2_storage = R2StorageService()