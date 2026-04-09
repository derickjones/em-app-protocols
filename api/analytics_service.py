"""
Analytics Service — Firestore event logging and aggregation for owner dashboard.
Tracks: queries, sessions (daily active users), protocol clicks.
Reads: aggregated trends by day/week/month, per-user breakdowns, feedback.

NOTE: Read queries use single-field filters only (date range) and filter type in
Python to avoid needing Firestore composite indexes.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

db = firestore.Client(project="clinical-assistant-457902")

# ============================================================================
# WRITE FUNCTIONS — called from endpoints
# ============================================================================

def log_query_event(user_id: str, user_email: str, query: str, sources: list, response_time_ms: int):
    """Log a search query event."""
    now = datetime.utcnow()
    db.collection("analytics_events").add({
        "type": "query",
        "userId": user_id,
        "userEmail": user_email,
        "query": query[:200],  # truncate for storage
        "sources": sources,
        "responseTimeMs": response_time_ms,
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def log_session_event(user_id: str, user_email: str):
    """
    Log a daily session (unique user visit).
    Uses userId_date as doc ID for natural deduplication.
    """
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    doc_id = f"{user_id}_{date_str}"
    db.collection("analytics_sessions").document(doc_id).set({
        "userId": user_id,
        "userEmail": user_email,
        "date": date_str,
        "timestamp": firestore.SERVER_TIMESTAMP,
    }, merge=True)  # merge=True so repeated calls are idempotent


def log_protocol_click(user_id: str, user_email: str, protocol_id: str, protocol_title: str, enterprise_id: str = ""):
    """Log a click on a local/highlighted protocol."""
    now = datetime.utcnow()
    db.collection("analytics_events").add({
        "type": "protocol_click",
        "userId": user_id,
        "userEmail": user_email,
        "protocolId": protocol_id,
        "protocolTitle": protocol_title,
        "enterpriseId": enterprise_id,
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


# ============================================================================
# READ FUNCTIONS — called from owner-only analytics endpoints
# ============================================================================

def _date_range(range_str: str) -> tuple[str, str]:
    """Convert range string to (start_date, end_date) inclusive."""
    now = datetime.utcnow()
    end = now.strftime("%Y-%m-%d")
    if range_str == "today":
        return end, end
    elif range_str == "7d":
        start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    elif range_str == "30d":
        start = (now - timedelta(days=29)).strftime("%Y-%m-%d")
    elif range_str == "90d":
        start = (now - timedelta(days=89)).strftime("%Y-%m-%d")
    elif range_str == "1y":
        start = (now - timedelta(days=364)).strftime("%Y-%m-%d")
    elif range_str == "all":
        start = "2020-01-01"
    else:
        start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    return start, end


def _bucket_key(date_str: str, granularity: str) -> str:
    """Convert a date string to a bucket key based on granularity."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if granularity == "day":
        return date_str
    elif granularity == "week":
        # ISO week start (Monday)
        start = dt - timedelta(days=dt.weekday())
        return start.strftime("%Y-%m-%d")
    elif granularity == "month":
        return dt.strftime("%Y-%m")
    return date_str


def _auto_granularity(range_str: str) -> str:
    """Pick granularity based on range."""
    if range_str in ("today", "7d", "30d"):
        return "day"
    elif range_str == "90d":
        return "week"
    else:
        return "month"


# ============================================================================
# HELPER: fetch analytics_events for a date range, filter type in Python
# ============================================================================

def _fetch_events(start: str, end: str, event_type: str = None) -> list:
    """Fetch analytics_events within date range, optionally filter by type in Python."""
    docs = db.collection("analytics_events") \
        .where(filter=FieldFilter("date", ">=", start)) \
        .where(filter=FieldFilter("date", "<=", end)) \
        .stream()
    results = []
    for doc in docs:
        d = doc.to_dict()
        if event_type and d.get("type") != event_type:
            continue
        results.append(d)
    return results


def _fetch_sessions(start: str, end: str) -> list:
    """Fetch analytics_sessions within date range."""
    docs = db.collection("analytics_sessions") \
        .where(filter=FieldFilter("date", ">=", start)) \
        .where(filter=FieldFilter("date", "<=", end)) \
        .stream()
    return [doc.to_dict() for doc in docs]


def _fetch_feedback(start: str, end: str) -> list:
    """Fetch feedback within date range."""
    docs = db.collection("feedback") \
        .where(filter=FieldFilter("date", ">=", start)) \
        .where(filter=FieldFilter("date", "<=", end)) \
        .stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def get_summary(range_str: str = "7d") -> dict:
    """Get top-line summary stats for a range."""
    start, end = _date_range(range_str)

    # Count queries
    query_events = _fetch_events(start, end, "query")
    query_count = len(query_events)
    user_queries = defaultdict(int)
    for d in query_events:
        user_queries[d.get("userId", "unknown")] += 1

    # Count unique sessions
    session_docs = _fetch_sessions(start, end)
    unique_users = set(d.get("userId", "unknown") for d in session_docs)
    user_count = len(unique_users)
    avg_per_user = round(query_count / user_count, 1) if user_count > 0 else 0

    # Feedback stats
    feedback_docs = _fetch_feedback(start, end)
    up_count = sum(1 for d in feedback_docs if d.get("rating") == "up")
    down_count = sum(1 for d in feedback_docs if d.get("rating") == "down")
    total_feedback = up_count + down_count
    feedback_score = round(up_count / total_feedback * 100) if total_feedback > 0 else 0

    # Previous period comparison
    days_in_range = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days + 1
    prev_end_dt = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=1)
    prev_start_dt = prev_end_dt - timedelta(days=days_in_range - 1)
    prev_start = prev_start_dt.strftime("%Y-%m-%d")
    prev_end = prev_end_dt.strftime("%Y-%m-%d")

    prev_queries = len(_fetch_events(prev_start, prev_end, "query"))
    prev_sessions = _fetch_sessions(prev_start, prev_end)
    prev_user_count = len(set(d.get("userId", "") for d in prev_sessions))

    def pct_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round((current - previous) / previous * 100)

    return {
        "users": user_count,
        "usersChange": pct_change(user_count, prev_user_count),
        "queries": query_count,
        "queriesChange": pct_change(query_count, prev_queries),
        "avgPerUser": avg_per_user,
        "feedbackUp": up_count,
        "feedbackDown": down_count,
        "feedbackScore": feedback_score,
        "totalFeedback": total_feedback,
        "range": range_str,
    }


