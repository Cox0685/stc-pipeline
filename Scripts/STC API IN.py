#!/usr/bin/env python
# coding: utf-8

"""
STC API IN - Local Version with CSV Output (3 Columns) - SEQUENTIAL
Outputs to: C:/Users/Thomas.Cox/OneDrive - OCU Group/Desktop/00_AST_SystemsIntegration/00_AST_DataUploads/01_STC Safety Culture/Data/TNS
Columns: ExactJSON, ParentID, IngestedAt
"""

import json
import requests
import time
import re
import os
import sys
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# MANIFEST - Same as original, with all missions enabled
# ============================================================================

MANIFEST = {
    "Global_Config": {
        "Base_URL": "https://api.safetyculture.io",
        "API_Key": "scapi_q3vGKiUidmaq5646BCLYGSOyoD1yEwlN02xBdc1QSX1M_tnpMCRaHXr6YqSMvrpRCB93JceBnXk4gX1EMZRWHs0EvIPHaOaksiQSr0ZUI6VXBjWVhqH3HeoU_p_64StMy1p9nbqQPAO7GEKw9tzro1fCU8KADaEuAHKEk1aLbF4",
        "Global Settings": {
            "Default_Timeout": 60,
            "Max_Retries": 3,
            "Retry_Delay": 5,
            "Rate_Limit_Delay": 0.5,
            "Enable_Rate_Limiting": True,
            "Batch_Commit_Size": 100
        }
    },
    "Endpoint_Definitions": {
    "Groups_List": {
        "Verb": "GET",
        "Endpoint": "/groups",
        "Pagination_Type": "None",
        "Response_Mapping": {
            "Record_Location": ["groups"]
        },
        "Table": "groups_list"
    },
    "Groups_Users": {
        "Verb": "GET",
        "Endpoint": "/groups/{{group_id}}/users",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Groups_List",
        "Parent_ID_Key": "id",
        "Response_Mapping": {
            "Record_Location": ["users"]
        },
        "Table": "group_users"
    },
    "HeadsUp_List": {
        "Verb": "POST",
        "Endpoint": "/announcements/v1/announcement:ListHeadsUpManage",
        "Pagination_Type": "Body_Token",
        "Page_Size": 100,
        "Payload_Template": {
            "page_size": "{{PAGE_SIZE}}",
            "page_token": "{{PAGE_TOKEN}}"
        },
        "Response_Mapping": {
            "Record_Location": ["heads_ups"],
            "Token_Location": ["next_page_token"],
            "Total_Location": ["total"]
        },
        "Table": "headsup_list"
    },
    "HeadsUp_Users": {
        "Verb": "POST",
        "Endpoint": "/announcements/v1/announcement:ListHeadsUpUsers",
        "Pagination_Type": "Offset",
        "Page_Size": 100,
        "Payload_Template": {
            "heads_up_id": "{{PARENT_ID}}",
            "page_size": "{{PAGE_SIZE}}",
            "offset": "{{OFFSET}}"
        },
        "Requires_Parent": True,
        "Parent_Endpoint": "HeadsUp_List",
        "Parent_ID_Key": "id",
        "Response_Mapping": {
            "Record_Location": ["users"],
            "Total_Location": ["total"]
        },
        "Table": "headsup_users"
    },
    "Audits_Search": {
        "Verb": "GET",
        "Endpoint": "/feed/inspections",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "modified_after": "{{MODIFIED_DATE}}",
            "limit": "{{PAGE_SIZE}}"
        },
        "Incremental": {
            "Supports_Incremental": True,
            "Date_Parameter": "modified_after",
            "Date_Parameter_Location": "params",
            "Initial_Backfill_Days": 2
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "remaining_records"]
        },
        "Table": "inspections_list"
    },
    "Audits_Details": {
        "Verb": "GET",
        "Endpoint": "/inspections/v1/inspections/{{audit_id}}",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Audits_Search",
        "Parent_ID_Key": ["audit_id", "id"],
        "Response_Mapping": {
            "Record_Location": ["inspection"]
        },
        "Table": "inspection_details"
    },
    "Inspections_Answers": {
        "Verb": "GET",
        "Endpoint": "/inspections/v1/answers/{{audit_id}}",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Audits_Search",
        "Parent_ID_Key": ["audit_id", "id"],
        "Response_Format": "NDJSON",
        "Response_Mapping": {
            "Record_Location": ["result"]
        },
        "Table": "inspection_answers"
    },
    "Companies_List": {
        "Verb": "POST",
        "Endpoint": "/companies/v1beta/companies",
        "Pagination_Type": "Body_Token",
        "Page_Size": 100,
        "Payload_Template": {
            "page_token": "{{PAGE_TOKEN}}"
        },
        "Response_Mapping": {
            "Record_Location": ["contractor_company_list"],
            "Token_Location": ["next_page_token"],
            "Total_Location": ["total_count"]
        },
        "Table": "companies_list"
    },
    "Companies_Detail": {
        "Verb": "GET",
        "Endpoint": "/companies/v1/company",
        "Pagination_Type": "None",
        "URL_Params": {
            "company_id": "{{PARENT_ID}}"
        },
        "Requires_Parent": True,
        "Parent_Endpoint": "Companies_List",
        "Parent_ID_Key": "company_id",
        "Response_Mapping": {
            "Record_Location": ["contractor_company"]
        },
        "Table": "company_details"
    },
    "Companies_Users": {
        "Verb": "POST",
        "Endpoint": "/companies/v1/users",
        "Pagination_Type": "Body_Token",
        "Page_Size": 10,
        "Payload_Template": {
            "company_id": "{{PARENT_ID}}",
            "page_token": "{{PAGE_TOKEN}}"
        },
        "Requires_Parent": True,
        "Parent_Endpoint": "Companies_List",
        "Parent_ID_Key": "company_id",
        "Response_Mapping": {
            "Record_Location": ["users"],
            "Token_Location": ["next_page_token"]
        },
        "Table": "company_users"
    },
    "Actions_Feed": {
        "Verb": "GET",
        "Endpoint": "/feed/actions",
        "Pagination_Type": "URL_Token",
        "Page_Size": 500,
        "URL_Params": {
            "modified_after": "{{MODIFIED_DATE}}",
            "next_page_token": "{{PAGE_TOKEN}}",
            "limit": "{{PAGE_SIZE}}"
        },
        "Incremental": {
            "Supports_Incremental": True,
            "Date_Parameter": "modified_after",
            "Date_Parameter_Location": "params",
            "Initial_Backfill_Days": 2
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "total"]
        },
        "Table": "actions_list"
    },
    "Actions_Retrieve": {
        "Verb": "GET",
        "Endpoint": "/tasks/v1/actions/{{action_id}}",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Actions_Feed",
        "Parent_ID_Key": "id",
        "Response_Mapping": {
            "Record_Location": ["action"]
        },
        "Table": "action_details"
    },
    "Incidents_Feed": {
        "Verb": "GET",
        "Endpoint": "/incidents/v1/feed/investigations",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}",
            "next_page_token": "{{PAGE_TOKEN}}"
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "total"]
        },
        "Table": "investigations_list"
    },
    "Incidents_Details": {
        "Verb": "GET",
        "Endpoint": "/incidents/v1/investigations/{{investigation_id}}",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Incidents_Feed",
        "Parent_ID_Key": "investigation_id",
        "Response_Mapping": {
            "Record_Location": ["investigation"]
        },
        "Table": "investigation_details"
    },
    "Templates_Feed": {
        "Verb": "GET",
        "Endpoint": "/feed/templates",
        "Pagination_Type": "URL_Token",
        "Page_Size": 1000,
        "URL_Params": {
            "modified_after": "{{MODIFIED_DATE}}",
            "limit": "{{PAGE_SIZE}}"
        },
        "Incremental": {
            "Supports_Incremental": True,
            "Date_Parameter": "modified_after",
            "Date_Parameter_Location": "params",
            "Initial_Backfill_Days": 2
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "remaining_records"]
        },
        "Table": "templates_list"
    },
    "Templates_List": {
        "Verb": "GET",
        "Endpoint": "/feed/templates",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}"
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "remaining_records"]
        },
        "Table": "templates_compact_list"
    },
    "Users_Feed": {
        "Verb": "GET",
        "Endpoint": "/feed/users",
        "Pagination_Type": "URL_Token",
        "Page_Size": 1000,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}",
            "next_page_token": "{{PAGE_TOKEN}}"
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "total"]
        },
        "Table": "users_list"
    },
    "User_Groups": {
        "Verb": "GET",
        "Endpoint": "/accounts/organisation/v1/accounts/user/{{user_id}}/groups",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Users_Feed",
        "Parent_ID_Key": "id",
        "Response_Mapping": {
            "Record_Location": ["groups"]
        },
        "Table": "user_groups"
    },
    "Issues_List": {
        "Verb": "POST",
        "Endpoint": "/tasks/v1/incidents/list",
        "Pagination_Type": "Body_Token",
        "Page_Size": 100,
        "Payload_Template": {
            "page_size": "{{PAGE_SIZE}}",
            "page_token": "{{PAGE_TOKEN}}",
            "filters": [
                {
                    "modified_at": {
                        "from": "{{MODIFIED_DATE}}"
                    }
                }
            ]
        },
        "Incremental": {
            "Supports_Incremental": True,
            "Date_Parameter": "modified_at",
            "Date_Parameter_Location": "payload",
            "Initial_Backfill_Days": 2
        },
        "Response_Mapping": {
            "Record_Location": ["incidents"],
            "Token_Location": ["next_page_token"],
            "Total_Location": ["total"]
        },
        "Table": "issues_list"
    },
    "Issues_Details": {
        "Verb": "GET",
        "Endpoint": "/tasks/v1/incident/{{incident_id}}",
        "Pagination_Type": "None",
        "Requires_Parent": True,
        "Parent_Endpoint": "Issues_List",
        "Parent_ID_Key": ["task", "task_id"],
        "Response_Mapping": {
            "Record_Location": ["incident"]
        },
        "Table": "issue_details"
    },
    "Issues_Answers": {
    "Verb": "GET",
    "Endpoint": "/tasks/v1/incidents/{{incident_id}}/questions_answers",
    "Pagination_Type": "None",
    "Requires_Parent": True,
    "Parent_Endpoint": "Issues_List",
    "Parent_ID_Key": ["task", "task_id"],
    "Response_Mapping": {
        "Record_Location": ["questions_answers"]  # Changed from ["data"] to ["questions_answers"]
    },
    "Table": "issues_answers"
},
    "Sites_List": {
        "Verb": "GET",
        "Endpoint": "/feed/sites",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}"
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "remaining_records"]
        },
        "Table": "sites_list"
    },
    "Site_Members": {
        "Verb": "GET",
        "Endpoint": "/feed/site_members",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}"
        },
        # FIXED: this was wrongly configured as a parent-child chain off
        # Sites_List. /feed/site_members is an organisation-wide FEED
        # endpoint (same shape as /feed/actions, /feed/users,
        # /feed/templates, /feed/sites - all standalone) - it has no
        # {{parent_id}} placeholder anywhere in its path or URL_Params, so
        # the parent site ID was never actually being sent. Every site was
        # independently re-pulling the ENTIRE organisation's member feed,
        # once per site, in parallel - confirmed live locally as the
        # "insane loop" of hundreds of pages with no end in sight. Now
        # standalone, pulled once, matching its siblings.
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["metadata", "remaining_records"]
        },
        "Table": "site_members"
    },
    "Schedule_Items": {
        "Verb": "GET",
        "Endpoint": "/scheduling/v1/feed/schedules",
        "Pagination_Type": "URL_Token",
        "Page_Size": 100,
        "URL_Params": {
            "limit": "{{PAGE_SIZE}}"
        },
        "Response_Mapping": {
            "Record_Location": ["data"],
            "Token_Location": ["metadata", "next_page"],
            "Total_Location": ["total_records"]
        },
        "Table": "schedule_items"
    }
},
    "Missions": [
    {"Name": "Issues", "Endpoint": "Issues_List", "Enabled": True},
    {"Name": "Issue Details", "Endpoint": "Issues_Details", "Enabled": True},
    {"Name": "Issues Answers", "Endpoint": "Issues_Answers", "Enabled": True},
    {"Name": "Groups", "Endpoint": "Groups_List", "Enabled": True},
    {"Name": "Group Users", "Endpoint": "Groups_Users", "Enabled": True},
    {"Name": "HeadsUp", "Endpoint": "HeadsUp_List", "Enabled": True},  # was False - never actually enabled for online ingestion
    {"Name": "HeadsUp Users", "Endpoint": "HeadsUp_Users", "Enabled": True},  # was False - same
    {"Name": "Inspections", "Endpoint": "Audits_Search", "Enabled": True},
    {"Name": "Inspection Details", "Endpoint": "Audits_Details", "Enabled": True},
    {"Name": "Inspection Answers", "Endpoint": "Inspections_Answers", "Enabled": True},
    {"Name": "Companies", "Endpoint": "Companies_List", "Enabled": False},
    {"Name": "Company Details", "Endpoint": "Companies_Detail", "Enabled": False},
    {"Name": "Company Users", "Endpoint": "Companies_Users", "Enabled": False},
    {"Name": "Actions", "Endpoint": "Actions_Feed", "Enabled": True},
    {"Name": "Action Details", "Endpoint": "Actions_Retrieve", "Enabled": True},
    {"Name": "Incidents", "Endpoint": "Incidents_Feed", "Enabled": True},
    {"Name": "Incident Details", "Endpoint": "Incidents_Details", "Enabled": True},
    {"Name": "Templates", "Endpoint": "Templates_Feed", "Enabled": True},
    {"Name": "Templates Compact", "Endpoint": "Templates_List", "Enabled": True},
    {"Name": "Users", "Endpoint": "Users_Feed", "Enabled": True},
    {"Name": "Sites", "Endpoint": "Sites_List", "Enabled": True},
    {"Name": "Site Members", "Endpoint": "Site_Members", "Enabled": True},  # was False - now safe as a standalone pull, see fix above
    {"Name": "User Groups", "Endpoint": "User_Groups", "Enabled": True},
    {"Name": "Schedule Items", "Endpoint": "Schedule_Items", "Enabled": False}
]
}

