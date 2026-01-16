"""
Agent #2: Historical Data Loader

Fetches historical OHLCV (Open, High, Low, Close, Volume) data for securities.
Supports multiple timeframes and date ranges.

Capabilities:
1. load_history - Load historical bars for a symbol
2. load_batch_history - Load history for multiple symbols
3. get_available_dates - Check what dates are cached
4. update_incremental - Fetch only new bars since last update
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import Message
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice, AgentCache, DataQualityLog
from shared.validators import DataValidator


class HistoricalDataLoader(BaseAgent):
    """Loads historical market data from Yahoo Finance."""

    def __init__(self):
        # Initialize validator and db before calling super().__init__()
        self.validator = DataValidator()
        self.db = get_database()
        
        # Cache TTL: 1 day for historical data (doesn't change)
        self.cache_ttl = timedelta(days=1)
        
        # Valid intervals for yfinance
        self.valid_intervals = {
            "1m", "2m", "5m", "15m", "30m", "60m", "90m",  # Intraday
            "1h", "1d", "5d", "1wk", "1mo", "3mo"  # Daily+
        }
        
        super().__init__()

    def get_metadata(self):
        """Return agent metadata."""
        from shared.data_models import AgentMetadata, AgentCapability
        
        return AgentMetadata(
            agent_id="historical_data_loader",
            name="Historical Data Loader",
            description="Loads historical OHLCV data for backtesting and analysis",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="load_history",
                    description="Load historical bars for a symbol",
                    parameters={
                        "symbol": "str",
                        "start_date": "str (YYYY-MM-DD)",
                        "end_date": "str (YYYY-MM-DD, optional)",
                        "interval": "str (default: 1d)"
                    }
                ),
                AgentCapability(
                    name="load_batch_history",
                    description="Load history for multiple symbols",
                    parameters={
                        "symbols": "List[str]",
                        "start_date": "str",
                        "end_date": "str (optional)",
                        "interval": "str (default: 1d)"
                    }
                ),
                AgentCapability(
                    name="get_available_dates",
                    description="Check what dates are cached for a symbol",
                    parameters={
                        "symbol": "str",
                        "interval": "str (optional)"
                    }
                ),
                AgentCapability(
                    name="update_incremental",
                    description="Fetch only new bars since last cached date",
                    parameters={
                        "symbol": "str",
                        "interval": "str (default: 1d)"
                    }
                )
            ],
            dependencies=[],
            category="data"
        )

    async def initialize(self):
        """Initialize database connection."""
        await self.db.initialize()
        logger.info(f"{self.agent_id} initialized with database")

    async def shutdown(self):
        """Cleanup resources."""
        await self.db.close()
        logger.info(f"{self.agent_id} shutdown complete")

    async def process_request(self, message: Message) -> Dict[str, Any]:
        """
        Process incoming messages (required by BaseAgent).
        
        Args:
            message: Message with capability and parameters
            
        Returns:
            Response dict with data or error
        """
        return await self.process_message(message)

    async def process_message(self, message: Message) -> Dict[str, Any]:
        """
        Process incoming messages and route to appropriate handler.
        
        Args:
            message: Message with topic and data
            
        Returns:
            Response dict with data or error
        """
        topic = message.topic
        params = message.data
        
        if topic == "load_history":
            return await self._handle_load_history(params)
        elif topic == "load_batch_history":
            return await self._handle_load_batch_history(params)
        elif topic == "get_available_dates":
            return await self._handle_get_available_dates(params)
        elif topic == "update_incremental":
            return await self._handle_update_incremental(params)
        else:
            return {
                "success": False,
                "error": f"Unknown topic: {topic}"
            }

    async def _handle_load_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load historical data for a single symbol.
        
        Args:
            params: {
                "symbol": str,
                "start_date": str (YYYY-MM-DD),
                "end_date": str (YYYY-MM-DD, optional),
                "interval": str (default: "1d")
            }
            
        Returns:
            {
                "success": bool,
                "data": List[Dict] with OHLCV bars,
                "count": int,
                "cached": bool
            }
        """
        symbol = params.get("symbol", "").strip().upper()
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        interval = params.get("interval", "1d")
        
        # Validate inputs
        try:
            self.validator.validate_symbol(symbol)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        
        if interval not in self.valid_intervals:
            return {
                "success": False,
                "error": f"Invalid interval: {interval}. Valid: {sorted(self.valid_intervals)}"
            }
        
        if not start_date:
            return {
                "success": False,
                "error": "start_date is required (format: YYYY-MM-DD)"
            }
        
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
            
            # Check cache first
            cache_key = f"{symbol}_{start_date}_{end_date or 'now'}_{interval}"
            cached_data = await self._get_from_cache(cache_key)
            
            if cached_data:
                logger.info(f"Cache hit for {symbol} history")
                return {
                    "success": True,
                    "data": cached_data,
                    "count": len(cached_data),
                    "cached": True
                }
            
            # Fetch from yfinance
            logger.info(f"Fetching history for {symbol} from {start_date} to {end_date or 'now'}")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_dt, end=end_dt, interval=interval)
            
            if hist.empty:
                logger.warning(f"No data returned for {symbol}")
                return {
                    "success": False,
                    "error": f"No historical data available for {symbol}"
                }
            
            # Convert to list of dicts and validate
            bars = []
            async with self.db.get_session() as session:
                for date, row in hist.iterrows():
                    try:
                        # Validate OHLC
                        self.validator.validate_ohlc(
                            open_price=float(row['Open']),
                            high=float(row['High']),
                            low=float(row['Low']),
                            close=float(row['Close'])
                        )
                        
                        # Validate volume
                        volume = int(row['Volume'])
                        self.validator.validate_volume(volume)
                        
                    except Exception as e:
                        # Log validation failure
                        await self._log_data_quality_issue(
                            session,
                            agent_id=self.agent_id,
                            data_type="historical_bar",
                            issue_type="validation",
                            description=f"{symbol} {date}: {str(e)}",
                            severity="warning"
                        )
                        continue  # Skip invalid bar
                    
                    bar_data = {
                        "symbol": symbol,
                        "date": date.to_pydatetime(),  # Convert pandas Timestamp to Python datetime
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": volume,
                        "adj_close": float(row.get('Close', row['Close'])),  # yfinance auto-adjusts
                        "interval": interval,
                        "source": "yfinance"
                    }
                    bars.append(bar_data)
                    
                    # Store in database (check for existing record first)
                    from sqlalchemy import select
                    stmt = select(HistoricalPrice).where(
                        HistoricalPrice.symbol == bar_data['symbol'],
                        HistoricalPrice.date == bar_data['date'],
                        HistoricalPrice.interval == bar_data['interval']
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing record
                        for key, value in bar_data.items():
                            setattr(existing, key, value)
                    else:
                        # Insert new record
                        hist_price = HistoricalPrice(**bar_data)
                        session.add(hist_price)
                
                await session.commit()
            
            # Cache the results
            await self._save_to_cache(cache_key, bars)
            
            # Publish event
            await self.publish_event(
                "historical_data_loaded",
                {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date or "now",
                    "interval": interval,
                    "bar_count": len(bars)
                }
            )
            
            logger.info(f"Loaded {len(bars)} bars for {symbol}")
            return {
                "success": True,
                "data": bars,
                "count": len(bars),
                "cached": False
            }
            
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            return {
                "success": False,
                "error": f"Invalid date format: {e}"
            }
        except Exception as e:
            logger.error(f"Error loading history for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _handle_load_batch_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load historical data for multiple symbols.
        
        Args:
            params: {
                "symbols": List[str],
                "start_date": str,
                "end_date": str (optional),
                "interval": str (default: "1d")
            }
            
        Returns:
            {
                "success": bool,
                "results": Dict[symbol -> data],
                "summary": {success_count, fail_count}
            }
        """
        symbols = params.get("symbols", [])
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        interval = params.get("interval", "1d")
        
        if not symbols:
            return {
                "success": False,
                "error": "symbols list is required"
            }
        
        results = {}
        success_count = 0
        fail_count = 0
        
        for symbol in symbols:
            result = await self._handle_load_history({
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "interval": interval
            })
            
            results[symbol] = result
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Batch load complete: {success_count} success, {fail_count} failed")
        return {
            "success": True,
            "results": results,
            "summary": {
                "total": len(symbols),
                "success_count": success_count,
                "fail_count": fail_count
            }
        }

    async def _handle_get_available_dates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get available cached dates for a symbol.
        
        Args:
            params: {"symbol": str, "interval": str (optional)}
            
        Returns:
            {
                "success": bool,
                "dates": List[str],
                "count": int,
                "earliest": str,
                "latest": str
            }
        """
        symbol = params.get("symbol", "").strip().upper()
        interval = params.get("interval", "1d")
        
        if not self.validator.validate_symbol(symbol):
            return {
                "success": False,
                "error": f"Invalid symbol: {symbol}"
            }
        
        try:
            async with self.db.get_session() as session:
                # Query database for dates
                stmt = (
                    select(HistoricalPrice.date)
                    .where(HistoricalPrice.symbol == symbol)
                    .order_by(HistoricalPrice.date)
                )
                result = await session.execute(stmt)
                dates = [row[0].strftime("%Y-%m-%d") for row in result.fetchall()]
            
            if not dates:
                return {
                    "success": True,
                    "dates": [],
                    "count": 0,
                    "earliest": None,
                    "latest": None
                }
            
            return {
                "success": True,
                "dates": dates,
                "count": len(dates),
                "earliest": dates[0],
                "latest": dates[-1]
            }
            
        except Exception as e:
            logger.error(f"Error getting available dates for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _handle_update_incremental(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch only new bars since last cached date.
        
        Args:
            params: {
                "symbol": str,
                "interval": str (default: "1d")
            }
            
        Returns:
            {
                "success": bool,
                "new_bars": int,
                "latest_date": str
            }
        """
        symbol = params.get("symbol", "").strip().upper()
        interval = params.get("interval", "1d")
        
        # Get latest cached date
        dates_result = await self._handle_get_available_dates({"symbol": symbol})
        
        if not dates_result["success"]:
            return dates_result
        
        latest_cached = dates_result.get("latest")
        
        if not latest_cached:
            # No cached data, fetch last 30 days
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            # Fetch from day after latest cached
            latest_dt = datetime.strptime(latest_cached, "%Y-%m-%d")
            next_day = latest_dt + timedelta(days=1)
            
            # If next day is in the future, nothing to fetch
            if next_day.date() > datetime.now().date():
                return {
                    "success": True,
                    "new_bars": 0,
                    "bars_loaded": 0,
                    "latest_date": latest_cached,
                    "message": "Data is already up to date"
                }
            
            start_date = next_day.strftime("%Y-%m-%d")
        
        # Load new data
        result = await self._handle_load_history({
            "symbol": symbol,
            "start_date": start_date,
            "interval": interval
        })
        
        if not result["success"]:
            return result
        
        # Convert latest date to string for comparison
        latest_date = result["data"][-1]["date"] if result["data"] else latest_cached
        if hasattr(latest_date, 'strftime'):
            latest_date = latest_date.strftime("%Y-%m-%d")
        elif hasattr(latest_date, 'isoformat'):
            latest_date = latest_date.isoformat().split('T')[0]
        
        return {
            "success": True,
            "new_bars": result["count"],
            "latest_date": latest_date,
            "data": result["data"]
        }

    async def _get_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Get data from cache if not expired."""
        try:
            async with self.db.get_session() as session:
                stmt = select(AgentCache).where(
                    and_(
                        AgentCache.agent_id == self.agent_id,
                        AgentCache.cache_key == cache_key,
                        AgentCache.expires_at > datetime.utcnow()
                    )
                )
                result = await session.execute(stmt)
                cache_entry = result.scalar_one_or_none()
                
                if cache_entry:
                    import json
                    return json.loads(cache_entry.cache_value)
                return None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def _save_to_cache(self, cache_key: str, data: List[Dict]):
        """Save data to cache with TTL."""
        try:
            async with self.db.get_session() as session:
                # Delete old cache entry if exists
                stmt = select(AgentCache).where(
                    and_(
                        AgentCache.agent_id == self.agent_id,
                        AgentCache.cache_key == cache_key
                    )
                )
                result = await session.execute(stmt)
                old_entry = result.scalar_one_or_none()
                if old_entry:
                    await session.delete(old_entry)
                    await session.commit()  # Commit the delete first
                
                # Create new cache entry
                # Convert datetime objects to ISO format strings for JSON serialization
                import json
                from datetime import datetime as dt
                
                def json_serial(obj):
                    """JSON serializer for objects not serializable by default json code"""
                    if isinstance(obj, dt):
                        return obj.isoformat()
                    raise TypeError(f"Type {type(obj)} not serializable")
                
                cache_entry = AgentCache(
                    agent_id=self.agent_id,
                    cache_key=cache_key,
                    cache_value=json.dumps(data, default=json_serial),
                    expires_at=datetime.utcnow() + self.cache_ttl
                )
                session.add(cache_entry)
                await session.commit()
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def _log_data_quality_issue(
        self,
        session: AsyncSession,
        agent_id: str,
        data_type: str,
        issue_type: str,
        description: str,
        severity: str
    ):
        """Log data quality issue to database."""
        log_entry = DataQualityLog(
            agent_id=agent_id,
            data_type=data_type,
            issue_type=issue_type,
            description=description,
            severity=severity
        )
        session.add(log_entry)
