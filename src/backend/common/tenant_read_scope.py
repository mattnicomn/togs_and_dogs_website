"""Tenant filters for read paths with explicit primary-only legacy compatibility."""

from boto3.dynamodb.conditions import Attr


# Historical untagged records belong only to this tenant, not an environment default.
LEGACY_PRIMARY_COMPANY_ID = "tog_and_dogs"


def build_tenant_read_filter(company_id, *, allow_primary_legacy=False):
    """Match exact tenant tags, optionally including the primary's absent tags.

    NULL, empty and malformed stored tags are not absent attributes. Invalid
    resolved tenant IDs match nothing; this helper does not resolve identity or
    grant access based on roles.
    """
    company = Attr("company_id")
    if not isinstance(company_id, str) or not company_id or company_id.strip() != company_id:
        return company.exists() & company.not_exists()

    condition = company.eq(company_id)
    if allow_primary_legacy and company_id == LEGACY_PRIMARY_COMPANY_ID:
        condition = condition | company.not_exists()
    return condition