print(f"✅ Manifest loaded: {len(MANIFEST['Endpoint_Definitions'])} endpoints, {len(MANIFEST['Missions'])} missions")

# ============================================================================
# RUNTIME OVERRIDES (set by the calling GitHub Actions workflow - optional)
# ============================================================================
# Lets the workflow control which missions run without editing this file
# directly - e.g. run-pipeline.yml uses this to skip User_Groups on every
# day except Friday (that one mission alone was seen taking 2.5+ hours
# with the current user count, which doesn't need refreshing daily). If
# the env var isn't set, the MANIFEST above is used exactly as written.

_mission_overrides_raw = os.environ.get("MISSION_ENABLED_OVERRIDES")
if _mission_overrides_raw:
    try:
        _mission_overrides = json.loads(_mission_overrides_raw)
        _override_count = 0
        _unknown_endpoints = []
        _known_endpoints = {m["Endpoint"] for m in MANIFEST["Missions"]}
        for _mission in MANIFEST["Missions"]:
            _endpoint = _mission["Endpoint"]
            if _endpoint in _mission_overrides:
                _mission["Enabled"] = _mission_overrides[_endpoint]
                _override_count += 1
        for _endpoint_name in _mission_overrides:
            if _endpoint_name not in _known_endpoints:
                _unknown_endpoints.append(_endpoint_name)
        print(f"🔧 Applied {_override_count} mission enable/disable override(s) from the workflow")
        if _unknown_endpoints:
            print(f"   ⚠️ {len(_unknown_endpoints)} override(s) didn't match any known mission: {_unknown_endpoints}")
    except Exception as e:
        print(f"⚠️ Could not parse MISSION_ENABLED_OVERRIDES - ignoring, using MANIFEST as written: {e}")

