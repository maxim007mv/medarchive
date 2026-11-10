import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome')
        pg=await b.new_page()
        await pg.goto('file:///workspace/autoexpert/build/screens/brandbook.html');await pg.wait_for_timeout(1500)
        await pg.evaluate('document.fonts.ready')
        ov=await pg.evaluate('''[...document.querySelectorAll('.pg')].map((p,i)=>{const pb=p.querySelector('.pb');const r=p.getBoundingClientRect();let bad=[];p.querySelectorAll('.pb *').forEach(e=>{const q=e.getBoundingClientRect();if(q.width&&(q.bottom>r.bottom-46||q.right>r.right-20))bad.push(e.className||e.tagName)});return bad.length?[i+1,bad.slice(0,4)]:null}).filter(Boolean)''')
        print('overflow',ov)
        await pg.pdf(path='/workspace/autoexpert/pack/MedArchive/02_design/brandbook.pdf',width='297mm',height='210mm',print_background=True,prefer_css_page_size=True)
        await b.close()
asyncio.run(main())
