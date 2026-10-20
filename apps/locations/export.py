import pandas as pd
from django.db.models import F
from django.http import HttpResponse

COLUMNS = [
    "id", "title", "description", "category", "address", "latitude", "longitude",
    "author", "avg_rating", "reviews_count", "views_7d", "popularity", "created_at", "updated_at",
]
FORMULA_PREFIXES = ("=", "+", "-", "@")


def locations_dataframe(queryset):
    rows = queryset.values(
        "id", "title", "description", "address", "latitude", "longitude",
        "avg_rating", "reviews_count", "views_7d", "popularity", "created_at", "updated_at",
        category_name=F("category__name"), author_name=F("author__username"),
    )
    df = pd.DataFrame.from_records(rows).rename(
        columns={"category_name": "category", "author_name": "author"}
    )
    df = df.reindex(columns=COLUMNS)
    df[["latitude", "longitude"]] = df[["latitude", "longitude"]].astype(float)
    df["avg_rating"] = df["avg_rating"].astype(float).round(2)
    df["popularity"] = df["popularity"].astype(float).round(2)
    for col in ("created_at", "updated_at"):
        df[col] = df[col].map(lambda v: v.isoformat() if pd.notna(v) else None)
    return df


def _escape_formulas(df):
    """Prevent spreadsheet formula injection from user-supplied text."""
    df = df.copy()
    for col in ("title", "description", "category", "address", "author"):
        df[col] = df[col].map(
            lambda v: "'" + v if isinstance(v, str) and v.startswith(FORMULA_PREFIXES) else v
        )
    return df


def export_response(df, fmt):
    if fmt == "csv":
        body = _escape_formulas(df).to_csv(index=False)
        content_type = "text/csv; charset=utf-8"
    else:
        body = df.to_json(orient="records", force_ascii=False)
        content_type = "application/json"
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="locations.{fmt}"'
    return response
