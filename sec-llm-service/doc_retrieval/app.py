import json
import os

import boto3
import requests
from botocore.exceptions import ClientError

from errors import (
    STATUS_INTERNAL_ERROR,
    STATUS_NOT_FOUND,
    STATUS_STORAGE_ERROR,
    STATUS_UPSTREAM_ERROR,
    STATUS_VALIDATION_ERROR,
    build_error_response,
    build_success_response,
    log_error,
)
from sec_edgar import SecEdgar

REQUIRED_FIELDS = ("question", "ticker", "year", "period")
VALID_PERIODS = {"Q1", "Q2", "Q3", "Q4", "FY"}
QUARTER_MAP = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
S3_KEY = "company_tickers.json"

s3_client = boto3.client("s3")


class ValidationError(Exception):
    """Raised when the incoming request body fails the doc_retrieval contract."""


def _validate_request(body):
    missing = [field for field in REQUIRED_FIELDS if not body.get(field)]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")

    question = body["question"]
    ticker = body["ticker"]
    period = body["period"]

    if not isinstance(question, str) or not question.strip():
        raise ValidationError("Field 'question' must be a non-empty string.")
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValidationError("Field 'ticker' must be a non-empty string.")

    try:
        year = int(body["year"])
    except (TypeError, ValueError):
        raise ValidationError(f"Field 'year' must be an integer, got: {body['year']!r}")

    if period not in VALID_PERIODS:
        raise ValidationError(
            f"Field 'period' must be one of {sorted(VALID_PERIODS)}, got: {period!r}"
        )

    return {
        "question": question,
        "ticker": ticker.upper(),
        "year": year,
        "period": period,
    }


def lambda_handler(event, context):
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        log_error(context, "ValidationError", "Missing BUCKET_NAME environment variable.")
        return build_error_response(
            STATUS_VALIDATION_ERROR,
            "ValidationError",
            "Missing BUCKET_NAME environment variable.",
            context.aws_request_id,
        )

    # API Gateway sends body as a JSON string; sam local invoke sends the dict directly.
    raw_body = event.get("body", event)
    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return build_error_response(
                STATUS_VALIDATION_ERROR,
                "ValidationError",
                "Request body must be valid JSON.",
                context.aws_request_id,
            )
    else:
        body = raw_body

    try:
        validated = _validate_request(body)
    except ValidationError as e:
        return build_error_response(
            STATUS_VALIDATION_ERROR, "ValidationError", str(e), context.aws_request_id
        )

    ticker = validated["ticker"]
    year = validated["year"]
    period = validated["period"]

    try:
        s3_response = s3_client.get_object(Bucket=bucket_name, Key=S3_KEY)
        filejson = json.loads(s3_response["Body"].read())
    except ClientError as e:
        message = f"Failed to read s3://{bucket_name}/{S3_KEY}: {e}"
        log_error(context, "StorageError", message, bucket_name=bucket_name, s3_key=S3_KEY)
        return build_error_response(
            STATUS_STORAGE_ERROR, "StorageError", message, context.aws_request_id
        )

    edgar = SecEdgar.from_dict(filejson)

    try:
        cik, _, _ = edgar.ticker_to_cik(ticker)
    except KeyError:
        return build_error_response(
            STATUS_NOT_FOUND,
            "NotFound",
            f"Ticker '{ticker}' not found in SEC EDGAR data.",
            context.aws_request_id,
        )

    if period == "FY":
        filings = edgar.annual_filing(cik, year)
    else:
        filings = edgar.quarterly_filing(cik, year, QUARTER_MAP[period])

    if not filings:
        return build_error_response(
            STATUS_NOT_FOUND,
            "NotFound",
            f"No {period} filing found for {ticker} in {year}.",
            context.aws_request_id,
        )

    filing = filings[0]

    try:
        content = edgar.get_filing_content(
            cik, filing["accessionNumber"], filing["primaryDocument"]
        )
    except requests.RequestException as e:
        message = f"Failed to fetch filing content from SEC: {e}"
        log_error(context, "UpstreamServiceError", message, url=filing["url"])
        return build_error_response(
            STATUS_UPSTREAM_ERROR, "UpstreamServiceError", message, context.aws_request_id
        )
    except Exception as e:
        log_error(context, "InternalError", str(e), ticker=ticker, year=year, period=period)
        return build_error_response(
            STATUS_INTERNAL_ERROR,
            "InternalError",
            "An unexpected error occurred.",
            context.aws_request_id,
        )

    return build_success_response(
        200,
        {
            "ticker": ticker,
            "year": year,
            "period": period,
            "filing": filing,
            "content": content,
        },
    )
