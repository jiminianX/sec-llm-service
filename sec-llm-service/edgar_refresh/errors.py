"""Structured error/success response helpers for Lambda proxy integration.

Keep this file identical to its sibling copy in doc_retrieval/errors.py.
SAM packages each function's CodeUri/ independently, so sharing this module
via a Lambda Layer isn't worth the extra build wiring for two functions this
small -- reconsider if a third function needs it too.
"""
import json

STATUS_VALIDATION_ERROR = 400
STATUS_NOT_FOUND = 404
STATUS_UPSTREAM_ERROR = 502
STATUS_STORAGE_ERROR = 500
STATUS_INTERNAL_ERROR = 500


def build_success_response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
    }


def build_error_response(status_code, error_code, message, request_id):
    return {
        "statusCode": status_code,
        "body": json.dumps({
            "error": error_code,
            "message": message,
            "request_id": request_id,
        }),
    }


def log_error(context, error_code, message, **input_context):
    print(json.dumps({
        "aws_request_id": getattr(context, "aws_request_id", None),
        "error_code": error_code,
        "message": message,
        **input_context,
    }))
