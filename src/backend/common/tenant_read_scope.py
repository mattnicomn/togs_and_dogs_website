"""Tenant read filters and bounded, response-confidential pagination."""

from boto3.dynamodb.conditions import Attr


# Historical untagged records belong only to this tenant, not an environment default.
LEGACY_PRIMARY_COMPANY_ID = "tog_and_dogs"

# Bound read amplification independently of caller-supplied pagination parameters.
MAX_TENANT_PAGE_READS = 16


class PaginationTraversalLimitReached(Exception):
    """A confidential continuation boundary could not be established safely."""

    def __init__(self):
        super().__init__("PAGINATION_TRAVERSAL_LIMIT_REACHED")


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


def read_confidential_page(read_page, read_kwargs, *, key_fields):
    """Read until exhaustion or a continuation key belonging to a returned row.

    The supplied database filter must enforce the complete tenant/role/read
    scope. LastEvaluatedKey describes an evaluated row, not necessarily a row
    passing that filter. Never publish it unless every key field matches the
    last returned row; build the public cursor from that authorized row instead.

    Leading empty pages retain the original evaluation limit. After collecting
    rows with an excluded trailing key, evaluate one row at a time to find a
    safe boundary without exceeding the original result-size limit. Exhaustion
    returns the collected rows without a cursor. Cap/stall/invalid-boundary
    failure discards partial results and reveals only a generic error.
    """
    kwargs = dict(read_kwargs)
    page_limit = kwargs['Limit']
    items = []
    seen_keys = []
    if kwargs.get('ExclusiveStartKey'):
        seen_keys.append(kwargs['ExclusiveStartKey'])

    for _ in range(MAX_TENANT_PAGE_READS):
        response = read_page(**kwargs)
        page_items = response.get('Items', [])
        items.extend(page_items)
        if len(items) > page_limit:
            raise PaginationTraversalLimitReached()

        evaluated_key = response.get('LastEvaluatedKey')
        if not evaluated_key:
            return {'Items': items}
        if (not isinstance(evaluated_key, dict)
                or set(evaluated_key) != set(key_fields)
                or evaluated_key in seen_keys):
            raise PaginationTraversalLimitReached()
        seen_keys.append(evaluated_key)

        if page_items:
            last_item = page_items[-1]
            if (all(field in last_item for field in key_fields)
                    and all(last_item[field] == evaluated_key[field] for field in key_fields)):
                return {'Items': items,
                        'LastEvaluatedKey': {field: last_item[field] for field in key_fields}}

        # This continuation state is internal only and retains the same filter.
        kwargs['ExclusiveStartKey'] = evaluated_key
        if items:
            kwargs['Limit'] = 1

    raise PaginationTraversalLimitReached()
