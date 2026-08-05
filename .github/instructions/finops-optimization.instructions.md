---
description: Guidelines for FinOps optimization dashboard development, including AWS EC2 rightsizing recommendations, Reserved Instance logic, uptime calculations, and UI table layouts.
applyTo: "dashboards/finops/optimization/**"
---

# FinOps Optimization Dashboard - Development Instructions

**Last Updated:** April 16, 2026  
**Scope:** AWS EC2/EBS Rightsizing, Reserved Instance Recommendations, Cost Optimization  

---

## 1. Recommendation Verdict Selection & Sorting

### Core Pattern
**ALWAYS prioritize CONFIDENCE LEVEL over raw savings amount when selecting the primary recommendation verdict.**

```python
# ✅ CORRECT - Confidence first, savings as tiebreaker
confidence_order = {"high": 0, "medium": 1, "low": 2}
sorted_recommendations = sorted(
    recommendations,
    key=lambda r: (confidence_order.get(r["confidence"], 99), -r["monthly_savings_usd"])
)
primary_verdict = sorted_recommendations[0]
```

### Why
Previous behavior sorted by savings only, causing less-confident options (e.g., Graviton medium) to be selected over higher-confidence recommendations (e.g., Upsize high), leading to unreliable primary suggestions.

### Implementation Locations
- **aws_provider.py, lines ~723-728**: Main verdict selection loop in `get_ec2_recommendations()`
- Applies to: Upsize, Downsize, Graviton Migration, AMD Migration, CPU Downsize, Reserved Instance recommendations

### Confidence Levels Reference
- `high`: Strong indicator from p99 metrics, consistent patterns, >80% uptime
- `medium`: Mixed signals, moderate uptime, ~30-80% uptime
- `low`: Weak signals, inconsistent data, <30% uptime

---

## 2. Reserved Instance (RI) Recommendations

### Trigger Conditions
Generate RI recommendation verdicts when **BOTH** conditions are true:

```python
uptime_hours > 720  # Instance running > 30 days
AND
uptime_pct_of_existence > 80%  # Running ≥80% of its lifetime
```

### RI Options to Generate

| Option | Commitment | Savings | Confidence | Criteria |
|--------|-----------|---------|-----------|----------|
| Reserved Instance (1-Year) | 1-year commitment | ~35% savings on on-demand | `high` | uptime_hours > 720 |
| Reserved Instance (3-Year) | 3-year commitment | ~55% savings on on-demand | `medium` | uptime_hours > 720 |

### Implementation Pattern
```python
if uptime_hours > 720 and uptime_pct_of_existence > 80:
    # 1-year RI option
    monthly_savings_usd = current_monthly_cost * 0.35
    recommendations.append({
        "recommendation_type": "reserved_instance",
        "period": "1-year",
        "monthly_savings_usd": monthly_savings_usd,
        "confidence": "high",
        "reason": f"Instance has {uptime_hours} uptime hours. RI commitment recommended for stable workload."
    })
    
    # 3-year RI option
    monthly_savings_usd = current_monthly_cost * 0.55
    recommendations.append({
        "recommendation_type": "reserved_instance",
        "period": "3-year",
        "monthly_savings_usd": monthly_savings_usd,
        "confidence": "medium",
        "reason": f"Instance has {uptime_hours} uptime hours. 3-year RI provides maximum savings."
    })
```

### Frontend Display
- Icon: `Shield` (from lucide-react) representing commitment/protection
- Label: "Reserved Instance (1-Year)" or "Reserved Instance (3-Year)"
- Placement: In recommendations table row with other verdicts

---

## 3. Uptime Calculation - Instance-Age-Aware

### Problem This Solves
Previously, all instances used fixed 720-hour (30-day) analysis window as denominator, causing newly-created instances to show artificially low uptime percentages.

### Correct Implementation Pattern

```python
# Calculate effective analysis window based on instance age
def get_effective_window_hours(uptime_hours, analysis_window_hours):
    """
    Returns smarter window for uptime percentage calculation.
    If instance is younger than 80% of analysis window, use instance age as denominator.
    Otherwise use full analysis window (handles startup time edge cases).
    """
    if uptime_hours < analysis_window_hours * 0.8:
        # Instance is new, use its actual age as denominator
        return uptime_hours
    else:
        # Instance has lived long enough, use full analysis window
        return analysis_window_hours

# In results building
effective_window = get_effective_window_hours(uptime_hours, analysis_window_hours)
uptime_pct_of_analysis = round((uptime_hours / effective_window) * 100) if effective_window > 0 else 0
```

### Implementation Locations
- **aws_provider.py, lines ~507-515**: In main `get_ec2_recommendations()` function
- **aws_provider.py, lines ~839-844**: In results building, when calculating final uptime_pct_of_analysis

