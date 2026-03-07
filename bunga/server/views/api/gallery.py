from dataclasses import asdict
import importlib
import inspect
import os
import subprocess
import sys
from typing import override


from django.core.cache import cache as Cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from server import models, serializers

from utils.log import logger
from server.utils import cached_function


class Gallery(viewsets.ViewSet):
    @action(
        url_path="pull-linkers",
        detail=False,
        methods=["POST"],
        permission_classes=[IsAdminUser],
    )
    def pull_linkers(self, request: Request) -> Response:
        base_path = os.path.join(os.getcwd(), "external_modules")
        if not os.path.exists(base_path):
            os.makedirs(base_path)

        repo_url = "https://github.com/joodo/bunga-link"
        folder_name = "bunga-link"

        target_path = os.path.join(base_path, "bunga-link")
        if not os.path.exists(target_path):
            logger.info(f"Cloning {repo_url}...")
            subprocess.run(["git", "clone", repo_url, target_path], check=True)
        else:
            logger.info(f"Updating {folder_name}...")
            subprocess.run(["git", "-C", target_path, "pull"], check=True)

        if target_path not in sys.path:
            sys.path.insert(0, target_path)
        module = importlib.import_module("src")
        importlib.reload(module)

        return Response("ok")

    @action(
        detail=False,
        methods=["GET"],
        permission_classes=[IsAdminUser],
    )
    def linkers(self, request: Request) -> Response:
        submodule_full_path = os.path.join(
            os.getcwd(), "external_modules", "bunga-link"
        )
        cmd = ["git", "log", "-1", "--format=%h|%an|%s|%ci"]
        result = subprocess.run(
            cmd,
            cwd=submodule_full_path,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        output = result.stdout.strip()
        h, author, msg, date = output.split("|")
        last_commit = {
            "hash": h,
            "author": author,
            "message": msg,
            "date": date,
        }

        classes = self._all_linker_classes()
        linker_list = []
        for cls in classes:
            info = cls.info()
            config, _ = models.LinkerConfig.objects.get_or_create(linker_id=info.id)
            d = asdict(info)
            d["enabled"] = config.enabled
            linker_list.append(d)

        return Response({"last_commit": last_commit, "linkers": linker_list})

    @action(
        detail=False,
        methods=["POST"],
        permission_classes=[IsAdminUser],
        url_path="set-linker-enabled",
    )
    def set_linker_enabled(self, request: Request) -> Response:
        linker_id = request.data.get("linker_id")
        enabled = request.data.get("enabled")
        if linker_id is None or enabled is None:
            return Response({"error": "linker_id and enabled required"}, status=400)
        config, _ = models.LinkerConfig.objects.get_or_create(linker_id=linker_id)
        config.enabled = (
            bool(enabled)
            if isinstance(enabled, bool)
            else str(enabled).lower() == "true"
        )
        config.save()
        return Response({"linker_id": linker_id, "enabled": config.enabled})

    @action(detail=False, methods=["GET"])
    def search(self, request: Request) -> Response:
        keyword = request.query_params.get("keyword")
        if not keyword:
            return Response(
                "'keyword' query param is required.", status=status.HTTP_400_BAD_REQUEST
            )

        class_list = self._all_linker_classes()
        enabled_ids = set(
            models.LinkerConfig.objects.filter(enabled=True).values_list(
                "linker_id", flat=True
            )
        )
        results = {}
        for cls in class_list:
            info = cls.info()
            if info.id not in enabled_ids:
                continue
            r = [asdict(i) for i in cls.search(keyword)]
            results[info.name] = {"info": asdict(info), "results": r}

        return Response(results)

    @override
    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        linker_id = request.query_params.get("linker")
        if not linker_id:
            raise Exception("linker' query param is required.")

        if not pk:
            raise Exception("Media pk is required.")

        detail = self._get_detail(linker_id, pk)
        return Response(asdict(detail))

    @action(detail=True, methods=["GET"])
    def sources(self, request: Request, pk: str | None = None) -> Response:
        linker_id = request.query_params.get("linker")
        if not linker_id:
            raise Exception("linker' query param is required.")

        if not pk:
            raise Exception("Media pk is required.")

        ep_id = request.query_params.get("ep")
        if not ep_id:
            raise Exception("linker' query param is required.")

        detail = self._get_detail(linker_id, pk)
        return Response({"sources": _sources(detail, ep_id)})

    def _find_class(self, id: str) -> type | None:
        classes = self._all_linker_classes()
        for cls in classes:
            info = cls.info()
            if info.id == id:
                return cls
        return None

    def _all_linker_classes(self) -> list[type]:
        target_path = os.path.join(os.getcwd(), "external_modules", "bunga-link")
        if target_path not in sys.path:
            sys.path.insert(0, target_path)

        module = importlib.import_module("src")
        return [cls for _, cls in inspect.getmembers(module, inspect.isclass)]

    def _get_detail(self, linker_id: str, key: str):
        cache_key = f"gallery:{linker_id}:{key}"
        try:
            cached = Cache.get(cache_key)
        except Exception:
            cached = None
        if cached:
            return cached

        linker = self._find_class(linker_id)
        if not linker:
            raise Exception("No linker found.")

        detail = linker.detail(key)
        Cache.set(cache_key, detail, timeout=5 * 24 * 60 * 60)
        return detail


@cached_function(lambda detail, ep_id: f"gallery:{detail.origin}:{ep_id}")
def _sources(detail, ep_id: str) -> list[dict]:
    sources = detail.fetch_sources(ep_id)
    return [asdict(s) for s in sources]
