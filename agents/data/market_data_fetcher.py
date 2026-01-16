"""
Agent #1: Market Data Fetcher

Fetches real-time stock prices, quotes, and trades from market data APIs.
This is the foundation agent for all market data operations.

Capabilities:
- Fetch current price for a symbol
- Fetch quote with bid/ask
- Batch fetch multiple symbols
- Cache recent data
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf
from loguru import logger
from sqlalchemy import select

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import AgentCapability, AgentMetadata, Message
from shared.database.connection import get_database
from shared.database.models import MarketQuote
from shared.validators import DataValidator, ValidationError


class MarketDataFetcher(BaseAgent):
    """
    Agent #1: Market Data Fetcher
    
    Fetches real-time market data from Yahoo Finance API.
    Validates data quality and caches results in database.
    
    Dependencies: None (foundational agent)
    Publishes to: market_data_updates
    """
    
    def __init__(self):
        """Initialize the Market Data Fetcher agent."""
        super().__init__()
        self.db = get_database()
        self.cache_ttl_seconds = 15  # Cache data for 15 seconds
        
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="market_data_fetcher",
            name="Market Data Fetcher",
            description="Fetches real-time stock prices, quotes, and trades",
            category="data",
            capabilities=[
                AgentCapability(
                    name="fetch_price",
                    description="Get current price for a symbol",
                    parameters={"symbol": "str"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="fetch_quote",
                    description="Get full quote with bid/ask spreads",
                    parameters={"symbol": "str", "use_cache": "bool"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="fetch_batch",
                    description="Fetch quotes for multiple symbols",
                    parameters={"symbols": "List[str]", "use_cache": "bool"},
                    returns="Dict[str, List[Dict]]",
                ),
                AgentCapability(
                    name="validate_symbol",
                    description="Check if a symbol is valid",
                    parameters={"symbol": "str"},
                    returns="Dict[str, bool]",
                ),
            ],
            subscribes_to=["market_data_request"],
            publishes_to=["market_data_updates", "data_quality_alerts"],
        )
    
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """
        Process incoming requests.
        
        Args:
            message: The request message
        
        Returns:
            Response data
        """
        action = message.topic
        data = message.data
        
        try:
            if action == "fetch_price":
                return await self._handle_fetch_price(data)
            
            elif action == "fetch_quote":
                return await self._handle_fetch_quote(data)
            
            elif action == "fetch_batch":
                return await self._handle_fetch_batch(data)
            
            elif action == "validate_symbol":
                return await self._handle_validate_symbol(data)
            
            else:
                return {
                    "error": f"Unknown action: {action}",
                    "available_actions": [c.name for c in self.metadata.capabilities],
                }
        
        except Exception as e:
            logger.error(f"Error processing request in {self.agent_id}: {e}")
            return {"error": str(e), "action": action}
    
    async def _handle_fetch_price(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fetch_price request.
        
        Args:
            data: Request data with 'symbol' key
        
        Returns:
            Price data
        """
        symbol = data.get("symbol")
        if not symbol:
            return {"error": "Missing required parameter: symbol"}
        
        try:
            # Sanitize and validate symbol
            symbol = DataValidator.sanitize_symbol(symbol)
            DataValidator.validate_symbol(symbol)
            
            # Fetch data from Yahoo Finance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or "currentPrice" not in info:
                # Try fast_info as fallback
                try:
                    price = ticker.fast_info.last_price
                except Exception:
                    return {
                        "error": f"Could not fetch price for symbol: {symbol}",
                        "symbol": symbol,
                    }
            else:
                price = info.get("currentPrice")
            
            # Validate price
            DataValidator.validate_price(price)
            
            result = {
                "symbol": symbol,
                "price": price,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "yfinance",
            }
            
            # Publish update event
            await self.publish_event(
                topic="market_data_updates",
                data={"type": "price_update", "symbol": symbol, "price": price},
            )
            
            return result
        
        except ValidationError as e:
            logger.warning(f"Validation error for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
        
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    async def _handle_fetch_quote(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fetch_quote request.
        
        Args:
            data: Request data with 'symbol' and optional 'use_cache'
        
        Returns:
            Full quote data
        """
        symbol = data.get("symbol")
        use_cache = data.get("use_cache", True)
        
        if not symbol:
            return {"error": "Missing required parameter: symbol"}
        
        try:
            # Sanitize and validate symbol
            symbol = DataValidator.sanitize_symbol(symbol)
            DataValidator.validate_symbol(symbol)
            
            # Check cache if enabled
            if use_cache:
                cached = await self._get_cached_quote(symbol)
                if cached:
                    logger.debug(f"Using cached quote for {symbol}")
                    return cached
            
            # Fetch fresh data
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Build quote data
            quote_data = {
                "symbol": symbol,
                "timestamp": datetime.utcnow(),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "bid": info.get("bid"),
                "ask": info.get("ask"),
                "bid_size": info.get("bidSize"),
                "ask_size": info.get("askSize"),
                "volume": info.get("volume"),
                "source": "yfinance",
            }
            
            # Validate quote
            DataValidator.validate_quote(quote_data)
            
            # Store in database
            await self._store_quote(quote_data)
            
            # Convert datetime to ISO format for JSON
            result = quote_data.copy()
            result["timestamp"] = quote_data["timestamp"].isoformat()
            
            # Publish update event
            await self.publish_event(
                topic="market_data_updates",
                data={"type": "quote_update", "symbol": symbol, "quote": result},
            )
            
            return result
        
        except ValidationError as e:
            logger.warning(f"Validation error for {symbol}: {e}")
            
            # Publish data quality alert
            await self.publish_alert(
                topic="data_quality_alerts",
                data={
                    "agent_id": self.agent_id,
                    "symbol": symbol,
                    "issue": str(e),
                    "severity": "medium",
                },
            )
            
            return {"error": str(e), "symbol": symbol}
        
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    async def _handle_fetch_batch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fetch_batch request for multiple symbols.
        
        Args:
            data: Request data with 'symbols' list
        
        Returns:
            Batch quote data
        """
        symbols = data.get("symbols", [])
        use_cache = data.get("use_cache", True)
        
        if not symbols:
            return {"error": "Missing required parameter: symbols"}
        
        if not isinstance(symbols, list):
            return {"error": "symbols must be a list"}
        
        results = []
        errors = []
        
        for symbol in symbols:
            try:
                quote = await self._handle_fetch_quote({
                    "symbol": symbol,
                    "use_cache": use_cache,
                })
                
                if "error" in quote:
                    errors.append({"symbol": symbol, "error": quote["error"]})
                else:
                    results.append(quote)
            
            except Exception as e:
                errors.append({"symbol": symbol, "error": str(e)})
        
        return {
            "quotes": results,
            "errors": errors,
            "total": len(symbols),
            "successful": len(results),
            "failed": len(errors),
        }
    
    async def _handle_validate_symbol(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle symbol validation request.
        
        Args:
            data: Request data with 'symbol'
        
        Returns:
            Validation result
        """
        symbol = data.get("symbol")
        
        if not symbol:
            return {"error": "Missing required parameter: symbol"}
        
        try:
            symbol = DataValidator.sanitize_symbol(symbol)
            DataValidator.validate_symbol(symbol)
            
            # Try to fetch info to confirm symbol exists
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            is_valid = bool(info and ("currentPrice" in info or "regularMarketPrice" in info))
            
            return {
                "symbol": symbol,
                "valid": is_valid,
                "company_name": info.get("shortName") or info.get("longName"),
            }
        
        except ValidationError as e:
            return {"symbol": symbol, "valid": False, "error": str(e)}
        
        except Exception as e:
            return {"symbol": symbol, "valid": False, "error": str(e)}
    
    async def _get_cached_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached quote from database if recent enough.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Cached quote data or None
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.cache_ttl_seconds)
            
            async with self.db.get_session() as session:
                stmt = (
                    select(MarketQuote)
                    .where(MarketQuote.symbol == symbol)
                    .where(MarketQuote.timestamp >= cutoff_time)
                    .order_by(MarketQuote.timestamp.desc())
                    .limit(1)
                )
                
                result = await session.execute(stmt)
                quote = result.scalar_one_or_none()
                
                if quote:
                    return {
                        "symbol": quote.symbol,
                        "timestamp": quote.timestamp.isoformat(),
                        "price": quote.price,
                        "bid": quote.bid,
                        "ask": quote.ask,
                        "bid_size": quote.bid_size,
                        "ask_size": quote.ask_size,
                        "volume": quote.volume,
                        "source": quote.source,
                        "cached": True,
                    }
        
        except Exception as e:
            logger.error(f"Error fetching cached quote: {e}")
        
        return None
    
    async def _store_quote(self, quote_data: Dict[str, Any]) -> None:
        """
        Store quote in database.
        
        Args:
            quote_data: Quote data to store
        """
        try:
            quote = MarketQuote(
                symbol=quote_data["symbol"],
                timestamp=quote_data["timestamp"],
                price=quote_data["price"],
                bid=quote_data.get("bid"),
                ask=quote_data.get("ask"),
                bid_size=quote_data.get("bid_size"),
                ask_size=quote_data.get("ask_size"),
                volume=quote_data.get("volume"),
                source=quote_data.get("source", "unknown"),
            )
            
            async with self.db.get_session() as session:
                session.add(quote)
                await session.commit()
            
            logger.debug(f"Stored quote for {quote_data['symbol']} in database")
        
        except Exception as e:
            logger.error(f"Error storing quote in database: {e}")
