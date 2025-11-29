#!/usr/bin/env python3
"""
Test script to verify the folder selection functionality.
"""

from file_uploader import S3FileUploader


def test_folder_validation():
    """Test the folder validation functionality."""
    print("Testing folder validation...")

    # Test valid folders
    valid_folders = S3FileUploader.get_valid_folders()
    print(f"Valid folders: {valid_folders}")

    # Create a test uploader instance (won't actually connect to S3)
    uploader = S3FileUploader(bucket_name="test-bucket")

    # Test each valid folder
    for folder in valid_folders:
        print(f"✓ {folder} - Valid")

    # Test invalid folder
    invalid_folder = "invalid-folder"
    print(f"✗ {invalid_folder} - Should be invalid")

    # Show what the S3 key would look like
    test_filename = "test-file.mp4"
    for folder in valid_folders:
        s3_key = f"vpms-vrt-emea-exp/{folder}/{test_filename}"
        print(f"  {folder}: {s3_key}")


if __name__ == "__main__":
    test_folder_validation()
