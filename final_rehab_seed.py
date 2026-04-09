import asyncio
from scripts.seed_all import STRATEGIES
from scripts.seed_data import seed_data

async def main():
    test_dir = ["synthetic_data_v2/project_docs"]
    print('REHAB: Starting 4-pass strategic seeding pass...')
    
    for strategy in ["semantic"]:
        print(f'REHAB: PASS -> {strategy}')
        # We catch exceptions for individual passes to ensure the loop finishes
        try:
            await seed_data(data_dirs=test_dir, chunker=strategy, dry_run=False)
        except Exception as e:
            print(f'REHAB: FAILED {strategy}: {str(e)}')
    
    print('REHAB: Strategic seeding pass complete.')

if __name__ == "__main__":
    asyncio.run(main())
