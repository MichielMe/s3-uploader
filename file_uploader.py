"""
AWS S3 File Uploader Module

This module provides functionality to upload files to AWS S3 buckets with
progress tracking, multipart upload support, and comprehensive error handling.
"""

import os
from pathlib import Path
from typing import Callable, Optional

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    FileSizeColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
)

load_dotenv()
console = Console()


class S3FileUploader:
    """
    A class to handle file uploads to AWS S3 with progress tracking.

    Attributes:
        bucket_name (str): The name of the S3 bucket
        region_name (str): AWS region name
        s3_client: Boto3 S3 client instance
    """

    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize the S3 uploader.

        Args:
            bucket_name: Name of the S3 bucket
            region_name: AWS region (default: us-east-1)
            aws_access_key_id: AWS access key (optional, uses default credentials if not provided)
            aws_secret_access_key: AWS secret key (optional)
        """
        self.bucket_name = bucket_name
        self.region_name = region_name

        # Create S3 client with credentials if provided
        session_kwargs = {"region_name": region_name}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )

        self.s3_client = boto3.client("s3", **session_kwargs)

        # Configure multipart upload thresholds
        self.transfer_config = TransferConfig(
            multipart_threshold=1024 * 25,  # 25MB
            max_concurrency=10,
            multipart_chunksize=1024 * 25,  # 25MB
            use_threads=True,
        )

    def bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible.

        Returns:
            bool: True if bucket exists and is accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                console.print(f"[red]Bucket '{self.bucket_name}' does not exist.[/red]")
            elif error_code == "403":
                console.print(
                    f"[red]Access denied to bucket '{self.bucket_name}'.[/red]"
                )
            else:
                console.print(f"[red]Error checking bucket: {e}[/red]")
            return False
        except NoCredentialsError:
            console.print("[red]AWS credentials not found.[/red]")
            return False

    def upload_file(
        self,
        file_path: str | Path,
        s3_key: Optional[str] = None,
        extra_args: Optional[dict] = None,
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Upload a file to S3 bucket with progress tracking.

        Args:
            file_path: Path to the file to upload
            s3_key: S3 object key (path in bucket). If None, uses the filename
            extra_args: Extra arguments for upload (e.g., ContentType, ACL)
            callback: Optional callback function for custom progress tracking

        Returns:
            bool: True if upload successful, False otherwise
        """
        file_path = Path(file_path)

        # Validate file exists
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return False

        if not file_path.is_file():
            console.print(f"[red]Path is not a file: {file_path}[/red]")
            return False

        # Use filename as S3 key if not provided
        if s3_key is None:
            s3_key = file_path.name

        # Get file size
        file_size = file_path.stat().st_size

        console.print(f"\n[cyan]Uploading:[/cyan] {file_path.name}")
        console.print(f"[cyan]To bucket:[/cyan] {self.bucket_name}")
        console.print(f"[cyan]S3 key:[/cyan] {s3_key}")
        console.print(
            f"[cyan]Size:[/cyan] {file_size:,} bytes ({file_size / (1024**2):.2f} MB)\n"
        )

        try:
            # Create progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
                FileSizeColumn(),
                TotalFileSizeColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:

                task_id = progress.add_task("Uploading", total=file_size)

                def progress_callback(bytes_transferred):
                    progress.update(task_id, completed=bytes_transferred)
                    if callback:
                        callback(bytes_transferred)

                # Upload the file
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs=extra_args,
                    Config=self.transfer_config,
                    Callback=progress_callback,
                )

            console.print(f"\n[green]✓ Upload successful![/green]")
            console.print(f"[green]S3 URI:[/green] s3://{self.bucket_name}/{s3_key}\n")
            return True

        except NoCredentialsError:
            console.print("[red]✗ AWS credentials not found.[/red]")
            console.print("[yellow]Please configure your AWS credentials.[/yellow]")
            return False
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            console.print(f"[red]✗ Upload failed: {error_code}[/red]")
            console.print(f"[red]{error_msg}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]✗ Unexpected error: {str(e)}[/red]")
            return False

    def upload_directory(
        self,
        directory_path: str | Path,
        s3_prefix: str = "",
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> tuple[int, int]:
        """
        Upload all files in a directory to S3.

        Args:
            directory_path: Path to the directory to upload
            s3_prefix: Prefix to add to all S3 keys
            include_patterns: List of glob patterns to include (e.g., ['*.txt', '*.pdf'])
            exclude_patterns: List of glob patterns to exclude

        Returns:
            tuple: (successful_uploads, failed_uploads)
        """
        directory_path = Path(directory_path)

        if not directory_path.exists() or not directory_path.is_dir():
            console.print(f"[red]Directory not found: {directory_path}[/red]")
            return 0, 0

        # Collect files to upload
        files_to_upload = []

        if include_patterns:
            for pattern in include_patterns:
                files_to_upload.extend(directory_path.rglob(pattern))
        else:
            files_to_upload = list(directory_path.rglob("*"))

        # Filter out directories and excluded patterns
        files_to_upload = [f for f in files_to_upload if f.is_file()]

        if exclude_patterns:
            for pattern in exclude_patterns:
                excluded = set(directory_path.rglob(pattern))
                files_to_upload = [f for f in files_to_upload if f not in excluded]

        if not files_to_upload:
            console.print("[yellow]No files found to upload.[/yellow]")
            return 0, 0

        console.print(
            f"\n[cyan]Found {len(files_to_upload)} file(s) to upload[/cyan]\n"
        )

        successful = 0
        failed = 0

        for file_path in files_to_upload:
            # Calculate relative path for S3 key
            relative_path = file_path.relative_to(directory_path)
            s3_key = f"{s3_prefix}/{relative_path}".lstrip("/").replace("\\", "/")

            if self.upload_file(file_path, s3_key):
                successful += 1
            else:
                failed += 1

        console.print(f"\n[cyan]Upload Summary:[/cyan]")
        console.print(f"[green]✓ Successful: {successful}[/green]")
        console.print(f"[red]✗ Failed: {failed}[/red]")

        return successful, failed

    def list_bucket_contents(
        self, prefix: str = "", max_items: int = 100
    ) -> list[dict]:
        """
        List contents of the S3 bucket.

        Args:
            prefix: Filter objects by prefix
            max_items: Maximum number of items to return

        Returns:
            list: List of objects in the bucket
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_items,
            )

            if "Contents" not in response:
                console.print("[yellow]Bucket is empty.[/yellow]")
                return []

            objects = response["Contents"]
            console.print(f"\n[cyan]Found {len(objects)} object(s) in bucket:[/cyan]\n")

            for obj in objects:
                size_mb = obj["Size"] / (1024**2)
                console.print(f"  • {obj['Key']} ({size_mb:.2f} MB)")

            return objects

        except ClientError as e:
            console.print(f"[red]Error listing bucket: {e}[/red]")
            return []

    def get_upload_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for uploading to S3.

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            str: Presigned URL or None if error
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            console.print(f"[red]Error generating presigned URL: {e}[/red]")
            return None


def create_uploader_from_env() -> Optional[S3FileUploader]:
    """
    Create an S3FileUploader instance using environment variables.

    Expected environment variables:
        - AWS_S3_BUCKET_NAME (required)
        - AWS_REGION (optional, default: us-east-1)
        - AWS_ACCESS_KEY_ID (optional, uses default credentials if not set)
        - AWS_SECRET_ACCESS_KEY (optional)

    Returns:
        S3FileUploader instance or None if bucket name not set
    """
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")

    if not bucket_name:
        console.print(
            "[red]Error: AWS_S3_BUCKET_NAME environment variable not set.[/red]"
        )
        return None

    return S3FileUploader(
        bucket_name=bucket_name,
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


if __name__ == "__main__":
    # Example usage
    console.print("[bold cyan]AWS S3 File Uploader[/bold cyan]\n")

    # Try to create uploader from environment variables
    uploader = create_uploader_from_env()

    if uploader:
        # Check if bucket exists
        if uploader.bucket_exists():
            console.print("[green]✓ Successfully connected to S3 bucket[/green]")
        else:
            console.print("[red]✗ Could not connect to S3 bucket[/red]")