# ============================================================================
# LOCAL SAFETYCULTURE INGESTOR - SEQUENTIAL (No Threading)
# ============================================================================

class _RateLimiter:
    """
    Thread-safe token-bucket limiter shared by every worker thread. Every
    HTTP call in this file funnels through execute_request(), which calls
    acquire() here first - so no matter how many threads or mission-level
    pools are firing at once, the actual rate of requests hitting the API
    never exceeds `rate_per_second`. This is what makes it safe to turn up
    concurrency elsewhere without risking a 429 storm.
    """
    def __init__(self, rate_per_second: float):
        self.rate = max(float(rate_per_second), 0.1)
        self.capacity = max(int(self.rate), 1)
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.last_refill = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            time.sleep(wait)


class LocalSafetyCultureIngestor:
    """Local CSV-based SafetyCulture API Ingestor - SEQUENTIAL - 3 Columns: ExactJSON, ParentID, IngestedAt"""
    
    def __init__(self, manifest: Dict, 
                 test_mode: bool = False, test_limit: int = 50):
        self.manifest = manifest
        self.test_mode = test_mode
        self.test_limit = test_limit
        
        self.config = manifest['Global_Config']
        self.endpoints = manifest['Endpoint_Definitions']
        self.missions = manifest['Missions']
        self.global_settings = self.config.get('Global Settings', {})
        
        self.base_url = self.config['Base_URL']
        self.api_key = self.config['API_Key']
        
        # DATA LAKE STORAGE PATH
        # This used to be a local OneDrive Windows path - now it's a folder
        # inside the ADLS Gen2 filesystem the Container App Job is granted
        # access to via its managed identity (see infra/main.bicep). No
        # connection string or key lives here; azure_io picks up
        # ADLS_ACCOUNT_URL / ADLS_FILESYSTEM from the environment and
        # authenticates with DefaultAzureCredential.
        self.local_data_path = "TNS"
        self.adls_client = azure_io.get_client()
        
        self.write_batch_size = self.global_settings.get('Batch_Commit_Size', 100)
        
        # Concurrency for per-parent child fetches (Stage: parent-child chains).
        # These are independent HTTP calls that were previously fired one at a
        # time with a sleep() between them - almost all wall-clock time there
        # was network wait, so a small thread pool gives a near-linear speedup.
        # Kept modest by default to stay polite to the API and avoid tripping
        # rate limits; raise Child_Fetch_Workers in Global Settings if the API
        # comfortably takes more.
        self.child_fetch_workers = self.global_settings.get('Child_Fetch_Workers', 8)
        
        # One persistent, retry-hardened session per worker thread, reused
        # across every parent it processes - not a fresh session per parent.
        # Opening a brand new session per parent meant a fresh DNS lookup +
        # TCP/TLS handshake on every single call, which is both slow and the
        # likely cause of intermittent "getaddrinfo failed" errors under
        # concurrency (too many simultaneous fresh connections hammering the
        # resolver). Reusing a session lets requests keep the connection
        # alive between calls on the same thread.
        self._thread_local = threading.local()
        
        # Global request-rate governor. This is the actual answer to "make it
        # faster with more engines" - concurrency alone doesn't help once
        # you're hitting the API's own rate limit; it just trades slow serial
        # requests for a pile of 429s that retry into the same ceiling.
        # SafetyCulture doesn't publish a fixed public number for every
        # account/token tier, so 8 req/sec below is a conservative starting
        # point, not a confirmed limit - check the `Retry-After` / rate-limit
        # headers on a real response (or your account's API docs) and raise
        # Requests_Per_Second in Global Settings once you know your real
        # ceiling. Every HTTP call this class makes - parent, child, or
        # standalone, from any thread or mission - passes through this one
        # limiter, so raising concurrency elsewhere is now safe: it just
        # keeps the pipe full instead of exceeding whatever cap you set here.
        self.requests_per_second = self.global_settings.get('Requests_Per_Second', 8)
        self.rate_limiter = _RateLimiter(self.requests_per_second)
        
        # Hard cap on manual 429 retries for standalone endpoints (see
        # _process_single_endpoint). Without this, a sustained rate limit
        # on a big endpoint retries forever - no error, no timeout, just
        # an indefinite sleep loop.
        self.max_429_retries = self.global_settings.get('Max_429_Retries', 5)
        
        # Per-future timeouts. The 429 cap above stops ONE HTTP call from
        # retrying forever, but that alone doesn't stop a future.result()
        # call from blocking forever if a thread hangs somewhere else.
        # Without these, a single stuck thread could block the whole
        # ThreadPoolExecutor's "with" block from ever exiting.
        self.child_fetch_timeout_seconds = self.global_settings.get('Child_Fetch_Timeout_Seconds', 180)
        self.mission_timeout_seconds = self.global_settings.get('Mission_Timeout_Seconds', 1800)
        
        # Opt-in only - printing this for every single parent (potentially
        # thousands across a full run) would massively bloat normal logs.
        # Flip this on specifically when chasing a hang: it prints which
        # parent ID (and page) a thread is about to request BEFORE making
        # the call, so if a thread stalls, the last such line printed for
        # that thread tells you exactly which API call never came back.
        self.verbose_child_fetch_logging = self.global_settings.get('Verbose_Child_Fetch_Logging', False)
        
        # How many parent-child chains / standalone endpoints run at once.
        # These hit different endpoints entirely, so there's no reason to
        # process them one at a time - the rate limiter above is what keeps
        # the API happy, not this.
        self.chain_concurrency = self.global_settings.get('Chain_Concurrency', 3)
        
        print(f"[{self.get_timestamp()}] 🚀 LOCAL Ingestor initialized (SEQUENTIAL - 3-Column CSV)")
        print(f"   🔗 Base URL: {self.base_url}")
        print(f"   📁 Data Path: {self.local_data_path}")
        print(f"   🧪 Test Mode: {'ON' if self.test_mode else 'OFF'}")
        if self.test_mode:
            print(f"   📊 Test Limit: {self.test_limit} records per endpoint")
        print(f"   📦 Write Batch Size: {self.write_batch_size}")
        print(f"   📋 Columns: ExactJSON, ParentID, IngestedAt")
    
    def get_timestamp(self) -> str:
        return datetime.now().strftime('%H:%M:%S')
    
    def _get_table_path(self, table_name: str) -> str:
        """Get the data-lake path for a table (folder/filename.csv inside the filesystem)"""
        clean_name = table_name.lower().replace(" ", "_").replace("-", "_")
        return f"{self.local_data_path}/{clean_name}.csv"
    
    def store_batch_records(self, records: List[Dict], endpoint_name: str,
                           parent_id: str = None) -> int:
        """Store records to local CSV file with 3 columns: ExactJSON, ParentID, IngestedAt"""
        if not records:
            return 0
        
        if self.test_mode and len(records) > self.test_limit:
            records = records[:self.test_limit]
        
        try:
            file_path = self._get_table_path(endpoint_name)
            
            # Prepare rows for CSV - EXACTLY 3 columns
            rows = []
            current_time = datetime.now().isoformat()
            
            for record in records:
                # ExactJSON: the complete, untampered JSON as a string
                exact_json = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
                
                rows.append({
                    'ExactJSON': exact_json,
                    'ParentID': parent_id if parent_id else '',
                    'IngestedAt': current_time
                })
            
            # Convert to DataFrame
            df_new = pd.DataFrame(rows)
            
            # Ensure columns are in the right order
            df_new = df_new[['ExactJSON', 'ParentID', 'IngestedAt']]
            
            # APPEND-ONLY WRITE: never read the existing file back into a
            # DataFrame just to rewrite it. azure_io.append_csv does one
            # blob read (raw bytes) + one blob write, same principle as the
            # earlier local-disk fix - it just never had a local filesystem
            # to fall back on, so this is the ADLS-native version of the
            # same rule.
            self.adls_client.append_csv(
                df_new,
                file_path,
                index=False,
                encoding='utf-8'
            )
            
            return len(records)
            
        except Exception as e:
            print(f"      [{self.get_timestamp()}] ❌ Failed to store: {e}")
            return 0
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Transport-level retry: covers transient DNS failures
        # (getaddrinfo failed), connection resets, and 5xx/429 responses
        # automatically, before execute_request even sees a problem.
        retry_strategy = Retry(
            total=4,
            connect=4,
            read=2,
            backoff_factor=1.5,          # 0s, 1.5s, 3s, 6s, 12s between attempts
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=20, pool_connections=20)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def _get_thread_session(self) -> requests.Session:
        """Returns this thread's persistent session, creating it on first use."""
        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = self._create_session()
        return self._thread_local.session
    
    def _extract_parent_id(self, parent: Dict, parent_id_key: Any) -> Optional[str]:
        """Extract parent ID from a parent record."""
        if isinstance(parent_id_key, list):
            # First, try treating as a path
            result = parent
            all_dicts = True
            for key in parent_id_key:
                if isinstance(result, dict) and key in result:
                    result = result[key]
                else:
                    all_dicts = False
                    break
            
            if all_dicts and not isinstance(result, dict):
                return str(result)
            
            # Try each key as a simple alternative
            for key in parent_id_key:
                if isinstance(parent, dict) and key in parent:
                    val = parent[key]
                    if not isinstance(val, dict):
                        return str(val)
            
            # Last resort: path approach
            result = parent
            for key in parent_id_key:
                if isinstance(result, dict):
                    result = result.get(key)
                    if result is None:
                        return None
                else:
                    return None
            return str(result) if result is not None else None
            
        elif isinstance(parent_id_key, str):
            if '.' in parent_id_key:
                parts = parent_id_key.split('.')
                result = parent
                for part in parts:
                    if isinstance(result, dict):
                        result = result.get(part)
                        if result is None:
                            return None
                    else:
                        return None
                return str(result) if result is not None else None
            else:
                val = parent.get(parent_id_key)
                return str(val) if val is not None else None
        
        return None
    
    def execute_request(self, session: requests.Session, url: str, 
                        params: Dict = None, payload: Dict = None, 
                        timeout: int = 30) -> Optional[requests.Response]:
        self.rate_limiter.acquire()
        try:
            if payload:
                return session.post(url, json=payload, params=params, timeout=timeout)
            else:
                return session.get(url, params=params, timeout=timeout)
        except Exception as e:
            print(f"      [{self.get_timestamp()}] ❌ Request error: {e}")
            return None
    
    def get_date_filter(self, endpoint_def: Dict) -> str:
        incremental = endpoint_def.get('Incremental', {})
        if not incremental.get('Supports_Incremental', False):
            return ''
        days_back = incremental.get('Initial_Backfill_Days', 30)
        return (datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'
    
    def build_url(self, endpoint_def: Dict, params: Dict = None) -> str:
        endpoint = endpoint_def['Endpoint']
        if params:
            for key, value in params.items():
                endpoint = endpoint.replace(f"{{{{{key}}}}}", str(value))
        if endpoint.startswith('/') and self.base_url.endswith('/'):
            endpoint = endpoint[1:]
        return f"{self.base_url}{endpoint}"
    
    def build_url_from_path(self, path: str) -> str:
        if path.startswith('/'):
            return f"{self.base_url}{path}"
        return path
    
    def build_params_payload(self, endpoint_def: Dict, page_token: str = None, 
                            page_size: int = None, parent_id: str = None,
                            modified_date: str = None, offset: int = None) -> Tuple[Dict, Dict]:
        pagination_type = endpoint_def.get('Pagination_Type', 'None')
        params = {}
        payload = {}
        
        url_params = endpoint_def.get('URL_Params', {})
        if url_params:
            for key, value_template in url_params.items():
                substituted = value_template
                substituted = substituted.replace('{{PAGE_SIZE}}', str(page_size or endpoint_def.get('Page_Size', 100)))
                substituted = substituted.replace('{{PAGE_TOKEN}}', page_token or '')
                substituted = substituted.replace('{{MODIFIED_DATE}}', modified_date or self.get_date_filter(endpoint_def))
                substituted = substituted.replace('{{PARENT_ID}}', parent_id or '')
                substituted = substituted.replace('{{OFFSET}}', str(offset or 0))
                params[key] = substituted
        
        payload_template = endpoint_def.get('Payload_Template')
        if payload_template:
            payload = self._substitute_payload(
                payload_template, page_token, page_size, parent_id, modified_date, offset
            )
        
        if pagination_type == 'Offset' and offset is not None:
            params['limit'] = page_size or endpoint_def.get('Page_Size', 100)
            params['offset'] = offset
        
        return params, payload
    
    def _substitute_payload(self, template: Any, page_token: str, page_size: int, 
                           parent_id: str, modified_date: str, offset: int = None) -> Any:
        if isinstance(template, dict):
            return {k: self._substitute_payload(v, page_token, page_size, parent_id, modified_date, offset) 
                   for k, v in template.items()}
        elif isinstance(template, list):
            return [self._substitute_payload(item, page_token, page_size, parent_id, modified_date, offset) 
                   for item in template]
        elif isinstance(template, str):
            return template.replace('{{PAGE_SIZE}}', str(page_size if page_size else 100)) \
                          .replace('{{PAGE_TOKEN}}', page_token or '') \
                          .replace('{{PARENT_ID}}', parent_id or '') \
                          .replace('{{MODIFIED_DATE}}', modified_date or '') \
                          .replace('{{OFFSET}}', str(offset or 0))
        return template
    
    def parse_ndjson_response(self, response_text: str) -> List[Dict]:
        if not response_text or not response_text.strip():
            return []
        
        records = []
        for line in response_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"raw_line": line})
        return records
    
    def extract_records(self, data: Any, endpoint_def: Dict) -> List[Any]:
        response_format = endpoint_def.get('Response_Format', 'JSON')
        
        if isinstance(data, list) and response_format == 'NDJSON':
            return data
        
        if not data:
            return []
        
        response_mapping = endpoint_def.get('Response_Mapping', {})
        record_location = response_mapping.get('Record_Location', ['data'])
        
        result = data
        for key in record_location:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return []
            else:
                return []
        
        if result is None:
            return []
        
        return result if isinstance(result, list) else [result]
    
    def get_next_token(self, data: Dict, endpoint_def: Dict) -> Optional[str]:
        response_mapping = endpoint_def.get('Response_Mapping', {})
        token_location = response_mapping.get('Token_Location')
        if not token_location:
            return None
        
        result = data
        for key in token_location:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return None
            else:
                return None
        return result
    
    def _process_single_endpoint(self, endpoint_name: str, endpoint_def: Dict) -> Tuple[int, int]:
        """Process a single standalone endpoint"""
        session = self._create_session()
        
        page_size = endpoint_def.get('Page_Size', 100)
        pagination_type = endpoint_def.get('Pagination_Type', 'None')
        response_format = endpoint_def.get('Response_Format', 'JSON')
        
        print(f"\n[{self.get_timestamp()}] 📋 EXTRACTING: {endpoint_name}")
        
        page_token = None
        offset = 0
        has_more = True
        successful = 0
        failed = 0
        page_count = 0
        next_page_path = None
        timeout = 30
        modified_date = self.get_date_filter(endpoint_def)
        accumulated_records = []
        total_collected = 0
        consecutive_429s = 0
        
        while has_more:
            # Check if we've reached test limit BEFORE making another request
            if self.test_mode and total_collected >= self.test_limit:
                print(f"   [{self.get_timestamp()}] 🧪 TEST MODE: Reached limit of {self.test_limit} records")
                break
            
            page_count += 1
            
            if next_page_path:
                url = self.build_url_from_path(next_page_path)
                params = {}
                payload = None
            else:
                url = self.build_url(endpoint_def)
                if pagination_type == 'Offset':
                    params, payload = self.build_params_payload(
                        endpoint_def, None, page_size, None, modified_date, offset
                    )
                else:
                    params, payload = self.build_params_payload(
                        endpoint_def, page_token, page_size, None, modified_date
                    )
            
            try:
                resp = self.execute_request(session, url, params, payload, timeout)
                if not resp or resp.status_code != 200:
                    if resp:
                        if resp.status_code == 429:
                            consecutive_429s += 1
                            if consecutive_429s > self.max_429_retries:
                                print(f"   [{self.get_timestamp()}] 🛑 {endpoint_name}: gave up after "
                                      f"{self.max_429_retries} consecutive 429s on this page - "
                                      f"moving on instead of hanging. Records collected so far "
                                      f"({total_collected}) are still kept.")
                                break
                            retry_after = int(resp.headers.get('Retry-After', 5))
                            print(f"   [{self.get_timestamp()}] ⏱️ Rate limited - waiting {retry_after}s "
                                  f"(attempt {consecutive_429s}/{self.max_429_retries})")
                            time.sleep(retry_after)
                            continue
                    break
                
                consecutive_429s = 0
                
                if response_format == 'NDJSON':
                    records = self.parse_ndjson_response(resp.text)
                    records = self.extract_records(records, endpoint_def)
                else:
                    data = resp.json()
                    records = self.extract_records(data, endpoint_def)
                
                if records:
                    # Calculate how many we can take
                    remaining = self.test_limit - total_collected if self.test_mode else len(records)
                    if self.test_mode and remaining <= 0:
                        has_more = False
                        break
                    
                    if self.test_mode and len(records) > remaining:
                        records = records[:remaining]
                        has_more = False
                    
                    total_collected += len(records)
                    accumulated_records.extend(records)
                    print(f"   [{self.get_timestamp()}] 📦 Page {page_count}: {len(records)} records (total: {total_collected})")
                    
                    # Write batch if needed
                    if len(accumulated_records) >= self.write_batch_size:
                        inserted = self.store_batch_records(accumulated_records, endpoint_name)
                        successful += inserted
                        failed += len(accumulated_records) - inserted
                        accumulated_records = []
                    
                    # Check pagination
                    if self.test_mode and total_collected >= self.test_limit:
                        has_more = False
                        print(f"   [{self.get_timestamp()}] 🧪 TEST MODE: Reached limit of {self.test_limit} records")
                        break
                    
                    if response_format == 'NDJSON':
                        has_more = False
                    elif pagination_type == 'Offset':
                        offset += len(records)
                        if offset >= data.get('total', 0):
                            has_more = False
                    elif pagination_type in ['URL_Token', 'Body_Token']:
                        next_token = self.get_next_token(data, endpoint_def)
                        if next_token:
                            if isinstance(next_token, str) and next_token.startswith('/'):
                                next_page_path = next_token
                                page_token = None
                            else:
                                page_token = next_token
                                next_page_path = None
                        else:
                            has_more = False
                    else:
                        has_more = False
                else:
                    print(f"   [{self.get_timestamp()}] ℹ️ No records found")
                    has_more = False
                    
            except Exception as e:
                print(f"   [{self.get_timestamp()}] ❌ Exception: {e}")
                break
        
        # Write any remaining records
        if accumulated_records:
            inserted = self.store_batch_records(accumulated_records, endpoint_name)
            successful += inserted
            failed += len(accumulated_records) - inserted
        
        session.close()
        print(f"   [{self.get_timestamp()}] ✅ {endpoint_name}: {successful} inserted, {failed} failed, {page_count} pages")
        return successful, failed
    
    def _process_parent_child_chain(self, parent_name: str, child_name: str) -> Tuple[int, int]:
        """Process a parent-child chain"""
        session = self._create_session()
        
        parent_def = self.endpoints.get(parent_name)
        child_def = self.endpoints.get(child_name)
        
        if not parent_def or not child_def:
            print(f"[{self.get_timestamp()}] ❌ Missing definitions: parent={parent_name}, child={child_name}")
            return 0, 0
        
        print(f"\n[{self.get_timestamp()}] 🔄 PARENT-CHAIN: {parent_name} → {child_name}")
        
        # STEP 1: Fetch all parents
        print(f"   [{self.get_timestamp()}] 📋 Fetching parents: {parent_name}")
        parents = []
        page_size = parent_def.get('Page_Size', 100)
        pagination_type = parent_def.get('Pagination_Type', 'None')
        response_format = parent_def.get('Response_Format', 'JSON')
        
        page_token = None
        offset = 0
        has_more = True
        next_page_path = None
        timeout = 30
        modified_date = self.get_date_filter(parent_def)
        parent_page_count = 0
        parent_total = 0
        
        while has_more:
            parent_page_count += 1
            
            if self.test_mode and parent_total >= self.test_limit:
                break
            
            if next_page_path:
                url = self.build_url_from_path(next_page_path)
                params = {}
                payload = None
            else:
                url = self.build_url(parent_def)
                if pagination_type == 'Offset':
                    params, payload = self.build_params_payload(
                        parent_def, None, page_size, None, modified_date, offset
                    )
                else:
                    params, payload = self.build_params_payload(
                        parent_def, page_token, page_size, None, modified_date
                    )
            
            resp = self.execute_request(session, url, params, payload, timeout)
            if not resp or resp.status_code != 200:
                if resp:
                    print(f"   [{self.get_timestamp()}] ❌ Parent fetch failed: {resp.status_code}")
                break
            
            if response_format == 'NDJSON':
                records = self.parse_ndjson_response(resp.text)
                records = self.extract_records(records, parent_def)
            else:
                data = resp.json()
                records = self.extract_records(data, parent_def)
            
            if records:
                if self.test_mode and parent_total + len(records) > self.test_limit:
                    remaining = self.test_limit - parent_total
                    if remaining > 0:
                        records = records[:remaining]
                        parent_total += len(records)
                        parents.extend(records)
                    break
                
                parent_total += len(records)
                parents.extend(records)
                print(f"   [{self.get_timestamp()}] 📦 Parent page {parent_page_count}: {len(records)} records (total: {parent_total})")
                
                if response_format == 'NDJSON':
                    has_more = False
                elif pagination_type == 'Offset':
                    offset += len(records)
                    if offset >= data.get('total', 0):
                        has_more = False
                elif pagination_type in ['URL_Token', 'Body_Token']:
                    next_token = self.get_next_token(data, parent_def)
                    if next_token:
                        if isinstance(next_token, str) and next_token.startswith('/'):
                            next_page_path = next_token
                            page_token = None
                        else:
                            page_token = next_token
                            next_page_path = None
                    else:
                        has_more = False
                else:
                    has_more = False
            else:
                has_more = False
        
        if not parents:
            print(f"   [{self.get_timestamp()}] ⚠️ No parents found for {parent_name}")
            session.close()
            return 0, 0
        
        print(f"   [{self.get_timestamp()}] 👥 Found {len(parents)} parents")
        
        # STEP 2: Fetch children for each parent
        successful = 0
        failed = 0
        parent_id_key = child_def.get('Parent_ID_Key', 'id')
        child_processed = 0
        total_children = 0
        
        # Debug first parent
        if parents:
            print(f"   [{self.get_timestamp()}] 🔍 First parent keys: {list(parents[0].keys())}")
            print(f"   [{self.get_timestamp()}] 🔍 Parent_ID_Key config: {parent_id_key}")
            test_id = self._extract_parent_id(parents[0], parent_id_key)
            print(f"   [{self.get_timestamp()}] 🔍 Extracted test ID: {test_id}")
        
        session.close()  # this was only ever used for fetching the parent list above -
                         # children are fetched using per-thread persistent sessions
        
        if self.test_mode:
            # Small runs: keep this strictly sequential and simple to reason about.
            for idx, parent in enumerate(parents, 1):
                if self.test_mode and total_children >= self.test_limit:
                    print(f"   [{self.get_timestamp()}] 🧪 TEST MODE: Reached child limit of {self.test_limit}")
                    break
                
                parent_id = self._extract_parent_id(parent, parent_id_key)
                if not parent_id:
                    continue
                
                records, page_count = self._fetch_children_for_parent(
                    parent_id, child_def, timeout,
                    remaining_limit=(self.test_limit - total_children)
                )
                
                if idx <= 2:
                    print(f"   [{self.get_timestamp()}] 👤 Parent {idx}/{len(parents)} (ID: {parent_id})")
                    print(f"      📦 Found {len(records)} children ({page_count} pages)")
                
                if records:
                    inserted = self.store_batch_records(records, child_name, str(parent_id))
                    successful += inserted
                    failed += len(records) - inserted
                    total_children += len(records)
                    child_processed += 1
                
                if idx % 20 == 0:
                    print(f"   [{self.get_timestamp()}] 📊 Progress: {idx}/{len(parents)} parents, {successful} children stored")
        else:
            # Production runs: these are independent per-parent HTTP calls, so
            # fan them out across a small thread pool instead of firing them
            # one at a time with a sleep() in between. store_batch_records is
            # only ever called back on the main thread, so file writes stay
            # single-threaded even though the fetching is concurrent.
            print(f"   [{self.get_timestamp()}] ⚡ Fetching children for {len(parents)} parents with {self.child_fetch_workers} workers")
            
            work_items = []
            for idx, parent in enumerate(parents, 1):
                parent_id = self._extract_parent_id(parent, parent_id_key)
                if parent_id:
                    work_items.append((idx, parent_id))
            
            with ThreadPoolExecutor(max_workers=self.child_fetch_workers) as executor:
                future_to_item = {
                    executor.submit(self._fetch_children_for_parent, parent_id, child_def, timeout): (idx, parent_id)
                    for idx, parent_id in work_items
                }
                
                for future in as_completed(future_to_item):
                    idx, parent_id = future_to_item[future]
                    try:
                        records, page_count = future.result(timeout=self.child_fetch_timeout_seconds)
                    except FutureTimeoutError:
                        print(f"      [{self.get_timestamp()}] 🛑 Timed out fetching parent {parent_id} "
                              f"after {self.child_fetch_timeout_seconds}s - skipping, moving on")
                        continue
                    except Exception as e:
                        print(f"      [{self.get_timestamp()}] ❌ Exception fetching parent {parent_id}: {e}")
                        continue
                    
                    if records:
                        inserted = self.store_batch_records(records, child_name, str(parent_id))
                        successful += inserted
                        failed += len(records) - inserted
                        total_children += len(records)
                        child_processed += 1
                    
                    if child_processed % 20 == 0:
                        print(f"   [{self.get_timestamp()}] 📊 Progress: {child_processed}/{len(work_items)} parents, {successful} children stored")
        
        print(f"   [{self.get_timestamp()}] ✅ Chain complete: {successful} children from {child_processed}/{len(parents)} parents")
        return successful, failed
    
    def _fetch_children_for_parent(self, parent_id: str, child_def: Dict, timeout: int,
                                    remaining_limit: Optional[int] = None) -> Tuple[List[Dict], int]:
        """
        Fetch (and fully paginate through) all child records for a single parent.
        Uses this thread's persistent session (created lazily, reused across
        every parent this thread ever processes) rather than opening a fresh
        one per call - safe to call concurrently from a thread pool since each
        thread gets its own session.
        """
        session = self._get_thread_session()
        
        if self.verbose_child_fetch_logging:
            print(f"      [{self.get_timestamp()}] 🔹 Starting parent {parent_id}")
        
        endpoint = child_def['Endpoint']
        param_match = re.search(r'\{\{(\w+)\}\}', endpoint)
        
        if param_match:
            url = self.build_url(child_def, {param_match.group(1): str(parent_id)})
        else:
            url = self.build_url(child_def)
        
        child_response_format = child_def.get('Response_Format', 'JSON')
        child_pagination_type = child_def.get('Pagination_Type', 'None')
        child_page_size = child_def.get('Page_Size', 0)
        
        child_page_token = None
        child_offset = 0
        child_has_more = True
        child_accumulated: List[Dict] = []
        child_page_count = 0
        child_total = 0
        
        while child_has_more:
            if remaining_limit is not None and child_total >= remaining_limit:
                break
            
            child_page_count += 1
            
            if child_pagination_type == 'Offset':
                params, payload = self.build_params_payload(
                    child_def, None, child_page_size, str(parent_id), None, child_offset
                )
            elif child_pagination_type in ['URL_Token', 'Body_Token']:
                params, payload = self.build_params_payload(
                    child_def, child_page_token, child_page_size, str(parent_id), None
                )
            else:
                params, payload = self.build_params_payload(
                    child_def, None, None, str(parent_id), None
                )
                child_has_more = False
            
            try:
                if self.verbose_child_fetch_logging:
                    print(f"      [{self.get_timestamp()}] 🔸 Requesting parent {parent_id}, page {child_page_count}")
                
                resp = self.execute_request(session, url, params, payload, timeout)
                
                if not resp or resp.status_code != 200:
                    break
                
                if child_response_format == 'NDJSON':
                    records = self.parse_ndjson_response(resp.text)
                    records = self.extract_records(records, child_def)
                else:
                    data = resp.json()
                    records = self.extract_records(data, child_def)
                
                if records:
                    if remaining_limit is not None:
                        remaining = remaining_limit - child_total
                        if remaining <= 0:
                            break
                        if len(records) > remaining:
                            records = records[:remaining]
                            child_has_more = False
                    
                    child_total += len(records)
                    child_accumulated.extend(records)
                    
                    if child_pagination_type == 'Offset':
                        child_offset += len(records)
                        if len(records) < child_page_size:
                            child_has_more = False
                    elif child_pagination_type in ['URL_Token', 'Body_Token']:
                        next_token = self.get_next_token(data, child_def)
                        if next_token:
                            child_page_token = next_token
                        else:
                            child_has_more = False
                    else:
                        child_has_more = False
                else:
                    child_has_more = False
                    
            except Exception:
                break
        
        if self.verbose_child_fetch_logging:
            print(f"      [{self.get_timestamp()}] ✔️ Finished parent {parent_id}: "
                  f"{len(child_accumulated)} record(s), {child_page_count} page(s)")
        
        return child_accumulated, child_page_count
    
    def run(self):
        start_time = time.time()
        
        print("=" * 80)
        print(f"⚔️  SAFETYCULTURE INGESTOR (SEQUENTIAL - 3-COLUMN CSV) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Data Path: {self.local_data_path}")
        print(f"📋 Columns: ExactJSON, ParentID, IngestedAt")
        if self.test_mode:
            print(f"🧪 TEST MODE ENABLED - Limit: {self.test_limit} records per endpoint")
        print("=" * 80)
        
        # Separate standalone and parent-child missions
        standalone_missions = []
        chain_missions = []
        
        for mission in self.missions:
            if not mission.get('Enabled', True):
                continue
            
            endpoint_name = mission['Endpoint']
            endpoint_def = self.endpoints.get(endpoint_name)
            
            if not endpoint_def:
                continue
            
            if endpoint_def.get('Requires_Parent'):
                chain_missions.append(mission)
            else:
                standalone_missions.append(mission)
        
        total_successful = 0
        total_failed = 0
        
        # Standalone endpoints and parent-child chains hit different API
        # endpoints entirely, so there's no reason to process them one at a
        # time - run up to `chain_concurrency` of them at once. The shared
        # rate limiter (not this number) is what actually protects the API,
        # so this is safe to raise independently of Requests_Per_Second.
        print(f"\n[{self.get_timestamp()}] 📋 Processing {len(standalone_missions)} standalone endpoints "
              f"(up to {self.chain_concurrency} at a time)")
        print("-" * 40)
        
        if standalone_missions:
            with ThreadPoolExecutor(max_workers=min(self.chain_concurrency, len(standalone_missions))) as executor:
                futures = {
                    executor.submit(self._process_single_endpoint, m['Endpoint'], self.endpoints[m['Endpoint']]): m
                    for m in standalone_missions
                }
                for future in as_completed(futures):
                    mission = futures[future]
                    try:
                        successful, failed = future.result(timeout=self.mission_timeout_seconds)
                    except FutureTimeoutError:
                        print(f"[{self.get_timestamp()}] 🛑 {mission['Endpoint']} timed out after "
                              f"{self.mission_timeout_seconds}s - skipping, moving on")
                        continue
                    except Exception as e:
                        print(f"[{self.get_timestamp()}] ❌ {mission['Endpoint']} failed: {e}")
                        continue
                    total_successful += successful
                    total_failed += failed
        
        # Process parent-child chains, also concurrently across chains
        if chain_missions:
            print(f"\n[{self.get_timestamp()}] 🔗 Processing {len(chain_missions)} parent-child chains "
                  f"(up to {self.chain_concurrency} at a time)")
            print("-" * 40)
            
            with ThreadPoolExecutor(max_workers=min(self.chain_concurrency, len(chain_missions))) as executor:
                futures = {}
                for mission in chain_missions:
                    endpoint_name = mission['Endpoint']
                    endpoint_def = self.endpoints[endpoint_name]
                    parent_name = endpoint_def.get('Parent_Endpoint')
                    
                    if not parent_name or parent_name not in self.endpoints:
                        print(f"[{self.get_timestamp()}] ⚠️ Skipping {endpoint_name}: parent {parent_name} not found")
                        continue
                    
                    future = executor.submit(self._process_parent_child_chain, parent_name, endpoint_name)
                    futures[future] = endpoint_name
                
                for future in as_completed(futures):
                    endpoint_name = futures[future]
                    try:
                        successful, failed = future.result(timeout=self.mission_timeout_seconds)
                    except FutureTimeoutError:
                        print(f"[{self.get_timestamp()}] 🛑 {endpoint_name} chain timed out after "
                              f"{self.mission_timeout_seconds}s - skipping, moving on")
                        continue
                    except Exception as e:
                        print(f"[{self.get_timestamp()}] ❌ {endpoint_name} chain failed: {e}")
                        continue
                    total_successful += successful
                    total_failed += failed
        
        total_minutes = (time.time() - start_time) / 60
        
        print("\n" + "=" * 80)
        print(f"🏁 ALL MISSIONS COMPLETE")
        print("=" * 80)
        print(f"📊 Total Records Inserted: {total_successful}")
        if total_failed > 0:
            print(f"   ❌ Failed: {total_failed}")
        if self.test_mode:
            print(f"🧪 TEST MODE: Limited to {self.test_limit} records per endpoint")
        print(f"⏱️  Total Time: {total_minutes:.2f} minutes")
        print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

