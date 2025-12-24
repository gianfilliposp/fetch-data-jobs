import os

USER_TYPE_ADMIN = "admin"
USER_TYPE_ACCOUNTING = "accounting"
USER_TYPE_CUSTOMER = "customer"

USER_STATUS_ACTIVE = "active"
USER_STATUS_INACTIVE = "inactive"
USER_STATUS_PENDING_CONFIRMATION = "pending_confirmation"


#PAYROLL STATUS
PAYROLL_STATUS_CREATED = "created"
PAYROLL_STATUS_PENDING_VALIDATION = "pending_validation"
PAYROLL_STATUS_VALIDATED = "validated"
PAYROLL_STATUS_PREVIEW_SENT = "preview_sent"
PAYROLL_STATUS_PREVIEW_VALIDATED = "preview_validated"
PAYROLL_STATUS_PREVIEW_REJECTED = "preview_rejected"
PAYROLL_STATUS_FINAL_VERSION_SENT = "final_version_sent"
PAYROLL_STATUS_FINAL_VERSION_APPROVED = "final_version_approved"
PAY_STUBS_BUCKET_NAME = f"pay-stubs-{os.environ.get('ENVIRONMENT')}"

convertable_fields = ['salary', 'va', 'vr', 'vt']