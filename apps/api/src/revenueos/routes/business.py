from __future__ import annotations

from math import ceil
from uuid import UUID

from revenueos.business_contracts import Page, TenantPage
from revenueos.business_repositories import PageResult
from revenueos.contracts import APIModel


def page_response[TSource, TResponse: APIModel](
    result: PageResult[TSource],
    response_type: type[TResponse],
    *,
    page: int,
    page_size: int,
) -> Page[TResponse]:
    return Page(
        items=[response_type.model_validate(item) for item in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
        pages=ceil(result.total / page_size) if result.total else 0,
    )


def tenant_page_response[TSource, TResponse: APIModel](
    result: PageResult[TSource],
    response_type: type[TResponse],
    *,
    organisation_id: UUID,
    page: int,
    page_size: int,
) -> TenantPage[TResponse]:
    return TenantPage(
        organisation_id=organisation_id,
        items=[response_type.model_validate(item) for item in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
        pages=ceil(result.total / page_size) if result.total else 0,
    )