# ============================================================================
# LOCAL DATA SUMMARY
# ============================================================================

def local_data_summary():
    """Show what data has been collected in the data lake"""
    client = azure_io.get_client()
    
    tables = [
        "actions_list", "action_details", "inspection_details", "inspections_list",
        "groups_list", "group_users", "investigation_details", "investigations_list",
        "inspection_answers", "issue_details", "issues_list", "issues_answers", "schedule_items",
        "site_members", "sites_list", "templates_list", "templates_compact_list",
        "user_groups", "users_list"
    ]
    
    print("\n" + "=" * 80)
    print("--- DATA LAKE SUMMARY (3-Column CSV) ---")
    print("Columns: ExactJSON, ParentID, IngestedAt")
    print("=" * 80)
    
    total_records = 0
    
    for tbl in tables:
        file_path = f"TNS/{tbl}.csv"
        
        try:
            if client.exists(file_path):
                df = client.read_csv(file_path)
                count = len(df)
                print(f"Table '{tbl}':".ljust(30) + f"{count} records")
                total_records += count
            else:
                print(f"Table '{tbl}':".ljust(30) + "[NOT FOUND]")
        except Exception as e:
            print(f"Table '{tbl}':".ljust(30) + f"[ERROR: {str(e)}]")
    
    print("=" * 80)
    print(f"📊 TOTAL RECORDS: {total_records}")
    print("=" * 80)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    ingestor = LocalSafetyCultureIngestor(
        manifest=MANIFEST,
        test_mode=False,   # False = full production run (threaded, rate-limited).
                            # True  = small, strictly sequential run capped at
                            #         test_limit records - for dry-runs only,
                            #         NOT what you want for a real pull.
        test_limit=1
    )
    ingestor.run()
    
    # Show summary of collected data
    local_data_summary()