import asyncio,sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome')
        pg=await b.new_page(viewport={'width':1600,'height':1000})
        for n in sys.argv[1:]:
            await pg.goto(f'file:///workspace/autoexpert/build/screens/{n}.html');await pg.wait_for_timeout(600)
            fr=await pg.query_selector_all('.frame')
            for i,f in enumerate(fr):
                await f.screenshot(path=f'/workspace/autoexpert/build/shots/{n}-{i+1:02d}.png')
        await b.close()
asyncio.run(main())