def get_trend(range_str: str = "7d") -> dict:
    """Get trend data bucketed by auto-granularity."""
    start, end = _date_range(range_str)
    granularity = _auto_granularity(range_str)

    query_events = _fetch_events(start, end, "query")
    session_docs = _fetch_sessions(start, end)
    feedback_docs = _fetch_feedback(start, end)

    # Query events bucketed
    query_buckets = defaultdict(int)
    for d in query_events:
        bucket = _bucket_key(d.get("date", start), granularity)
        query_buckets[bucket] += 1

    # Session events bucketed
    user_buckets = defaultdict(set)
    for d in session_docs:
        bucket = _bucket_key(d.get("date", start), granularity)
        user_buckets[bucket].add(d.get("userId", ""))

    # Feedback bucketed
    feedback_up_buckets = defaultdict(int)
    feedback_down_buckets = defaultdict(int)
    for d in feedback_docs:
        bucket = _bucket_key(d.get("date", start), granularity)
        if d.get("rating") == "up":
            feedback_up_buckets[bucket] += 1
        elif d.get("rating") == "down":
            feedback_down_buckets[bucket] += 1

    # Merge into sorted list
    all_buckets = sorted(set(list(query_buckets.keys()) + list(user_buckets.keys()) + list(feedback_up_buckets.keys()) + list(feedback_down_buckets.keys())))
    
    trend = []
    for bucket in all_buckets:
        trend.append({
            "period": bucket,
            "users": len(user_buckets.get(bucket, set())),
            "queries": query_buckets.get(bucket, 0),
            "feedbackUp": feedback_up_buckets.get(bucket, 0),
            "feedbackDown": feedback_down_buckets.get(bucket, 0),
        })

    return {
        "granularity": granularity,
        "range": range_str,
        "data": trend,
    }


def get_users_breakdown(range_str: str = "7d") -> list:
    """Per-user stats for the range."""
    start, end = _date_range(range_str)

    query_events = _fetch_events(start, end, "query")
    feedback_docs = _fetch_feedback(start, end)

    # Queries per user
    user_stats = defaultdict(lambda: {"email": "", "queries": 0, "lastActive": "", "feedbackUp": 0, "feedbackDown": 0})
    
    for d in query_events:
        uid = d.get("userId", "unknown")
        user_stats[uid]["email"] = d.get("userEmail", "")
        user_stats[uid]["queries"] += 1
        date = d.get("date", "")
        if date > user_stats[uid]["lastActive"]:
            user_stats[uid]["lastActive"] = date

    # Feedback per user
    for d in feedback_docs:
        email = d.get("user_email", "anonymous")
        for uid, stats in user_stats.items():
            if stats["email"] == email:
                if d.get("rating") == "up":
                    stats["feedbackUp"] += 1
                elif d.get("rating") == "down":
                    stats["feedbackDown"] += 1
                break

    result = []
    for uid, stats in user_stats.items():
        result.append({
            "userId": uid,
            "email": stats["email"],
            "queries": stats["queries"],
            "lastActive": stats["lastActive"],
            "feedbackUp": stats["feedbackUp"],
            "feedbackDown": stats["feedbackDown"],
        })
    
    result.sort(key=lambda x: x["queries"], reverse=True)
    return result


def get_feedback_list(range_str: str = "7d", rating_filter: str = "all", page: int = 1, page_size: int = 20) -> dict:
    """Paginated feedback list."""
    start, end = _date_range(range_str)

    feedback_docs = _fetch_feedback(start, end)
    # Sort by date descending
    feedback_docs.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    if rating_filter != "all":
        feedback_docs = [d for d in feedback_docs if d.get("rating") == rating_filter]

    total = len(feedback_docs)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_docs = feedback_docs[start_idx:end_idx]

    return {
        "feedback": page_docs,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size,
    }


def get_protocol_clicks(range_str: str = "7d") -> list:
    """Top clicked protocols for the range."""
    start, end = _date_range(range_str)

    click_events = _fetch_events(start, end, "protocol_click")
    click_stats = defaultdict(lambda: {"title": "", "enterpriseId": "", "clicks": 0, "uniqueUsers": set()})
    
    for d in click_events:
        pid = d.get("protocolId", "unknown")
        click_stats[pid]["title"] = d.get("protocolTitle", pid)
        click_stats[pid]["enterpriseId"] = d.get("enterpriseId", "")
        click_stats[pid]["clicks"] += 1
        click_stats[pid]["uniqueUsers"].add(d.get("userId", ""))

    result = []
    for pid, stats in click_stats.items():
        result.append({
            "protocolId": pid,
            "title": stats["title"],
            "enterpriseId": stats["enterpriseId"],
            "clicks": stats["clicks"],
            "uniqueUsers": len(stats["uniqueUsers"]),
        })
    
    result.sort(key=lambda x: x["clicks"], reverse=True)
    return result[:50]  # top 50
