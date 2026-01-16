"""
Data validation utilities for market data.

Ensures data quality and catches anomalies.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class DataValidator:
    """
    Validates market data for quality and correctness.
    
    Checks:
    - Symbol format
    - Price ranges
    - Volume ranges
    - Date/time validity
    - Data completeness
    """
    
    # Common stock symbol pattern (supports international exchanges like .NS, .BO, etc.)
    # Also supports indices with hyphens (DX-Y.NYB) and carets (^TNX)
    SYMBOL_PATTERN = re.compile(r'^[\^]?[A-Z0-9\-]{1,12}(\.[A-Z]{1,5})?$')
    
    # Reasonable price bounds (in USD)
    MIN_PRICE = 0.01
    MAX_PRICE = 1_000_000.0
    
    # Volume bounds
    MIN_VOLUME = 0
    MAX_VOLUME = 10_000_000_000
    
    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        """
        Validate stock symbol format.
        
        Args:
            symbol: Stock symbol to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If symbol is invalid
        """
        if not symbol:
            raise ValidationError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        
        if not cls.SYMBOL_PATTERN.match(symbol):
            raise ValidationError(
                f"Invalid symbol format: {symbol}. "
                "Expected format: Letters/numbers/hyphens (1-12 chars), optional exchange suffix (.XX)"
            )
        
        return True
    
    @classmethod
    def validate_price(
        cls,
        price: float,
        field_name: str = "price",
        allow_zero: bool = False,
    ) -> bool:
        """
        Validate price value.
        
        Args:
            price: Price to validate
            field_name: Name of field (for error messages)
            allow_zero: Whether zero is acceptable
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If price is invalid
        """
        if price is None:
            raise ValidationError(f"{field_name} cannot be None")
        
        if not isinstance(price, (int, float)):
            raise ValidationError(f"{field_name} must be numeric, got {type(price)}")
        
        if price < 0:
            raise ValidationError(f"{field_name} cannot be negative: {price}")
        
        if price == 0 and not allow_zero:
            raise ValidationError(f"{field_name} cannot be zero")
        
        if price < cls.MIN_PRICE and price != 0:
            raise ValidationError(
                f"{field_name} too low: {price} (min: {cls.MIN_PRICE})"
            )
        
        if price > cls.MAX_PRICE:
            raise ValidationError(
                f"{field_name} too high: {price} (max: {cls.MAX_PRICE})"
            )
        
        return True
    
    @classmethod
    def validate_volume(cls, volume: int, allow_zero: bool = True) -> bool:
        """
        Validate volume value.
        
        Args:
            volume: Volume to validate
            allow_zero: Whether zero volume is acceptable
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If volume is invalid
        """
        if volume is None:
            raise ValidationError("Volume cannot be None")
        
        if not isinstance(volume, int):
            raise ValidationError(f"Volume must be integer, got {type(volume)}")
        
        if volume < 0:
            raise ValidationError(f"Volume cannot be negative: {volume}")
        
        if volume == 0 and not allow_zero:
            raise ValidationError("Volume cannot be zero")
        
        if volume > cls.MAX_VOLUME:
            raise ValidationError(
                f"Volume too high: {volume} (max: {cls.MAX_VOLUME})"
            )
        
        return True
    
    @classmethod
    def validate_ohlc(
        cls,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> bool:
        """
        Validate OHLC price relationship.
        
        Args:
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If OHLC relationship is invalid
        """
        # Validate individual prices
        cls.validate_price(open_price, "open")
        cls.validate_price(high, "high")
        cls.validate_price(low, "low")
        cls.validate_price(close, "close")
        
        # Check relationships
        if high < low:
            raise ValidationError(
                f"High ({high}) cannot be less than low ({low})"
            )
        
        if high < open_price or high < close:
            raise ValidationError(
                f"High ({high}) must be >= open ({open_price}) and close ({close})"
            )
        
        if low > open_price or low > close:
            raise ValidationError(
                f"Low ({low}) must be <= open ({open_price}) and close ({close})"
            )
        
        # Check for suspicious spreads (> 50%)
        spread_pct = ((high - low) / low) * 100 if low > 0 else 0
        if spread_pct > 50:
            logger.warning(
                f"Suspicious OHLC spread: {spread_pct:.1f}% "
                f"(H:{high}, L:{low}, O:{open_price}, C:{close})"
            )
        
        return True
    
    @classmethod
    def validate_quote(cls, quote_data: Dict[str, Any]) -> bool:
        """
        Validate a complete quote data dictionary.
        
        Args:
            quote_data: Quote data to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If quote data is invalid
        """
        required_fields = ["symbol", "price", "timestamp"]
        
        # Check required fields
        for field in required_fields:
            if field not in quote_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate symbol
        cls.validate_symbol(quote_data["symbol"])
        
        # Validate price
        cls.validate_price(quote_data["price"])
        
        # Validate timestamp
        if not isinstance(quote_data["timestamp"], datetime):
            raise ValidationError("Timestamp must be a datetime object")
        
        # Validate optional bid/ask
        if "bid" in quote_data and quote_data["bid"] is not None:
            cls.validate_price(quote_data["bid"], "bid")
        
        if "ask" in quote_data and quote_data["ask"] is not None:
            cls.validate_price(quote_data["ask"], "ask")
        
        # Check bid/ask relationship
        if (
            "bid" in quote_data
            and "ask" in quote_data
            and quote_data["bid"] is not None
            and quote_data["ask"] is not None
        ):
            if quote_data["bid"] > quote_data["ask"]:
                raise ValidationError(
                    f"Bid ({quote_data['bid']}) cannot be greater than "
                    f"ask ({quote_data['ask']})"
                )
        
        # Validate volume if present
        if "volume" in quote_data and quote_data["volume"] is not None:
            cls.validate_volume(quote_data["volume"])
        
        return True
    
    @classmethod
    def validate_historical_bar(cls, bar_data: Dict[str, Any]) -> bool:
        """
        Validate a historical price bar.
        
        Args:
            bar_data: Bar data to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If bar data is invalid
        """
        required_fields = ["symbol", "date", "open", "high", "low", "close", "volume"]
        
        # Check required fields
        for field in required_fields:
            if field not in bar_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate symbol
        cls.validate_symbol(bar_data["symbol"])
        
        # Validate OHLC
        cls.validate_ohlc(
            bar_data["open"],
            bar_data["high"],
            bar_data["low"],
            bar_data["close"],
        )
        
        # Validate volume
        cls.validate_volume(bar_data["volume"])
        
        # Validate date
        if not isinstance(bar_data["date"], datetime):
            raise ValidationError("Date must be a datetime object")
        
        return True
    
    @classmethod
    def sanitize_symbol(cls, symbol: str) -> str:
        """
        Sanitize and normalize a symbol string.
        
        Args:
            symbol: Raw symbol string
        
        Returns:
            Cleaned symbol string
        """
        if not symbol:
            raise ValidationError("Symbol cannot be empty")
        
        # Remove whitespace and convert to uppercase
        symbol = symbol.strip().upper()
        
        # Remove any invalid characters
        symbol = re.sub(r'[^A-Z\.]', '', symbol)
        
        return symbol
