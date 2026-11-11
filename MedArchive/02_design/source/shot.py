"""Screenshot every .frame of a board: `python shot.py desktop-light mobile-light:1`.

`board:N` keeps only frame N (1-based), e.g. to refresh one screen without the rest.
"""
import asyncio,sys
from pathlib import Path
from playwright.async_api import async_playwright
HERE = Path(__file__).resolve().parent
SCREENS = HERE.parent / 'screens'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':1600,'height':1000})
        for arg in sys.argv[1:]:
            n,_,only=arg.partition(':')
            await pg.goto((HERE/f'{n}.html').as_uri());await pg.wait_for_timeout(600)
            fr=await pg.query_selector_all('.frame')
            for i,f in enumerate(fr):
                if only and i+1!=int(only): continue
                await f.screenshot(path=str(SCREENS/f'{n}-{i+1:02d}.png'))
        await b.close()
asyncio.run(main())