### Edge Cases to Handle
- Instance age: 1 day (should show ~100%, not 1/30th)
- Instance age: 15 days (should show appropriate percentage relative to 15 days, not 30)
- Instance age: 40+ days (use full 30-day analysis window normally)

---

## 4. Cost Visualization - Dual-Bar Approach

### Frontend Pattern

For cost comparisons, use conditional rendering based on recommendation type:

```typescript
if (monthly_savings_usd > 0) {
  // Savings/Downsize: Single green bar showing reduction
  <ProgressBar percentage={(suggested/current)*100} color="green" />
} else if (monthly_savings_usd < 0) {
  // Additional cost/Upsize: Dual bars (current at 100%, suggested above)
  <div className="flex gap-2">
    <CostBar label="Current" amount={current} color="gray" width="100%" />
    <CostBar label="Suggested" amount={suggested} color="blue" width={proportion} />
  </div>
} else {
  // No change: Show as equal
  <CostBar label="No Change" amount={current} color="neutral" />
}
```

### Why Dual Bars for Upsize
- Single bar confuses users when suggested > current (bar would exceed 100%)
- Dual bars clearly show: current cost + additional cost needed
- User can instantly see "This costs more but has benefits (confidence, capacity)"

### Implementation Location
- **codly-admin-portal/src/app/dashboard/finops-hub/optimization/page.tsx**
- Recommended section: Inside table row rendering logic, CostDisplay component

---

## 5. Recommendation Table Layout - Required Structure

### Frontend UI Pattern

**Replace card grid layouts with 6-column table:**

| Column | Content | Notes |
|--------|---------|-------|
| **Recommendation** | Icon + Type (Upsize, Downsize, Graviton, AMD, CPU Downsize, RI) | Icon mapping required |
| **Current** | Current monthly cost in $ | `CostDisplay` component |
| **Suggested** | Suggested monthly cost in $ | `CostDisplay` component |
| **Monthly Impact** | Savings amount with color (red for cost, green for savings) | Percentage badge |
| **Confidence** | High/Medium/Low badge with color coding | Color: green/yellow/red |
| **Reason** | Explanation text (max 1-2 lines) | Truncate with ellipsis if needed |

### Icon Mapping
```typescript
const recommendationIcons = {
  upsize: ArrowUpCircle,
  downsize: ArrowDownCircle,
  graviton_migration: Atom,
  amd_migration: Cpu,
  cpu_downsize: Zap,
  terminate: Trash2,
  reserved_instance: Shield  // NEW
};
```

### Implementation Location
- **codly-admin-portal/src/app/dashboard/finops-hub/optimization/page.tsx, lines ~582-690**
- Replace: Previous card grid rendering with `<table>` structure

### Why Table Over Cards
- Easier to compare costs side-by-side across 10+ recommendations
- More compact, density-efficient for dashboards
- Familiar format for financial data
- Sorts/filters work better with table DOM structure

---

## 6. EBS Snapshot Pricing - Region-Specific Rate Lookup

### Critical Pattern
**NEVER treat pricing config dicts as numbers. Always extract region-specific rate first.**

```python
# ❌ WRONG - Causes TypeError
monthly_cost = round(size_gb * EBS_SNAPSHOT_RATE_USD_PER_GB, 2)
# TypeError: unsupported operand type(s) for *: 'float' and 'dict'

# ✅ CORRECT - Extract rate first
snapshot_rate = EBS_SNAPSHOT_RATE_USD_PER_GB.get(region, 0.05)  # Default to $0.05/GB
monthly_cost = round(size_gb * snapshot_rate, 2)
```

### Configuration Reference
Located in `dashboards/finops/constants.py`:

```python
EBS_SNAPSHOT_RATE_USD_PER_GB = {
    "us-east-1": 0.05,
    "us-west-2": 0.05,
    "eu-west-1": 0.055,
    # ... other regions
}
```

### Implementation Locations
- **aws_provider.py, lines ~1042-1056**: In `get_idle_resources()` snapshot cost calculation
- **aws_provider.py, anywhere EBS costs calculated**: Use same pattern

### Why This Matters
- Snapshots are charged differently per region (different data center costs)
- Users in high-cost regions (e.g., eu-west-1) see inflated storage costs
- Incorrect calculations lead to misleading idle resource findings

---

## 7. Multi-Tenant & Multi-Cloud Considerations

### Credential Management Pattern
When calculating recommendations, ALWAYS use:

```python
cred_loader = create_cloud_cred_loader(
    account.cloud_provider,  # aws, azure, gcp
    user=request.user,
    account=account,
    customer=customer
)
cred_loader.load_db_credentials()
env_vars = cred_loader.get_env_values()

# Use env_vars for cloud SDK calls, never hardcode credentials
```

### Multi-Cloud Structure (If Adding Azure/GCP)
```
dashboards/finops/optimization/
├── providers/
│   ├── base/
│   │   └── optimization_manager.py  # Abstract base
│   ├── aws_provider.py              # AWS implementation
│   ├── azure_provider.py            # Future
│   └── gcp_provider.py              # Future
└── ...
```

