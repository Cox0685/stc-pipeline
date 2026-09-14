"""
Shared Azure Data Lake Storage Gen2 helpers for the STC pipeline.

This module exists so the 23 pipeline scripts don't each carry their own copy
of storage connection/auth/retry logic (see: the naming and duplication mess
from the original local-disk audit - not doing that again in Azure).

Implementation note: this talks to the storage account via the plain Blob
API (azure-storage-blob), not the Data Lake-specific SDK. A Data Lake Gen2
filesystem *is* a blob container once hierarchical namespace is enabled on
the account - the Blob API works against it perfectly well for everything
this pipeline needs (upload/download/list-by-prefix/copy). The dedicated
azure-storage-filedatalake SDK is only worth reaching for if you need
directory-level atomic rename/move semantics, which nothing here does. This
also means the same code path is exercised against Azurite for local testing
and against a real ADLS Gen2 account in Azure - no "works in the emulator,
breaks in prod" gap from using two different SDKs.

Configuration comes from environment variables. Two auth modes are supported:

1. PRODUCTION (Container App Job): managed identity, no secrets anywhere.
       ADLS_ACCOUNT_URL     e.g. https://stocustcprd001.blob.core.windows.net
       ADLS_FILESYSTEM      e.g. stc-data
   Authenticates via DefaultAzureCredential, which in Azure resolves to the
   job's user-assigned managed identity automatically.

2. LOCAL DEV STOPGAP: a storage account access key, when Entra sign-in
   itself is blocked (e.g. Conditional Access device-compliance policies
   that also block `az login`) and you need to run the pipeline from a
   laptop while that gets sorted with IT.
       ADLS_CONNECTION_STRING   the full connection string from
                                 Portal -> storage account -> Access keys
       ADLS_FILESYSTEM           e.g. stc-data
   This does NOT touch Entra ID at all - it's a symmetric key, a
   completely different auth mechanism, so it is not affected by
   Conditional Access policies scoped to user sign-in. It is, however, a
   master key with full access to the entire storage account - treat it
   like a password: local .env file only, never committed, never logged,
   and worth rotating in the Portal once you've moved to managed identity
   for real. If ADLS_CONNECTION_STRING is set, it takes priority over
   ADLS_ACCOUNT_URL/DefaultAzureCredential - unset it once you're running
   through the Container App Job so production always uses the identity,
   not a long-lived key.

Paths passed to these functions are POSIX-style relative paths inside the
filesystem, mirroring the old folder structure, e.g.:
    "TNS/incidents_raw.csv"
    "GLD/archive/2026-09-14_101530/gld_sites.csv"
"""

import io
import os
from datetime import datetime
from typing import List, Optional

import pandas as pd
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


class ADLSClient:
    """
    Thin wrapper exposing the handful of operations the pipeline actually
    needs: read a CSV into a DataFrame, write/append a DataFrame as CSV,
    list files under a folder, and copy a file (used by the pre-pull archive
    step). Safe to share across threads for reads; concurrent writes to the
    *same* path are not coordinated here (same rule as the local-disk
    version - don't do that).
    """

    def __init__(self, account_url: Optional[str] = None, filesystem: Optional[str] = None,
                 credential=None, connection_string: Optional[str] = None):
        self.filesystem_name = filesystem or os.environ["ADLS_FILESYSTEM"]

        connection_string = connection_string or os.environ.get("ADLS_CONNECTION_STRING")
        if connection_string:
            # Local dev stopgap - account key auth, no Entra sign-in involved.
            self.account_url = None
            self.credential = None
            self.service_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            # Production path - managed identity (or your `az login` session
            # locally, if that isn't blocked for you).
            self.account_url = account_url or os.environ["ADLS_ACCOUNT_URL"]
            self.credential = credential if credential is not None else DefaultAzureCredential()
            self.service_client = BlobServiceClient(
                account_url=self.account_url, credential=self.credential
            )

        self.container_client = self.service_client.get_container_client(self.filesystem_name)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        try:
            self.container_client.get_blob_client(path).get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False

    def read_csv(self, path: str, **read_csv_kwargs) -> pd.DataFrame:
        """Reads a CSV directly from the data lake into a DataFrame. Same kwargs as pd.read_csv."""
        blob_client = self.container_client.get_blob_client(path)
        data = blob_client.download_blob().readall()
        return pd.read_csv(io.BytesIO(data), **read_csv_kwargs)

    def list_files(self, folder: str, suffix: str = ".csv") -> List[str]:
        """
        Lists files directly under `folder` (top-level only, not recursive) -
        mirrors os.listdir()'s behaviour that the local archive step relied on.
        """
        prefix = folder.rstrip("/") + "/" if folder else ""
        results = []
        for blob in self.container_client.list_blobs(name_starts_with=prefix):
            name = blob.name
            if not name.endswith(suffix):
                continue
            relative = name[len(prefix):]
            if "/" in relative:
                continue  # nested subfolder - not a direct child
            results.append(name)
        return results

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def write_csv(self, df: pd.DataFrame, path: str, **to_csv_kwargs) -> None:
        """Overwrites `path` with the full contents of df."""
        buf = io.StringIO()
        df.to_csv(buf, **to_csv_kwargs)
        data = buf.getvalue().encode("utf-8")
        self.container_client.get_blob_client(path).upload_blob(data, overwrite=True)

    def append_csv(self, df: pd.DataFrame, path: str, **to_csv_kwargs) -> None:
        """
        Appends rows to an existing CSV, writing the header only if the file
        doesn't exist yet. This is the data-lake equivalent of the
        append-only fix made to store_batch_records() on the local pipeline -
        it never reads the whole file back into a DataFrame just to rewrite
        it. It is one blob read + one blob write of raw bytes, not the
        pandas full-frame read/concat/rewrite pattern the original bug had.
        """
        to_csv_kwargs = dict(to_csv_kwargs)
        blob_client = self.container_client.get_blob_client(path)

        if not self.exists(path):
            to_csv_kwargs["header"] = to_csv_kwargs.get("header", True)
            buf = io.StringIO()
            df.to_csv(buf, **to_csv_kwargs)
            blob_client.upload_blob(buf.getvalue().encode("utf-8"), overwrite=False)
            return

        to_csv_kwargs["header"] = False
        buf = io.StringIO()
        df.to_csv(buf, **to_csv_kwargs)
        new_bytes = buf.getvalue().encode("utf-8")

        existing_bytes = blob_client.download_blob().readall()
        blob_client.upload_blob(existing_bytes + new_bytes, overwrite=True)

    def copy_file(self, source_path: str, dest_path: str) -> None:
        """
        Copy within the same filesystem/account - used by the pre-pull
        archive step.
        """
        source_client = self.container_client.get_blob_client(source_path)
        dest_client = self.container_client.get_blob_client(dest_path)
        dest_client.upload_blob(source_client.download_blob().readall(), overwrite=True)


def get_client() -> ADLSClient:
    """Convenience factory - most scripts just need one client."""
    return ADLSClient()


def archive_folder(client: ADLSClient, folder: str, run_stamp: Optional[str] = None) -> int:
    """
    Data-lake equivalent of the local pre-pull archive step: copies every CSV
    directly under `folder` into `folder/archive/<run_stamp>/`. Returns the
    number of files archived. Never recurses into its own archive/ output,
    since list_files() only lists direct children of `folder` itself.
    """
    run_stamp = run_stamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    csv_files = client.list_files(folder)
    for f in csv_files:
        filename = f.rsplit("/", 1)[-1]
        dest = f"{folder}/archive/{run_stamp}/{filename}"
        client.copy_file(f, dest)
    return len(csv_files)
