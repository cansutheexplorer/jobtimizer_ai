# test_connection.py
import asyncio
from services.database import db_service


async def test_connection():
    """Test database connection and ESCO data"""
    try:
        await db_service.connect()

        # Count total occupations
        count = await db_service.occupations_col.count_documents({})
        print(f"✅ Connected! Found {count} ESCO occupations")

        # Get a few sample occupations
        samples = await db_service.get_random_occupations(5)
        print("\n📋 Sample occupations:")
        for i, occ in enumerate(samples, 1):
            print(f"  {i}. {occ.get('name', 'Unknown')}")
            if 'alternative_labels' in occ and occ['alternative_labels']:
                print(f"     Labels: {', '.join(occ['alternative_labels'][:3])}")

        # Test search
        print("\n🔍 Testing search for 'software':")
        results = await db_service.search_occupations_by_text("software", 3)
        for i, occ in enumerate(results, 1):
            print(f"  {i}. {occ.get('name', 'Unknown')}")

        await db_service.disconnect()
        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_connection())