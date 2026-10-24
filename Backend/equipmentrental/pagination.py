from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """PAGE_SIZE (25) rows per page; clients may ask for more with ?page_size=, up to a hard cap.

    The availability calendar uses page_size to fetch a week of slots in one or two requests.
    """

    page_size_query_param = 'page_size'
    max_page_size = 100
