from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import os
import logging

# Import ordotools - handle import gracefully
try:
    import ordotools
    from ordotools import calendar as ordo_calendar
    ORDOTOOLS_AVAILABLE = True
except ImportError:
    ORDOTOOLS_AVAILABLE = False
    logging.warning("ordotools not available. Install with: pip install ordotools")

app = FastAPI(
    title="OrdoTools Calendar API",
    description="Traditional Catholic Ordo and Calendar API - Standalone Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - Allow your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.onrender.com",  # All Render domains
        "http://localhost:3000",   # Local development
        "http://localhost:8000",   # Local development
        "http://localhost:5000",   # Local development
        "https://your-frontend-service.onrender.com",  # Replace with your actual frontend URL
        "*"  # Remove this in production, add specific domains
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Pydantic models
class OrdoDay(BaseModel):
    date: date
    liturgical_season: Optional[str] = None
    liturgical_color: Optional[str] = None
    feast_name: Optional[str] = None
    feast_rank: Optional[str] = None
    commemorations: List[str] = []
    proper_readings: Optional[Dict[str, Any]] = None
    saint_of_day: Optional[str] = None
    notes: Optional[str] = None

class OrdoMonth(BaseModel):
    year: int
    month: int
    month_name: str
    days: List[OrdoDay]

class OrdoYear(BaseModel):
    year: int
    liturgical_year: Optional[str] = None
    months: List[OrdoMonth]
    major_feasts: List[Dict[str, Any]] = []

class APIStatus(BaseModel):
    status: str
    ordotools_available: bool
    version: str
    timestamp: str
    uptime_seconds: Optional[float] = None

# Track startup time for uptime
import time
startup_time = time.time()

def get_ordo_data_for_date(target_date: date) -> OrdoDay:
    """Get ordotools data for a specific date"""
    if not ORDOTOOLS_AVAILABLE:
        return OrdoDay(
            date=target_date,
            liturgical_season="Ordinary Time",
            liturgical_color="Green",
            feast_name=None,
            feast_rank="Ferial",
            commemorations=[],
            proper_readings=None,
            saint_of_day=None,
            notes="ordotools not available - install for full functionality"
        )
    
    try:
        ordo_data = ordo_calendar.get_day(target_date.year, target_date.month, target_date.day)
        
        return OrdoDay(
            date=target_date,
            liturgical_season=getattr(ordo_data, 'season', None),
            liturgical_color=getattr(ordo_data, 'color', None),
            feast_name=getattr(ordo_data, 'feast', None),
            feast_rank=getattr(ordo_data, 'rank', None),
            commemorations=getattr(ordo_data, 'commemorations', []),
            proper_readings=getattr(ordo_data, 'readings', None),
            saint_of_day=getattr(ordo_data, 'saint', None),
            notes=getattr(ordo_data, 'notes', None)
        )
    except Exception as e:
        logging.error(f"Error getting ordo data for {target_date}: {e}")
        return OrdoDay(
            date=target_date,
            notes=f"Error retrieving ordo data: {str(e)}"
        )

# Health and status endpoints
@app.get("/", response_model=APIStatus)
async def root():
    """API root endpoint with status"""
    return APIStatus(
        status="healthy",
        ordotools_available=ORDOTOOLS_AVAILABLE,
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=time.time() - startup_time
    )

@app.get("/health", response_model=APIStatus)
async def health_check():
    """Health check endpoint for monitoring"""
    return APIStatus(
        status="healthy",
        ordotools_available=ORDOTOOLS_AVAILABLE,
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=time.time() - startup_time
    )

@app.get("/status", response_model=APIStatus)
async def detailed_status():
    """Detailed API status"""
    return APIStatus(
        status="healthy",
        ordotools_available=ORDOTOOLS_AVAILABLE,
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=time.time() - startup_time
    )

# Calendar endpoints
@app.get("/today", response_model=OrdoDay)
async def get_today_ordo():
    """Get today's ordo"""
    today = date.today()
    return get_ordo_data_for_date(today)

@app.get("/day/{date_str}", response_model=OrdoDay)
async def get_day_ordo(date_str: str):
    """Get ordo details for a specific date (format: YYYY-MM-DD)"""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    return get_ordo_data_for_date(target_date)

@app.get("/month/{year}/{month}", response_model=OrdoMonth)
async def get_month_ordo(year: int, month: int):
    """Get liturgical calendar for a specific month"""
    if year < 1900 or year > 2100:
        raise HTTPException(status_code=400, detail="Year must be between 1900 and 2100")
    
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    # Get days in month
    if month in [1, 3, 5, 7, 8, 10, 12]:
        days_in_month = 31
    elif month in [4, 6, 9, 11]:
        days_in_month = 30
    else:  # February
        days_in_month = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    
    month_days = []
    for day in range(1, days_in_month + 1):
        target_date = date(year, month, day)
        month_days.append(get_ordo_data_for_date(target_date))
    
    return OrdoMonth(
        year=year,
        month=month,
        month_name=date(year, month, 1).strftime("%B"),
        days=month_days
    )

@app.get("/year/{year}", response_model=OrdoYear)
async def get_year_ordo(year: int):
    """Get complete liturgical calendar for a specific year"""
    if year < 1900 or year > 2100:
        raise HTTPException(status_code=400, detail="Year must be between 1900 and 2100")
    
    months = []
    major_feasts = []
    
    for month in range(1, 13):
        month_days = []
        
        # Get days in month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:  # February
            days_in_month = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
        
        for day in range(1, days_in_month + 1):
            target_date = date(year, month, day)
            ordo_day = get_ordo_data_for_date(target_date)
            month_days.append(ordo_day)
            
            # Collect major feasts
            if ordo_day.feast_rank and ordo_day.feast_rank.lower() in ['solemnity', 'feast']:
                major_feasts.append({
                    "date": target_date.isoformat(),
                    "name": ordo_day.feast_name,
                    "rank": ordo_day.feast_rank
                })
        
        months.append(OrdoMonth(
            year=year,
            month=month,
            month_name=target_date.strftime("%B"),
            days=month_days
        ))
    
    return OrdoYear(
        year=year,
        liturgical_year=f"{year-1}-{year}" if year > 1900 else str(year),
        months=months,
        major_feasts=major_feasts
    )

@app.get("/feasts/{year}")
async def get_major_feasts(year: int):
    """Get major feasts for a specific year"""
    if year < 1900 or year > 2100:
        raise HTTPException(status_code=400, detail="Year must be between 1900 and 2100")
    
    major_feasts = []
    
    # Scan the entire year for major feasts
    for month in range(1, 13):
        if month in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:
            days_in_month = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
        
        for day in range(1, days_in_month + 1):
            target_date = date(year, month, day)
            ordo_day = get_ordo_data_for_date(target_date)
            
            if ordo_day.feast_rank and ordo_day.feast_rank.lower() in ['solemnity', 'feast']:
                major_feasts.append({
                    "date": target_date.isoformat(),
                    "name": ordo_day.feast_name,
                    "rank": ordo_day.feast_rank,
                    "color": ordo_day.liturgical_color,
                    "season": ordo_day.liturgical_season
                })
    
    return {
        "year": year,
        "major_feasts": major_feasts,
        "count": len(major_feasts)
    }

@app.get("/season/{year}/{season}")
async def get_liturgical_season(year: int, season: str):
    """Get dates for a specific liturgical season"""
    if year < 1900 or year > 2100:
        raise HTTPException(status_code=400, detail="Year must be between 1900 and 2100")
    
    valid_seasons = ['advent', 'christmas', 'ordinary', 'lent', 'easter']
    if season.lower() not in valid_seasons:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid season. Must be one of: {', '.join(valid_seasons)}"
        )
    
    season_days = []
    
    # Scan the year for days in the specified season
    for month in range(1, 13):
        if month in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:
            days_in_month = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
        
        for day in range(1, days_in_month + 1):
            target_date = date(year, month, day)
            ordo_day = get_ordo_data_for_date(target_date)
            
            if ordo_day.liturgical_season and season.lower() in ordo_day.liturgical_season.lower():
                season_days.append({
                    "date": target_date.isoformat(),
                    "feast_name": ordo_day.feast_name,
                    "rank": ordo_day.feast_rank,
                    "color": ordo_day.liturgical_color
                })
    
    return {
        "year": year,
        "season": season.title(),
        "days": season_days,
        "count": len(season_days)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