### Database Query Pattern
```python
# ✅ CORRECT - Filtered by customer/account
recommendations = Recommendation.objects.filter(
    account=account,
    customer=customer
)

# ❌ WRONG - Cross-tenant data leak risk
recommendations = Recommendation.objects.all()
```

---

## 8. Error Handling Standards

### Cloud API Calls
ALWAYS wrap with try/except:

```python
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

try:
    response = ec2_client.describe_instances()
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'UnauthorizedOperation':
        logger.warning(f"EC2 permission denied: {e}")
        return {"error": "Insufficient permissions", "instances": []}
    else:
        logger.exception(f"EC2 API error: {e}")
        return {"error": "Failed to retrieve instances", "instances": []}
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    return {"error": "Internal error", "instances": []}
```

### Pricing Dictionary Lookups
```python
# ✅ CORRECT - Safe fallback
rate = PRICING_DICT.get(region, DEFAULT_RATE)

# ❌ WRONG - KeyError if region missing
rate = PRICING_DICT[region]
```

---

## 9. Common Mistakes to Avoid

| ❌ Don't | ✅ Do | Why |
|---------|------|-----|
| Sort by savings only | Sort by confidence, then savings | Confidence indicates reliability |
| Use 720 hours for all uptime % | Use effective_window_hours | New instances show accurate uptime |
| Treat pricing dicts as numbers | Extract region-specific rate | Prevents TypeError |
| Show RI for all instances | Only instances with uptime > 720h | RI not suitable for short-lived VMs |
| Single bar for upsize costs | Dual bars for upsize scenarios | Clearer visualization |
| Card grid for 20+ recommendations | Table layout | Better for comparison |
| Hardcode AWS regions | Accept from request context | Multi-region support |
| `.all()` without customer filter | `.filter(customer=customer, ...)` | Multi-tenant isolation |

---

## 10. Frontend Component Architecture

### CostDisplay Component
Used in recommendation table for both Current and Suggested columns:

```typescript
<CostDisplay 
  amount={recommendation.current_monthly_cost}
  currency="USD"
  savings={recommendation.monthly_savings_usd}
  confidence={recommendation.confidence}
/>
```

### Badge Component
For confidence level:

```typescript
<Badge 
  text={confidence}
  color={confidence === 'high' ? 'green' : confidence === 'medium' ? 'yellow' : 'red'}
  size="sm"
/>
```

### Icons
Always import from `lucide-react`:

```typescript
import { 
  ArrowUpCircle, 
  ArrowDownCircle, 
  Atom, 
  Cpu, 
  Zap, 
  Trash2,
  Shield  // For RI recommendations
} from 'lucide-react';
```

---

## 11. Performance Optimization Notes

### Database Queries
```python
# ✅ CORRECT - Avoid N+1 queries
instances = EC2Instance.objects.filter(
    customer=customer
).select_related('account', 'environment').prefetch_related('recommendations')

# ❌ WRONG - Creates query per instance
for instance in instances:
    print(instance.account.name)  # Extra DB query
```

### Caching Recommendations
- Cache EC2 instance list: 5 minutes
- Cache pricing configs: 1 hour
- Cache p99 metrics from CloudWatch: 15 minutes
- Don't cache: Real-time cost calculations, credential lookups

---

## 12. Testing & Validation Checklist

### New RI Recommendations
- [ ] Instance with uptime_hours > 720 shows both 1-year and 3-year RI options
- [ ] Instance with uptime_hours < 720 does NOT show RI options
- [ ] Confidence level is "high" for 1-year, "medium" for 3-year
- [ ] Savings calculations match expected percentages (35% and 55%)

### Uptime Calculation
- [ ] New instance (1 day old): Shows ~100% uptime, not 1/30
- [ ] Middle-age instance (15 days old): Shows percentage relative to 15 days
- [ ] Old instance (40+ days): Uses full 30-day analysis window
- [ ] Instance with 0 hours uptime: Shows 0%, not division error

### Cost Visualization
- [ ] Upsize recommendations: Show dual bars (current + additional cost)
- [ ] Downsize recommendations: Show single green bar with reduction
- [ ] No cross-tenant data visible in recommendations
- [ ] All costs in $ format, rounded to 2 decimals

### Snapshot Pricing
- [ ] No TypeError warnings in logs when running idle resource analysis
- [ ] Snapshot costs calculated correctly for different regions
- [ ] Fallback to $0.05/GB if region not in config

---

## 13. Related Documentation

- API Endpoints: `/docs/api/finops/optimization.md`
- Constants & Pricing: `dashboards/finops/constants.py`
- Backend Standards: `.github/instructions/backend-instruction.instructions.md`
- PR Review Guidelines: `/docs/PR_REVIEW_GUIDELINES.md`
