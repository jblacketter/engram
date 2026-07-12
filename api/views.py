from collections import Counter

import httpx
from asgiref.sync import async_to_sync
from django.db import connection
from django.db.models import Count, Max, Min
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Memory
from core.services import memory_service, scoping, search_service

from .authentication import request_agent

from .serializers import (
    IngestBatchSerializer,
    IngestFileSerializer,
    IngestURLSerializer,
    MemoryCreateSerializer,
    MemoryListQuerySerializer,
    MemorySerializer,
    MemoryUpdateSerializer,
    SearchRequestSerializer,
    SearchResultSerializer,
)
from .throttling import ReadRateThrottle, WriteRateThrottle


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            db_ok = False
        return Response({"status": "ok", "database": db_ok})


class MemoryListCreateView(APIView):
    def get_throttles(self):
        if self.request.method == "GET":
            return [ReadRateThrottle()]
        return [WriteRateThrottle()]

    def get(self, request):
        query = MemoryListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        try:
            tags = scoping.constrain_read_tags(
                request_agent(request), params.get("tags")
            )
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        memories = async_to_sync(memory_service.list_recent)(
            limit=params["limit"],
            source=params.get("source"),
            tags=tags or None,
            exclude_tags=params.get("exclude_tags"),
        )
        serializer = MemorySerializer(memories, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MemoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            data["tags"] = scoping.check_write_tags(
                request_agent(request), data.get("tags")
            )
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        try:
            memory = async_to_sync(memory_service.create_memory)(**data)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Response(
                {"error": "Embedding service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(MemorySerializer(memory).data, status=status.HTTP_201_CREATED)


class MemoryDetailView(APIView):
    def get_throttles(self):
        if self.request.method == "GET":
            return [ReadRateThrottle()]
        return [WriteRateThrottle()]

    def _out_of_scope(self, request, pk) -> bool:
        """True when an agent principal cannot see this memory (404, never
        403 — no existence oracle). Owner/anonymous: always False."""
        agent = request_agent(request)
        if agent is None:
            return False
        return not scoping.allowed_queryset(agent).filter(pk=pk).exists()

    def get(self, request, pk):
        if self._out_of_scope(request, pk):
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            memory = async_to_sync(memory_service.get_memory)(pk)
        except Memory.DoesNotExist:
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(MemorySerializer(memory).data)

    def patch(self, request, pk):
        serializer = MemoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response(
                {"error": "No fields to update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if self._out_of_scope(request, pk):
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        data = dict(serializer.validated_data)
        if "tags" in data:
            # Same write contract as create/ingest (and MCP update): agents
            # cannot retag a memory out of their allowed domains, and a
            # tags update with no domain tag gets the default injected —
            # a row can never leave every agent scope via PATCH.
            try:
                data["tags"] = scoping.check_write_tags(
                    request_agent(request), data["tags"]
                )
            except scoping.ScopeError as exc:
                return Response(
                    {"error": str(exc)}, status=status.HTTP_403_FORBIDDEN
                )
        try:
            memory = async_to_sync(memory_service.update_memory)(pk, **data)
        except Memory.DoesNotExist:
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Response(
                {"error": "Embedding service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(MemorySerializer(memory).data)

    def delete(self, request, pk):
        if self._out_of_scope(request, pk):
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            async_to_sync(memory_service.delete_memory)(pk)
        except Memory.DoesNotExist:
            return Response(
                {"error": "Memory not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchView(APIView):
    throttle_classes = [WriteRateThrottle]

    def post(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            data["tags"] = scoping.constrain_read_tags(
                request_agent(request), data.get("tags")
            ) or None
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        try:
            results = async_to_sync(search_service.search)(**data)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Response(
                {"error": "Embedding service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(SearchResultSerializer(results, many=True).data)


class StatsView(APIView):
    throttle_classes = [ReadRateThrottle]

    def get(self, request):
        agent = request_agent(request)
        qs = Memory.objects if agent is None else scoping.allowed_queryset(agent)
        total = qs.count()
        if total == 0:
            return Response(
                {"total": 0, "by_source": {}, "top_tags": [], "date_range": None}
            )

        # Source breakdown
        source_rows = qs.values("source").annotate(count=Count("id"))
        by_source = {row["source"]: row["count"] for row in source_rows}

        # Date range
        agg = qs.aggregate(
            earliest=Min("created_at"), latest=Max("created_at")
        )

        # Tag frequency
        all_tags = qs.values_list("tags", flat=True)
        tag_counter = Counter()
        for tags in all_tags:
            if isinstance(tags, list):
                tag_counter.update(tags)
        top_tags = [
            {"tag": tag, "count": count} for tag, count in tag_counter.most_common(20)
        ]

        return Response(
            {
                "total": total,
                "by_source": by_source,
                "top_tags": top_tags,
                "date_range": {
                    "earliest": (
                        agg["earliest"].isoformat() if agg["earliest"] else None
                    ),
                    "latest": agg["latest"].isoformat() if agg["latest"] else None,
                },
            }
        )


class TagsView(APIView):
    throttle_classes = [ReadRateThrottle]

    def get(self, request):
        agent = request_agent(request)
        qs = Memory.objects if agent is None else scoping.allowed_queryset(agent)
        all_tags = qs.values_list("tags", flat=True)
        tag_counter = Counter()
        for tags in all_tags:
            if isinstance(tags, list):
                tag_counter.update(tags)
        result = [
            {"tag": tag, "count": count}
            for tag, count in tag_counter.most_common()
        ]
        return Response(result)


# --- Ingestion views ---


class IngestFileView(APIView):
    throttle_classes = [WriteRateThrottle]

    def post(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IngestFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = request.FILES["file"]
        max_size = getattr(
            __import__("django.conf", fromlist=["settings"]).settings,
            "INGEST_MAX_FILE_SIZE",
            10 * 1024 * 1024,
        )
        if uploaded.size > max_size:
            return Response(
                {"error": f"File exceeds {max_size} byte limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_bytes = uploaded.read()
        tags = serializer.validated_data.get("tags", [])
        if isinstance(tags, str):
            import json as _json

            try:
                tags = _json.loads(tags)
            except (ValueError, TypeError):
                tags = []

        try:
            tags = scoping.check_write_tags(request_agent(request), tags)
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        try:
            from ingestion.file_ingestor import ingest_file

            results = async_to_sync(ingest_file)(
                file_bytes=file_bytes,
                filename=uploaded.name,
                source=serializer.validated_data.get("source", "import"),
                tags=tags,
                importance=serializer.validated_data.get("importance", 0.5),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Response(
                {"error": "Embedding service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"memories_created": len(results), "results": results},
            status=status.HTTP_201_CREATED,
        )


class IngestURLView(APIView):
    throttle_classes = [WriteRateThrottle]

    def post(self, request):
        serializer = IngestURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            url_tags = scoping.check_write_tags(
                request_agent(request), serializer.validated_data.get("tags", [])
            )
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        try:
            from ingestion.url_scraper import SSRFError, scrape_url

            results = async_to_sync(scrape_url)(
                url=serializer.validated_data["url"],
                source=serializer.validated_data.get("source", "url"),
                tags=url_tags,
                importance=serializer.validated_data.get("importance", 0.5),
            )
        except SSRFError as exc:
            return Response(
                {"error": f"SSRF validation failed: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Response(
                {"error": "Embedding service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"memories_created": len(results), "results": results},
            status=status.HTTP_201_CREATED,
        )


class IngestBatchView(APIView):
    throttle_classes = [WriteRateThrottle]

    def post(self, request):
        serializer = IngestBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = serializer.validated_data["items"]
        agent = request_agent(request)
        try:
            for item in items:
                item["tags"] = scoping.check_write_tags(agent, item.get("tags"))
        except scoping.ScopeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        batch_items = []
        for item in items:
            if item["type"] == "url":
                batch_items.append({
                    "type": "url",
                    "url": item.get("url", ""),
                    "source": item.get("source", "url"),
                    "tags": item.get("tags"),
                    "importance": item.get("importance", 0.5),
                })
            elif item["type"] == "file":
                import base64

                try:
                    file_bytes = base64.b64decode(item.get("content_base64", ""))
                except Exception:
                    batch_items.append({
                        "type": "file",
                        "file_bytes": None,
                        "filename": item.get("filename", ""),
                    })
                    continue
                batch_items.append({
                    "type": "file",
                    "file_bytes": file_bytes,
                    "filename": item.get("filename", ""),
                    "source": item.get("source", "import"),
                    "tags": item.get("tags"),
                    "importance": item.get("importance", 0.5),
                })

        from ingestion.batch_processor import process_batch

        results = async_to_sync(process_batch)(batch_items)

        succeeded = sum(1 for r in results if r["status"] == "ok")
        failed = sum(1 for r in results if r["status"] == "error")

        return Response({
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        })
