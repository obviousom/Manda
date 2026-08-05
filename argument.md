# Tool Arguments Reference — AWS & Azure Waste Management + Cost Optimization

## Common Argument Patterns

Most per-service tools share the same base argument set:

| Argument | Type | Default | Description |
|---|---|---|---|
| `region` | `str` | required / `""` | Cloud region (e.g. `"ap-south-1"`, `"centralindia"`) |
| `limit` | `int` | `5` | Pagination: 1-30, or `-1` for all |
| `tag_key` | `str` | `""` | Include-filter: tag key (e.g. `"Environment"`) |
| `tag_value` | `str` | `""` | Include-filter: tag value (case-insensitive) |
| `exclude_tag_key` | `str` | `""` | Exclude-filter: tag key |
| `exclude_tag_value` | `str` | `""` | Exclude-filter: tag value (case-insensitive) |

`runtime: ToolRuntime` is always injected by the framework -- never a user-facing arg.

---

## AWS Waste Management

**File:** `chatbot/finops/waste_management/aws_tools.py`
**Extended:** `aws_tools_extended.py`, `aws_security_tools.py`

### Aggregate / Dashboard

| Tool | Args |
|---|---|
| `execute_cli_command` | `command: str`, `to_csv: bool = False` |
| `search_unattached_resources` | `region_or_location: str`, `limit: int = 5`, `cloud_provider: Literal["AWS","AZURE"] = "AWS"` |
| `get_ri_sp_coverage_gaps` | _(no user args)_ |
| `get_ec2_waste_dashboard` | `region: str` |

### EBS / Storage

| Tool | Args (beyond common) |
|---|---|
| `search_unattached_ebs_volumes` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `search_old_ebs_snapshots` | same |
| `search_unused_s3_buckets` | `region: str = None`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `search_stale_ecr_images` | `region: str` |
| `search_idle_efs_file_systems` | `region: str` |

### RDS / Databases

| Tool | Args |
|---|---|
| `search_rds_snapshots` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `search_inactive_rds_databases` | `region: str`, `days: int = 10`, `limit: int = 5`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |

### Compute (EC2)

| Tool | Args |
|---|---|
| `get_stopped_ec2_instances` | `region: str`, `limit: int = 5`, `min_stopped_days: int = 7`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `get_idle_ec2_instances` | `region: str`, `limit: int = 5`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |

### Networking

