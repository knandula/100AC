"""Check available data for Gold/Silver ETFs."""
import asyncio
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice
from sqlalchemy import select, func

async def check_symbols():
    db = get_database()
    await db.initialize()
    
    symbols = ['GLD', 'SLV', 'GOLDBEES', 'SILVERBEES']
    
    print("=" * 60)
    print("Gold/Silver ETF Data Availability")
    print("=" * 60)
    
    async with db.get_session() as session:
        for symbol in symbols:
            count_stmt = select(func.count()).select_from(HistoricalPrice).where(
                HistoricalPrice.symbol == symbol
            )
            result = await session.execute(count_stmt)
            count = result.scalar()
            
            if count > 0:
                min_stmt = select(func.min(HistoricalPrice.date)).where(
                    HistoricalPrice.symbol == symbol
                )
                max_stmt = select(func.max(HistoricalPrice.date)).where(
                    HistoricalPrice.symbol == symbol
                )
                
                min_result = await session.execute(min_stmt)
                max_result = await session.execute(max_stmt)
                
                min_date = min_result.scalar()
                max_date = max_result.scalar()
                
                print(f"{symbol:12} {count:4} records  ({min_date} to {max_date})")
            else:
                print(f"{symbol:12} No data available")
    
    print("=" * 60)
    await db.close()

if __name__ == '__main__':
    asyncio.run(check_symbols())
