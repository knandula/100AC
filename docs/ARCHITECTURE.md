# 100AC System Architecture & Development Guide
**Critical Reference for Continuing Development**

Last Updated: 2026-01-15 (Post Agent #2)

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Patterns](#architecture-patterns)
4. [Development Workflow](#development-workflow)
5. [Database Schema](#database-schema)
6. [Common Patterns & Solutions](#common-patterns--solutions)
7. [Testing Strategy](#testing-strategy)
8. [Lessons Learned](#lessons-learned)
9. [How to Add New Agents](#how-to-add-new-agents)

---

## System Overview

### Project Goal
Build a **100-agent autonomous collaborative financial analysis system** that can replace a team of 100 human financial analysts. The system uses message-based communication, async processing, and SQLite persistence.

### Current Status (Checkpoint)
- **Phase 1**: ✅ Complete (8/8 tests) - Foundation infrastructure
- **Phase 2**: 🔄 In Progress (2/12 agents complete, 15/15 tests)
  - ✅ Agent #1: Market Data Fetcher
  - ✅ Agent #2: Historical Data Loader
  - ⏳ Agent #3: Economic Calendar Monitor (next)

### Critical Constraint
> "This if done wrong will cost me 1Billion dollar loss, so please be careful in your execution"
> 
> **Approach**: Test-driven, step-by-step validation, zero shortcuts

---

## Technology Stack

### Core Framework
```
Python 3.13.5
├── asyncio - Async/await for non-blocking I/O
├── pydantic 2.12.1 - Data validation and serialization
└── loguru 0.7.3 - Structured logging
```

### Database Layer
```
SQLAlchemy 2.0.45 (async ORM)
├── aiosqlite 0.22.1 - Async SQLite driver
├── greenlet 3.3.0 - Required for SQLAlchemy async
└── SQLite 3.x - File-based database (100ac.db)
```

### Data Sources
```
Market Data:
├── yfinance 1.0 - Yahoo Finance API (free, real-time)
├── pandas 2.3.3 - Time series data manipulation
└── numpy 2.4.1 - Numerical operations
```

### Testing
```
pytest 9.0.2
├── pytest-asyncio 1.3.0 - Async test support
└── pytest-cov 7.0.0 - Coverage reporting
```

### Why These Choices?

**SQLite over PostgreSQL:**
- ✅ Zero setup for development
- ✅ In-memory databases for fast tests
- ✅ Single file deployment
- 🔄 Migration path: SQLAlchemy makes PostgreSQL swap trivial

**yfinance over Alpha Vantage:**
- ✅ No API key required
- ✅ No rate limits (free tier)
- ✅ Real-time data (~15min delay acceptable for testing)
- ❌ Occasional API instability (need retry logic)

**Async/Await Architecture:**
- ✅ 100 agents need non-blocking I/O
- ✅ Handle multiple API calls concurrently
- ✅ Database operations don't block message bus
- 📝 Pattern: Always use `async def` and `await` for I/O

---

## Architecture Patterns

### 1. Message-Based Communication

All agents communicate via a central message bus (pub/sub pattern):

```python
# Message structure (Pydantic model)
Message(
    from_agent="market_data_fetcher",
    to_agent="risk_analyzer",
    message_type=MessageType.REQUEST,  # REQUEST, RESPONSE, EVENT
    topic="fetch_price",  # Capability name
    data={"symbol": "AAPL"}  # Payload
)
```

**Key Points:**
- Messages are immutable (Pydantic frozen)
- Topics map to agent capabilities
- Async publish/subscribe prevents blocking
- No direct agent-to-agent calls

### 2. Agent Base Class Pattern

All agents inherit from `BaseAgent`:

```python
class MyAgent(BaseAgent):
    async def get_metadata(self) -> AgentMetadata:
        """Return agent info and capabilities"""
        return AgentMetadata(
            agent_id=self.agent_id,
            name="My Agent",
            category=AgentCategory.DATA_COLLECTION,
            capabilities=[
                AgentCapability(
                    name="my_capability",
                    description="What it does",
                    input_schema={"symbol": "str"},
                    output_schema={"price": "float"}
                )
            ]
        )
    
    async def process_request(self, message: Message) -> Dict:
        """Entry point for all requests"""
        return await self.process_message(message)
    
    async def process_message(self, message: Message) -> Dict:
        """Route to capability handlers"""
        topic = message.topic
        if topic == "my_capability":
            return await self._handle_my_capability(message.data)
        return {"success": False, "error": "Unknown capability"}
```

**Critical Pattern:**
- `get_metadata()` - Returns capabilities (abstract method)
- `process_request()` - Entry point (abstract method)
- `process_message()` - Routes to handlers based on topic
- Handler methods prefixed with `_handle_*`

### 3. Database Session Management

**ALWAYS use async context managers:**

```python
async with self.db.get_session() as session:
    # Query
    stmt = select(Model).where(Model.field == value)
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    
    # Insert/Update
    session.add(new_obj)
    await session.commit()
```

**Common Mistake:**
```python
# ❌ WRONG - Missing await
session.commit()

# ✅ CORRECT
await session.commit()
```

### 4. Upsert Pattern (Critical!)

When inserting data that might already exist:

```python
# Query first
stmt = select(Model).where(
    Model.key1 == value1,
    Model.key2 == value2
)
result = await session.execute(stmt)
existing = result.scalar_one_or_none()

if existing:
    # Update existing record
    for key, value in new_data.items():
        setattr(existing, key, value)
else:
    # Insert new record
    new_obj = Model(**new_data)
    session.add(new_obj)

await session.commit()
```

**Why Not `merge()`?**
- `merge()` requires primary key, but our UNIQUE constraints are on other columns
- Tests reuse in-memory database causing UNIQUE violations
- Query-first pattern is explicit and reliable

### 5. Cache Pattern

All agents use `AgentCache` table for TTL-based caching:

```python
# Save to cache
async def _save_to_cache(self, cache_key: str, data: List[Dict]):
    async with self.db.get_session() as session:
        # Delete old entry (if exists)
        old_entry = await session.execute(
            select(AgentCache).where(
                AgentCache.agent_id == self.agent_id,
                AgentCache.cache_key == cache_key
            )
        ).scalar_one_or_none()
        
        if old_entry:
            await session.delete(old_entry)
            await session.commit()  # Commit delete first!
        
        # Insert new entry with JSON serialization
        def json_serial(obj):
            if isinstance(obj, datetime):
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

# Get from cache
async def _get_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
    async with self.db.get_session() as session:
        result = await session.execute(
            select(AgentCache).where(
                AgentCache.agent_id == self.agent_id,
                AgentCache.cache_key == cache_key,
                AgentCache.expires_at > datetime.utcnow()
            )
        )
        cache_entry = result.scalar_one_or_none()
        if cache_entry:
            return json.loads(cache_entry.cache_value)
        return None
```

**Critical Details:**
- Commit delete before insert (prevents UNIQUE constraint errors)
- Use custom JSON encoder for datetime objects
- Cache key format: `{identifier}_{param1}_{param2}`
- TTL varies by agent (real-time: 60s, historical: 1 day)

---

## Development Workflow

### Step-by-Step Agent Development

**1. Design Phase (10 min)**
- Read spec for agent requirements
- Define capabilities (4-6 typical)
- Identify data source API
- Plan database models needed

**2. Implementation (30-60 min)**
- Create `agents/{category}/{agent_name}.py`
- Inherit from `BaseAgent`
- Implement `get_metadata()` and `process_request()`
- Add capability handlers (`_handle_*` methods)
- Add validation, caching, error handling

**3. Testing (20-40 min)**
- Create `tests/test_{agent_name}.py`
- Test metadata structure
- Test each capability (valid/invalid inputs)
- Test batch operations (if applicable)
- Test caching behavior
- Test error handling

**4. Validation (5 min)**
- Run `pytest tests/test_{agent_name}.py -v`
- All tests must pass before moving on
- Fix any failures immediately
- Document any bugs/solutions

**5. Documentation (10 min)**
- Update `PHASE2_PROGRESS.md` with results
- Note any design decisions
- Record performance metrics

### Git Workflow

```bash
# After each agent completion
git add .
git commit -m "feat: Agent #{N} - {Name} complete (X/X tests passing)"
git push
```

---

## Database Schema

### Current Models (Phase 1-2)

#### MarketPrice
Real-time market quotes (Agent #1)
```sql
CREATE TABLE market_prices (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price FLOAT NOT NULL,
    bid FLOAT,
    ask FLOAT,
    volume INTEGER,
    market_cap FLOAT,
    timestamp DATETIME NOT NULL,
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
);
```

#### HistoricalPrice
OHLCV bars for backtesting (Agent #2)
```sql
CREATE TABLE historical_prices (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATETIME NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume INTEGER NOT NULL,
    adj_close FLOAT,
    interval VARCHAR(10) DEFAULT '1d',
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date, interval)
);
```

#### AgentCache
Generic TTL-based cache (all agents)
```sql
CREATE TABLE agent_cache (
    id INTEGER PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    cache_key VARCHAR(255) NOT NULL,
    cache_value TEXT NOT NULL,  -- JSON serialized
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    extra_info TEXT,
    UNIQUE(agent_id, cache_key)
);
```

#### DataQualityLog
Track validation issues (all agents)
```sql
CREATE TABLE data_quality_log (
    id INTEGER PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    issue_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Adding New Models

1. Add to `shared/database/models.py`:
```python
class NewModel(Base):
    __tablename__ = "new_table"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
```

2. Database auto-creates tables on initialization (no migrations needed in dev)

---

## Common Patterns & Solutions

### Problem 1: DateTime Handling

**Issue:** Pandas Timestamp ≠ Python datetime ≠ JSON serializable

**Solution:**
```python
# For SQLite storage (needs Python datetime)
date_for_db = pandas_timestamp.to_pydatetime()

# For JSON caching
def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

cached_data = json.dumps(data, default=json_serial)

# For test comparisons (datetime to string)
date_str = datetime_obj.strftime("%Y-%m-%d")
```

### Problem 2: Validation Error Handling

**Issue:** Validators raise exceptions, not return booleans

**Wrong:**
```python
is_valid, error = self.validator.validate_symbol(symbol)
if not is_valid:
    return {"error": error}
```

**Correct:**
```python
try:
    self.validator.validate_symbol(symbol)
except ValidationError as e:
    return {"success": False, "error": str(e)}
```

### Problem 3: Message Model Fields

**Issue:** Message model uses specific field names

**Wrong:**
```python
Message(
    sender_id="agent1",
    receiver_id="agent2",
    payload={"data": "value"},
    metadata={"type": "request"}
)
```

**Correct:**
```python
Message(
    from_agent="agent1",
    to_agent="agent2",
    message_type=MessageType.REQUEST,
    topic="capability_name",
    data={"data": "value"}
)
```

### Problem 4: AgentCache Field Names

**Issue:** AgentCache uses `cache_value` not `data`

**Wrong:**
```python
AgentCache(
    agent_id="agent1",
    cache_key="key",
    data=json.dumps(obj)  # ❌ No 'data' field
)
```

**Correct:**
```python
AgentCache(
    agent_id="agent1",
    cache_key="key",
    cache_value=json.dumps(obj, default=json_serial)
)
```

### Problem 5: DataQualityLog Fields

**Issue:** Uses `agent_id` and `description`, not `source` and `details`

**Correct:**
```python
DataQualityLog(
    agent_id="market_data_fetcher",  # not 'source'
    data_type="market_price",
    issue_type="validation_error",
    description="Price validation failed",  # not 'details'
    severity="high"
)
```

---

## Testing Strategy

### Test File Structure

```python
import pytest
from shared.message_bus import init_message_bus
from shared.database.connection import init_database
from agents.{category}.{agent_name} import {AgentClass}

@pytest.mark.asyncio
async def test_agent_metadata():
    """Verify agent metadata and capabilities."""
    agent = {AgentClass}()
    metadata = await agent.get_metadata()
    
    assert metadata.agent_id == "expected_id"
    assert len(metadata.capabilities) == 4  # Expected count
    assert metadata.category == AgentCategory.DATA_COLLECTION

@pytest.mark.asyncio
async def test_capability_valid_input():
    """Test capability with valid inputs."""
    # Initialize dependencies
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = {AgentClass}()
    await agent.initialize()
    await agent.start()
    
    # Create message
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="capability_name",
        data={"param": "value"}
    )
    
    # Process and assert
    result = await agent.process_request(message)
    assert result["success"] is True
    assert "expected_field" in result
    
    # Cleanup
    await agent.stop()
    await bus.stop()
    await db.close()
```

### Test Coverage Requirements

Each agent needs tests for:
1. ✅ Metadata structure (agent_id, capabilities, category)
2. ✅ Each capability with valid inputs
3. ✅ Each capability with invalid inputs
4. ✅ Batch operations (if applicable)
5. ✅ Caching behavior (if applicable)
6. ✅ Error handling
7. ✅ Data validation

### Running Tests

```bash
# Single agent
pytest tests/test_agent_name.py -v

# All Phase 2 tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=agents --cov=shared -v

# Specific test
pytest tests/test_agent_name.py::test_function_name -v
```

---

## Lessons Learned (Bugs Fixed)

### Bug #1: Missing greenlet Dependency
**Error:** `ImportError: greenlet required for async SQLAlchemy`  
**Fix:** Added `greenlet>=3.3.0` to requirements.txt  
**Root Cause:** SQLAlchemy 2.0 async requires greenlet but doesn't auto-install it

### Bug #2: DateTime Storage in SQLite
**Error:** `SQLite DateTime type only accepts Python datetime objects`  
**Fix:** Convert Pandas Timestamp: `date.to_pydatetime()`  
**Root Cause:** yfinance returns Pandas Timestamp, SQLite needs Python datetime

### Bug #3: Cache JSON Serialization
**Error:** `TypeError: Object of type datetime is not JSON serializable`  
**Fix:** Custom JSON encoder with `obj.isoformat()` for datetime  
**Root Cause:** Cache stores JSON text, datetime objects need conversion

### Bug #4: UNIQUE Constraint Violations in Tests
**Error:** `IntegrityError: UNIQUE constraint failed`  
**Fix:** Upsert pattern (query first, then update or insert)  
**Why merge() failed:** UNIQUE constraint on non-primary-key columns

### Bug #5: Cache Not Persisting
**Error:** `IntegrityError: UNIQUE constraint failed` on cache insert  
**Fix:** Commit delete transaction before inserting new cache entry  
**Root Cause:** Trying to insert while old entry still exists in transaction

### Bug #6: Import Path Issues
**Error:** `ModuleNotFoundError: No module named 'shared.base_agent'`  
**Fix:** Correct import: `from agents.base_agent import BaseAgent`  
**Plus:** Add `sys.path.insert(0, os.path.dirname(__file__))` in tests

### Bug #7: Validator Return Values
**Error:** `TypeError: cannot unpack non-iterable bool object`  
**Fix:** Validators raise exceptions, use try/except not unpacking  
**Pattern:** All `DataValidator` methods raise `ValidationError` on failure

---

## How to Add New Agents

### Template Checklist

- [ ] Copy template: `cp agents/data/market_data_fetcher.py agents/{category}/{new_agent}.py`
- [ ] Update class name and agent_id
- [ ] Define 4-6 capabilities in `get_metadata()`
- [ ] Implement capability handlers (`_handle_*`)
- [ ] Add data validation
- [ ] Add caching (if data doesn't change rapidly)
- [ ] Add error handling and logging
- [ ] Create test file: `tests/test_{new_agent}.py`
- [ ] Write 6-8 tests (metadata + capabilities + edge cases)
- [ ] Run tests until 100% passing
- [ ] Update `PHASE2_PROGRESS.md`
- [ ] Commit and push

### Agent Template

```python
"""
Agent #{N}: {Agent Name}
Category: {DATA_COLLECTION | ANALYSIS | etc.}
Purpose: {One-line description}
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from loguru import logger
from sqlalchemy import select, and_

from agents.base_agent import BaseAgent
from shared.data_models import (
    AgentMetadata, AgentCapability, AgentCategory, Message
)
from shared.database.models import AgentCache, DataQualityLog
from shared.validation import DataValidator

class NewAgent(BaseAgent):
    """Agent #{N}: {Description}"""
    
    def __init__(self):
        super().__init__()
        self.agent_id = "new_agent"
        self.validator = DataValidator()
        self.cache_ttl = timedelta(seconds=60)  # Adjust as needed
    
    async def get_metadata(self) -> AgentMetadata:
        """Return agent metadata and capabilities."""
        return AgentMetadata(
            agent_id=self.agent_id,
            name="New Agent",
            category=AgentCategory.DATA_COLLECTION,
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="capability_1",
                    description="What it does",
                    input_schema={"param": "type"},
                    output_schema={"result": "type"}
                ),
                # Add 3-5 more capabilities
            ]
        )
    
    async def process_request(self, message: Message) -> Dict:
        """Process incoming requests."""
        return await self.process_message(message)
    
    async def process_message(self, message: Message) -> Dict:
        """Route messages to capability handlers."""
        topic = message.topic
        
        if topic == "capability_1":
            return await self._handle_capability_1(message.data)
        
        return {
            "success": False,
            "error": f"Unknown capability: {topic}"
        }
    
    async def _handle_capability_1(self, params: Dict) -> Dict:
        """Handle capability_1 requests."""
        try:
            # 1. Validate inputs
            # 2. Check cache
            # 3. Fetch data from source
            # 4. Validate outputs
            # 5. Store in database
            # 6. Cache results
            # 7. Return response
            
            return {
                "success": True,
                "data": [],
                "cached": False
            }
        except Exception as e:
            logger.error(f"Error in capability_1: {e}")
            return {"success": False, "error": str(e)}
```

---

## Quick Reference Commands

```bash
# Activate virtual environment
cd /Users/knandula/work/roborev/100AC
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific agent tests
pytest tests/test_market_data_fetcher.py -v
pytest tests/test_historical_data_loader.py -v

# Check database
sqlite3 100ac.db
> .tables
> SELECT * FROM market_prices LIMIT 5;
> .quit

# Clean cache (if needed)
rm 100ac.db
```

---

## Next Steps (Agent #3 and Beyond)

See `100AC_spec.md` for full agent list.

**Priority Queue:**
1. Agent #3: Economic Calendar Monitor
2. Agent #4: News Sentiment Analyzer  
3. Agent #5: Order Book Tracker
4. Agent #6: Options Chain Loader

**Development Pace:**
- 1-2 agents per day (with full testing)
- Week 1: Agents 1-12 (Data Collection)
- Week 2: Agents 13-25 (Technical Analysis)

---

## Emergency Recovery

If the project state is unclear:

```bash
# Check Phase 1
pytest tests/test_*.py -k "phase1" -v

# Check Phase 2 agents
pytest tests/test_market_data_fetcher.py tests/test_historical_data_loader.py -v

# Review progress
cat docs/PHASE2_PROGRESS.md

# Check database state
sqlite3 100ac.db ".schema"
```

Expected: Phase 1 (8 tests) + Agent #1 (7 tests) + Agent #2 (8 tests) = 23 total tests passing

---

**Document Version:** 1.0  
**Last Checkpoint:** Agent #2 Complete (15/15 tests passing)  
**Next Milestone:** Agent #3 Implementation