| Tool | Args |
|---|---|
| `search_unassociated_elastic_ips` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `search_unused_load_balancers_tool` | same |
| `search_unused_security_groups` | `region: str`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` _(no limit arg)_ |
| `search_unused_vpcs` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `search_idle_nat_gateways` | `region: str` |

### Images / AMIs

| Tool | Args |
|---|---|
| `search_unused_amis` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |

### Security / Keys / Secrets

| Tool | Args |
|---|---|
| `search_unused_kms_keys` | `region: str`, `unused_days_threshold: int = 90`, `tag_key: str = ""`, `tag_value: str = ""` |
| `search_unused_secrets` | `region: str`, `unused_days_threshold: int = 90`, `tag_key: str = ""`, `tag_value: str = ""` |

### Serverless / Observability

| Tool | Args |
|---|---|
| `search_unused_lambda_functions` | `region: str` |
| `search_cloudwatch_logs_no_retention` | `region: str` |

### Delete / Query

| Tool | Args |
|---|---|
| `delete_resource_post_approval` | `resource_id: str`, `resource_type: str`, `region: str` |
| `query_table` | `table_id: str`, `select: list\|None = None`, `where: dict\|None = None`, `group_by: list\|None = None`, `aggregate: dict\|None = None`, `order_by: str = ""`, `order_dir: str = "desc"`, `limit: int = 10` |

---

## AWS Cost Optimization

**File:** `chatbot/finops/cost_optimization/aws/tools/aws_tools.py`

| Tool | Args |
|---|---|
| `get_savings_plan_recommendations` | _(no user args -- uses region from context)_ |
| `analyze_intel_to_amd_processor_savings` | `days: int = 30`, `cpu_on_threshold: float = 1.0` |
| `send_cost_optimization_report_multi_format` | `formats: str = "csv,excel,pdf"`, `subject: str = "Cloud Cost Optimization Report"`, `region: str = ""` |

---

## Azure Waste Management

**File:** `chatbot/finops/waste_management/azure_tools.py`
**Extended:** `azure_tools_extended.py`, `azure_keyvault_tools.py`

### Aggregate / Dashboard

| Tool | Args |
|---|---|
| `execute_cli_command` (Azure) | `command: str`, `to_csv: bool = False` |
| `azure_search_waste_resources` | `region: str = ""`, `limit: int = 5`, `tag_key: str = ""`, `tag_value: str = ""` _(no exclude args)_ |
| `azure_get_cost_analysis` | `days: int = 30` |
| `azure_get_vm_waste_dashboard` | `region: str = ""` |

### Disk / Storage

| Tool | Args |
|---|---|
| `azure_search_unattached_managed_disks` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `azure_search_old_snapshots` | same |
| `azure_search_unused_storage_accounts` | `region: str = ""`, `limit: int = 5` _(no tag args)_ |

### Databases

| Tool | Args |
|---|---|
| `azure_find_underutilized_sql_databases` | `days: int = 10`, `dtu_threshold: float = 5.0`, `limit: int = 5` |

### Compute (VMs)

| Tool | Args |
|---|---|
| `get_idle_azure_vms` | `region: str = ""`, `days: int = 7`, `cpu_threshold: float = 5.0`, `limit: int = 5`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `get_stopped_azure_vms` | `region: str = ""`, `limit: int = 5`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |

### Networking

| Tool | Args |
|---|---|
| `azure_search_unassociated_public_ips` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |
| `azure_search_unused_load_balancers` | same |
| `azure_search_unused_nsgs` | same |
| `azure_search_unused_vnets` | same |

### Images

| Tool | Args |
|---|---|
| `azure_search_unused_images` | `region`, `limit`, `tag_key`, `tag_value`, `exclude_tag_key`, `exclude_tag_value` |

### Security / Keys

| Tool | Args |
|---|---|
| `azure_search_unused_key_vaults` | `region: str = ""`, `limit: int = 5` |

### Delete / Query

| Tool | Args |
|---|---|
| `azure_delete_resource` | `resource_id: str`, `resource_type: str` |
| `query_table` | _(same as AWS version above)_ |

---

## Azure Cost Optimization

**File:** `chatbot/finops/cost_optimization/azure/tools/azure_tools.py`

### VM Rightsizing

| Tool | Args |
|---|---|
| `find_underutilized_azure_vms` | `start_time: str`, `end_time: str`, `period: int = 300` |
| `calculate_finops_recommendations_azure` | `resources_data: List[Dict[str,Any]]`, `location: str = "centralindia"` |
| `get_azure_savings_recommendations` | _(no user args)_ |
| `analyze_azure_intel_to_amd_processor_savings` | `days: int = 30`, `cpu_on_threshold: float = 1.0` |

### CLI

| Tool | Args |
|---|---|
| `execute_azure_cli_command` | `cli_command: str` |

### Serverless / Functions

| Tool | Args |
|---|---|
| `find_azure_functions_always_ready` | `region: str = ""`, `limit: int = 10` |

### SQL / Database

| Tool | Args |
|---|---|
| `get_azure_sql_rightsizing_recommendations` | `region: str = ""`, `days: int = 14` |

### Storage

| Tool | Args |
|---|---|
| `get_azure_storage_archive_recommendations` | `region: str = ""` |
| `find_azure_blob_archive_candidates` | `start_time: str = ""`, `end_time: str = ""` |

### Reports

| Tool | Args |
|---|---|
| `send_cost_optimization_report_multi_format` | `formats: str = "csv,excel,pdf"`, `subject: str = "Cloud Cost Optimization Report"`, `region: str = ""` |

---

## Argument Type Summary (for Policy Form Design)

| Argument | Type | Used In | Purpose |
|---|---|---|---|
| `region` / `region_or_location` | `str` | All tools | Filter by cloud region |
| `limit` | `int` (1-30 or -1) | Most tools | Pagination control |
| `days` | `int` | RDS, SQL, VM idle, AMD analysis | Lookback window for metrics |
| `min_stopped_days` | `int` | `get_stopped_ec2_instances` | Min days stopped before flagging |
| `cpu_threshold` | `float` (%) | `get_idle_azure_vms` | CPU % below which VM is idle |
| `cpu_on_threshold` | `float` (%) | AMD analysis tools | CPU % above which instance counted as ON |
| `dtu_threshold` | `float` (%) | Azure SQL | DTU % threshold for inactivity |
| `unused_days_threshold` | `int` | KMS keys, Secrets | Days unused before flagging |
| `tag_key` | `str` | Most tools | Inclusive tag filter key |
| `tag_value` | `str` | Most tools | Inclusive tag filter value |
| `exclude_tag_key` | `str` | Most AWS + Azure tools | Exclusive tag filter key |
| `exclude_tag_value` | `str` | Most AWS + Azure tools | Exclusive tag filter value |
| `cloud_provider` | `"AWS"\|"AZURE"` | `search_unattached_resources` | Provider selector |
| `to_csv` | `bool` | CLI execute tools | Auto-upload result as CSV to S3 |
| `resource_id` | `str` | Delete tools | Full resource ID to delete |
| `resource_type` | `str` | Delete tools | Resource type (e.g. `"disk"`, `"snapshot"`) |
| `formats` | `str` | Report email tools | Comma-separated: `"csv,excel,pdf"` |
| `subject` | `str` | Report email tools | Email subject line |
| `start_time` | `str` | Azure VM analysis, Blob | ISO datetime for lookback start |
| `end_time` | `str` | Azure VM analysis, Blob | ISO datetime for lookback end |
| `period` | `int` | `find_underutilized_azure_vms` | Metric aggregation period (seconds) |
| `location` | `str` | Azure recommendations | Azure region for VM size lookup |
| `resources_data` | `List[Dict]` | `calculate_finops_recommendations_azure` | Pre-fetched resource list |
| `table_id` | `str` | `query_table` | Reference to stored result table |
| `select` | `list\|None` | `query_table` | Columns to return |
| `where` | `dict\|None` | `query_table` | Filter conditions |
| `group_by` | `list\|None` | `query_table` | Group-by columns |
| `aggregate` | `dict\|None` | `query_table` | Aggregation functions |
| `order_by` | `str` | `query_table` | Sort column name |
| `order_dir` | `"asc"\|"desc"` | `query_table` | Sort direction |
