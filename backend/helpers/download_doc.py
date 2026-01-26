from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

LAKEHOUSE_NAME = "csj_documentos"


@dataclass
class OneLakeDownloader:
    def normalize_dfs_url(self, url: str) -> str:
        u = (url or "").strip().replace("\\", "/")

        # arregla duplicación Lakehouse/Files
        dup = f"/{LAKEHOUSE_NAME}.Lakehouse/Files/{LAKEHOUSE_NAME}.Lakehouse/Files/"
        u = u.replace(dup, f"/{LAKEHOUSE_NAME}.Lakehouse/Files/")

        # arregla dobles slashes (sin dañar https://)
        if "://" in u:
            scheme, rest = u.split("://", 1)
            while "//" in rest:
                rest = rest.replace("//", "/")
            u = scheme + "://" + rest

        return u

    def download_bytes(self, dfs_url: str) -> bytes:
        """
        dfs_url:
        https://onelake.dfs.fabric.microsoft.com/<workspace>/<lakehouse>.Lakehouse/Files/...
        """
        dfs_url = self.normalize_dfs_url(dfs_url)
        u = urlparse(dfs_url)

        # dfs -> blob host
        host_blob = u.netloc.replace(".dfs.", ".blob.")
        account_url = f"{u.scheme}://{host_blob}"

        # path: /<workspace>/<item>.<type>/<rest>
        parts = u.path.lstrip("/").split("/", 2)
        if len(parts) < 3:
            raise ValueError(f"DFS URL inválida: {dfs_url}")

        container_name = parts[0]              # workspace
        blob_name = f"{parts[1]}/{parts[2]}"   # <lakehouse>.Lakehouse/Files/...

        credential = DefaultAzureCredential()
        service = BlobServiceClient(account_url=account_url, credential=credential)
        blob = service.get_blob_client(container=container_name, blob=blob_name)

        return blob.download_blob().readall()
