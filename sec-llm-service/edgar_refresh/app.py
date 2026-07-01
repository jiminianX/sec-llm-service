import os
import requests
import boto3
from botocore.exceptions import ClientError

from errors import (
    STATUS_VALIDATION_ERROR,
    STATUS_UPSTREAM_ERROR,
    STATUS_STORAGE_ERROR,
    STATUS_INTERNAL_ERROR,
    build_success_response,
    build_error_response,
    log_error,
)

# Initialize the Amazon S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    # 1. Grab parameters (fallback to environment variables if not provided in event)
    file_url = event.get('file_url', 'https://www.sec.gov/files/company_tickers.json')
    bucket_name = event.get('bucket_name', os.environ.get('BUCKET_NAME'))
    s3_key = event.get('s3_key', 'company_tickers.json')

    if not bucket_name:
        log_error(
            context, "ValidationError", "Missing target S3 bucket name.",
            file_url=file_url, s3_key=s3_key,
        )
        return build_error_response(
            STATUS_VALIDATION_ERROR, "ValidationError",
            "Missing target S3 bucket name.", context.aws_request_id,
        )

    try:
        print(f"Downloading file from: {file_url}")

        # 2. Download the file content directly into memory
        headers = {'user-agent': "NYU jj3945@nyu.edu"}
        r = requests.get(file_url, headers=headers, timeout=(5, 15))
        r.raise_for_status()

        print(f"Uploading file to S3 bucket: {bucket_name} as key: {s3_key}")

        # 3. Upload the byte stream to Amazon S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=r.content,
            ContentType='application/json',
        )

        return build_success_response(200, {
            "bucket": bucket_name,
            "key": s3_key,
            "status": "uploaded",
        })

    except requests.RequestException as e:
        message = f"Failed to download SEC ticker file from {file_url}: {e}"
        log_error(context, "UpstreamServiceError", message, file_url=file_url)
        return build_error_response(
            STATUS_UPSTREAM_ERROR, "UpstreamServiceError", message, context.aws_request_id,
        )
    except ClientError as e:
        message = f"Failed to upload to s3://{bucket_name}/{s3_key}: {e}"
        log_error(context, "StorageError", message, bucket_name=bucket_name, s3_key=s3_key)
        return build_error_response(
            STATUS_STORAGE_ERROR, "StorageError", message, context.aws_request_id,
        )
    except Exception as e:
        log_error(
            context, "InternalError", str(e),
            file_url=file_url, bucket_name=bucket_name, s3_key=s3_key,
        )
        return build_error_response(
            STATUS_INTERNAL_ERROR, "InternalError",
            "An unexpected error occurred.", context.aws_request_id,
        )
