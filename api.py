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
    readings: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class APIStatus(BaseModel):
    status: str
    ordotools_available: bool
    timestamp: str

# Cache for liturgical calendars
_calendar_cache = {}

def get_calendar(year: int) -> List:
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

def find_date_in_calendar(calendar_data: List, target_date: date) -> object:
    """Find a specific date in the calendar data"""
    target_str = target_date.isoformat()
    
    for day_data in calendar_data:
        if hasattr(day_data, 'date'):
            date_str = str(day_data.date)
            if len(date_str) >= 10 and date_str[:10] == target_str:
                return day_data
    
    return None

def get_ordo_for_date(target_date: date) -> OrdoDay:
    """Get ordo data for a specific date"""
    calendar_data = get_calendar(target_date.year)
    
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
