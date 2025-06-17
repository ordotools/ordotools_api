from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import os

# Import ordotools
try:
    from ordotools import LiturgicalCalendar
    ORDOTOOLS_AVAILABLE = True
except ImportError:
    ORDOTOOLS_AVAILABLE = False

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

# Models
class OrdoDay(BaseModel):
    date: date
    liturgical_season: Optional[str] = None
    liturgical_color: Optional[str] = None
    feast_name: Optional[str] = None
    feast_rank: Optional[str] = None
    saint_of_day: Optional[str] = None
    commemorations: List[str] = []
    notes: Optional[str] = None

class APIStatus(BaseModel):
    status: str
    ordotools_available: bool
    timestamp: str

# Cache for liturgical calendars
_calendar_cache = {}

def get_calendar(year: int) -> Dict:
    """Get or create liturgical calendar for a year"""
    if not ORDOTOOLS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="ordotools not available. Install with: pip install git+https://github.com/ordotools/ordotools.git"
        )
    
    if year not in _calendar_cache:
        try:
            calendar = LiturgicalCalendar(year, "roman", "la")
            _calendar_cache[year] = calendar.build()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error building calendar: {str(e)}")
    
    return _calendar_cache[year]

def get_ordo_for_date(target_date: date) -> OrdoDay:
    """Get ordo data for a specific date"""
    calendar_data = get_calendar(target_date.year)
    
    # Find the specific date in the calendar data
    date_key = target_date.strftime("%Y-%m-%d")
    
    # The structure depends on how ordotools returns data
    # You might need to adjust this based on the actual structure
    day_data = None
    for day in calendar_data:  # Assuming calendar_data is iterable
        if hasattr(day, 'date') and day.date == target_date:
            day_data = day
            break
        elif isinstance(day, dict) and day.get('date') == date_key:
            day_data = day
            break
    
    if not day_data:
        raise HTTPException(status_code=404, detail=f"No data found for date {target_date}")
    
    # Extract data based on ordotools structure
    return OrdoDay(
        date=target_date,
        liturgical_season=getattr(day_data, 'season', day_data.get('season') if isinstance(day_data, dict) else None),
        liturgical_color=getattr(day_data, 'color', day_data.get('color') if isinstance(day_data, dict) else None),
        feast_name=getattr(day_data, 'feast', day_data.get('feast') if isinstance(day_data, dict) else None),
        feast_rank=getattr(day_data, 'rank', day_data.get('rank') if isinstance(day_data, dict) else None),
        saint_of_day=getattr(day_data, 'saint', day_data.get('saint') if isinstance(day_data, dict) else None),
        commemorations=getattr(day_data, 'commemorations', day_data.get('commemorations', []) if isinstance(day_data, dict) else []),
        notes="Data from ordotools"
    )

# Endpoints
@app.get("/", response_model=APIStatus)
async def root():
    return APIStatus(
        status="healthy",
        ordotools_available=ORDOTOOLS_AVAILABLE,
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
            # Skip days that don't have data
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
    
    return {
        "year": year,
        "calendar": calendar_data
    }

@app.get("/debug/{year}")
async def debug_calendar(year: int):
    """Debug endpoint to see raw calendar structure"""
    calendar_data = get_calendar(year)
    
    # Return first few items to understand structure
    if isinstance(calendar_data, list):
        sample = calendar_data[:5] if len(calendar_data) > 5 else calendar_data
    elif isinstance(calendar_data, dict):
        sample = dict(list(calendar_data.items())[:5])
    else:
        sample = str(calendar_data)[:1000]
    
    return {
        "type": str(type(calendar_data)),
        "length": len(calendar_data) if hasattr(calendar_data, '__len__') else "unknown",
        "sample": sample
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
