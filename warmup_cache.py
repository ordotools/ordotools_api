from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import os
# import json
import shutil
from pathlib import Path
import pickle


# Try multiple ways to get version information
def get_ordotools_version():
    try:
        import ordotools
    except ImportError:
        return None

    # Try __version__ attribute first
    if hasattr(ordotools, '__version__'):
        return ordotools.__version__

    # Try to read from setup.py or package metadata
    try:
        import pkg_resources
        return pkg_resources.get_distribution('ordotools').version
    except:
        pass

    # Try to get git commit hash if installed from git
    try:
        import subprocess
        module_path = ordotools.__file__
        if module_path:
            module_dir = Path(module_path).parent.parent
            if (module_dir / '.git').exists():
                result = subprocess.run(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=module_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return f"git-{result.stdout.strip()}"
    except:
        pass

    # Try to get last modified time of the module as a fallback
    try:
        module_path = ordotools.__file__
        if module_path:
            stat = Path(module_path).stat()
            return f"mod-{int(stat.st_mtime)}"
    except:
        pass

    # Fallback to timestamp
    return f"unknown-{int(datetime.now().timestamp())}"

# Import ordotools
try:
    from ordotools import LiturgicalCalendar
    ORDOTOOLS_AVAILABLE = True
    ORDOTOOLS_VERSION = get_ordotools_version()
except ImportError:
    ORDOTOOLS_AVAILABLE = False
    ORDOTOOLS_VERSION = None

app = FastAPI(
    title="OrdoTools Calendar API",
    description="Traditional Catholic Ordo and Calendar API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache configuration
CACHE_BASE_DIR = Path("ordotools_cache")
CACHE_BASE_DIR.mkdir(exist_ok=True)


# Models
class OrdoDay(BaseModel):
    date: date
    liturgical_season: Optional[str] = None
    liturgical_color: Optional[str] = None
    feast_name: Optional[str] = None
    feast_rank: Optional[str] = None
    saint_of_day: Optional[str] = None
    commemorations: List[str] = []
    readings: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class APIStatus(BaseModel):
    status: str
    ordotools_available: bool
    ordotools_version: Optional[str]
    cache_directory: Optional[str]
    timestamp: str


# In-memory cache for quick access
_calendar_cache = {}


def get_cache_dir() -> Path:
    """Get the current cache directory based on ordotools version"""
    if not ORDOTOOLS_AVAILABLE:
        return None
    return CACHE_BASE_DIR / f"v_{ORDOTOOLS_VERSION}"


def get_cache_file_path(year: int, calendar_type: str = "roman", locale: str = "la") -> Path:
    """Get the cache file path for specific parameters"""
    cache_dir = get_cache_dir()
    if not cache_dir:
        return None

    filename = f"{year}_{calendar_type}_{locale}.pkl"
    return cache_dir / filename


def cleanup_old_cache_dirs():
    """Remove old cache directories that don't match current version"""
    if not ORDOTOOLS_AVAILABLE:
        return

    current_cache_dir = get_cache_dir()

    for cache_dir in CACHE_BASE_DIR.iterdir():
        if cache_dir.is_dir() and cache_dir != current_cache_dir:
            print(f"Removing old cache directory: {cache_dir}")
            shutil.rmtree(cache_dir)


def load_calendar_from_cache(year: int, calendar_type: str = "roman", locale: str = "la") -> Optional[List]:
    """Load calendar data from cache file"""
    cache_file = get_cache_file_path(year, calendar_type, locale)
    if not cache_file or not cache_file.exists():
        return None

    try:
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Error loading cache file {cache_file}: {e}")
        # Remove corrupted cache file
        try:
            cache_file.unlink()
        except:
            pass
        return None


def save_calendar_to_cache(calendar_data: List, year: int, calendar_type: str = "roman", locale: str = "la"):
    """Save calendar data to cache file"""
    cache_file = get_cache_file_path(year, calendar_type, locale)
    if not cache_file:
        return

    # Ensure cache directory exists
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(calendar_data, f)
        print(f"Saved calendar data to cache: {cache_file}")
    except Exception as e:
        print(f"Error saving cache file {cache_file}: {e}")


def get_calendar(year: int, calendar_type: str = "roman", locale: str = "la") -> List:
    """Get or create liturgical calendar for a year with file-based caching"""
    if not ORDOTOOLS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="ordotools not available. Install with: pip install git+https://github.com/ordotools/ordotools.git"
        )

    # Create cache key for in-memory cache
    cache_key = f"{year}_{calendar_type}_{locale}"

    # Check in-memory cache first
    if cache_key in _calendar_cache:
        return _calendar_cache[cache_key]

    # Check file cache
    calendar_data = load_calendar_from_cache(year, calendar_type, locale)
    if calendar_data:
        print(f"Loaded calendar {cache_key} from file cache")
        _calendar_cache[cache_key] = calendar_data
        return calendar_data

    # Generate calendar data if not cached
    try:
        print(f"Generating calendar {cache_key} with ordotools...")
        calendar = LiturgicalCalendar(year, calendar_type, locale)
        calendar_data = calendar.build()

        # Save to both caches
        _calendar_cache[cache_key] = calendar_data
        save_calendar_to_cache(calendar_data, year, calendar_type, locale)

        # Clean up old cache directories after successful generation
        cleanup_old_cache_dirs()

        return calendar_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building calendar: {str(e)}")


def find_date_in_calendar(calendar_data: List, target_date: date) -> object:
    """Find a specific date in the calendar data"""
    target_str = target_date.isoformat()

    for day_data in calendar_data:
        if hasattr(day_data, 'date'):
            date_str = str(day_data.date)
            if len(date_str) >= 10 and date_str[:10] == target_str:
                return day_data

    return None


def get_ordo_for_date(target_date: date, calendar_type: str = "roman", locale: str = "la") -> OrdoDay:
    """Get ordo data for a specific date"""
    calendar_data = get_calendar(target_date.year, calendar_type, locale)

    day_data = find_date_in_calendar(calendar_data, target_date)

    if not day_data:
        raise HTTPException(status_code=404, detail=f"No data found for date {target_date}")

    # Extract commemorations
    commemorations = []
    if hasattr(day_data, '_com_1') and day_data._com_1 and hasattr(day_data._com_1, 'name') and day_data._com_1.name:
        commemorations.append(day_data._com_1.name)
    if hasattr(day_data, '_com_2') and day_data._com_2 and hasattr(day_data._com_2, 'name') and day_data._com_2.name:
        commemorations.append(day_data._com_2.name)
    if hasattr(day_data, '_com_3') and day_data._com_3 and hasattr(day_data._com_3, 'name') and day_data._com_3.name:
        commemorations.append(day_data._com_3.name)

    return OrdoDay(
        date=target_date,
        liturgical_season=None,
        liturgical_color=getattr(day_data, 'color', None),
        feast_name=getattr(day_data, '_name', None),
        feast_rank=getattr(day_data, 'rank_v', None),
        saint_of_day=None,
        commemorations=commemorations,
        readings=getattr(day_data, 'mass', None),
        notes=f"ID: {getattr(day_data, 'id', 'Unknown')}"
    )


# Endpoints
@app.get("/", response_model=APIStatus)
async def root():
    cache_dir = get_cache_dir()
    return APIStatus(
        status="healthy",
        ordotools_available=ORDOTOOLS_AVAILABLE,
        ordotools_version=ORDOTOOLS_VERSION,
        cache_directory=str(cache_dir) if cache_dir else None,
        timestamp=datetime.now().isoformat()
    )


@app.get("/today", response_model=OrdoDay)
async def get_today():
    return get_ordo_for_date(date.today())


@app.get("/day/{date_str}", response_model=OrdoDay)
async def get_day(date_str: str):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    return get_ordo_for_date(target_date)


@app.get("/month/{year}/{month}")
async def get_month(year: int, month: int):
    if not (1900 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid year or month")

    # Calculate days in month
    if month == 2:
        days_in_month = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    elif month in [4, 6, 9, 11]:
        days_in_month = 30
    else:
        days_in_month = 31

    days = []
    for day in range(1, days_in_month + 1):
        target_date = date(year, month, day)
        try:
            days.append(get_ordo_for_date(target_date))
        except HTTPException:
            continue

    return {
        "year": year,
        "month": month,
        "month_name": date(year, month, 1).strftime("%B"),
        "days": days
    }


@app.get("/year/{year}")
async def get_year(year: int):
    """Get the entire liturgical calendar for a year"""
    if not (1900 <= year <= 2100):
        raise HTTPException(status_code=400, detail="Invalid year")

    calendar_data = get_calendar(year)

    # Convert Feast objects to dictionaries for JSON serialization
    year_data = []
    for feast in calendar_data:
        try:
            ordo_day = get_ordo_for_date(datetime.strptime(str(feast.date)[:10], "%Y-%m-%d").date())
            year_data.append(ordo_day.dict())
        except:
            continue

    return {
        "year": year,
        "total_days": len(year_data),
        "calendar": year_data
    }


@app.post("/cache/clear")
async def clear_cache():
    """Clear all cached data"""
    global _calendar_cache
    _calendar_cache.clear()

    # Remove all cache directories
    if CACHE_BASE_DIR.exists():
        shutil.rmtree(CACHE_BASE_DIR)
        CACHE_BASE_DIR.mkdir(exist_ok=True)

    return {"message": "Cache cleared successfully"}


@app.get("/cache/status")
async def cache_status():
    """Get cache status information"""
    cache_dir = get_cache_dir()
    cache_files = []

    if cache_dir and cache_dir.exists():
        for cache_file in cache_dir.glob("*.pkl"):
            try:
                stat = cache_file.stat()
                cache_files.append({
                    "filename": cache_file.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except:
                continue

    return {
        "ordotools_version": ORDOTOOLS_VERSION,
        "cache_directory": str(cache_dir) if cache_dir else None,
        "in_memory_cache_keys": list(_calendar_cache.keys()),
        "cached_files": cache_files,
        "total_cached_files": len(cache_files)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
