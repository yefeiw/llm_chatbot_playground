from app.search.base import SearchProvider, SearchResult


class NoopSearchProvider(SearchProvider):
    def search(self, query: str) -> list[SearchResult]:
        _ = query
        return []
