import json, io, contextlib
from pathlib import Path
with contextlib.redirect_stdout(io.StringIO()):
    import gen
from gen import I, P, tag, dd, F, typeradio, filebox, modal, table, toolbar, mcard, DOCS
HERE = Path(__file__).resolve().parent
pal = json.loads((HERE / 'palette.json').read_text(encoding='utf-8'))
L, Dk = pal['light'], pal['dark']

def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
    la,lb=sorted([lum(a),lum(b)],reverse=True); return (la+0.05)/(lb+0.05)

PAGES=[]
def page(title, body, sec='', cls=''):
    PAGES.append((title, sec, body, cls))

def ok(html, note, w=''):
    return f'<div class="cmp ok"{w}><div class="cmp-h">{I("check","ic ic16")}Правильно</div><div class="cmp-b">{html}</div><p>{note}</p></div>'
def no(html, note, w=''):
    return f'<div class="cmp no"{w}><div class="cmp-h">{I("x","ic ic16")}Неправильно</div><div class="cmp-b">{html}</div><p>{note}</p></div>'
def pair(a,b): return f'<div class="pair">{a}{b}</div>'
def demo(html, theme='light', style=''):
    return f'<div class="demo" data-theme="{theme}" style="{style}">{html}</div>'

# ---------- 1 cover
page('', f'''<div class="cover"><div class="cv-logo"><i>{I("archive")}</i>Медархив</div>
<div><h1 class="cv-t">Брендбук и дизайн-система</h1><p class="cv-s">Цвет, типографика Medeo, сетка, компоненты и их состояния, движение, AI-генерация, правила «правильно / неправильно» и все экраны продукта в светлой и тёмной теме.</p></div>
<div class="cv-meta"><span>Версия 1.0</span><span>10.11.2026</span><span>Шрифт Medeo Sans и Medeo Mono, OFL 1.1</span></div>
<div class="cv-sw">{''.join(f'<i style="background:{c}"></i>' for c in ['#171717','#F4F4F5','#FFFFFF','#0F766E','#1D4ED8','#6D28D9','#92400E','#B42318','#067647'])}</div></div>''', cls='cv')

# ---------- 3 principles
page('Характер продукта', f'''<div class="grid3">
<div class="pr"><b>01</b><h3>Спокойствие</h3><p>Медицинские документы приносят тревогу. Интерфейс нейтрально-серый, без декора, один акцент бирюзовый. Красный только там, где действие необратимо.</p></div>
<div class="pr"><b>02</b><h3>Точность</h3><p>Даты набраны моноширинным Medeo Mono, у каждой цифры подпись. Дата документа и дата загрузки всегда раздельно и не путаются.</p></div>
<div class="pr"><b>03</b><h3>Контроль у человека</h3><p>Ничего не пропадает молча: документ без даты помечен, применённые фильтры видны, AI только подсказывает и ничего не сохраняет сам.</p></div>
<div class="pr"><b>04</b><h3>Одно главное действие</h3><p>На каждом экране одна чёрная кнопка. Всё остальное второстепенное, текстовое или скрыто в меню строки.</p></div>
<div class="pr"><b>05</b><h3>Доступность по умолчанию</h3><p>Все пары цветов проверены по WCAG 2.2 AA, цели нажатия от 40 px, вся строка списка кликабельна, движение уважает системную настройку.</p></div>
<div class="pr"><b>06</b><h3>Две равноправные темы</h3><p>Светлая по умолчанию, тёмная по системной настройке и переключателю. Глубже значит темнее, выше значит светлее, в обеих темах.</p></div></div>''', '0')

# ---------- palette pages
ROLES=[('bg','Фон страницы'),('surface','Карточка, таблица'),('sunken','Вдавленное, disabled'),('raised','Модалка, лист'),('border','Разделитель'),('control','Граница поля'),
('text','Основной текст'),('text2','Вторичный текст'),('text3','Подсказки'),('primary','Главная кнопка'),('onPrimary','Текст на главной'),('accent','Акцент, фокус'),('accentSoft','Мягкий акцент'),
('analysis','Тип «Анализ»'),('analysisBg','Фон метки'),('conclusion','Тип «Заключение»'),('conclusionBg','Фон метки'),('other','Тип «Другое»'),('otherBg','Фон метки'),
('warn','Предупреждение'),('warnBg','Фон'),('danger','Опасность'),('dangerBg','Фон'),('success','Успех'),('successBg','Фон')]
def swatches(p, theme):
    bg=p['bg']; surf=p['surface']; out=''
    for k,name in ROLES:
        c=p[k]; ref = surf if k in ('bg','sunken','raised','border','surface','accentSoft','analysisBg','conclusionBg','otherBg','warnBg','dangerBg','successBg') else bg
        if k in ('bg','surface','raised'): txt=f'текст {cr(p["text"],c):.2f}:1'
        elif k=='onPrimary': txt=f'на primary {cr(c,p["primary"]):.2f}:1'
        elif k.endswith('Bg') or k in('accentSoft','sunken','border'): txt=f'vs surface {cr(c,surf):.2f}:1'
        else: txt=f'на фоне {cr(c,bg):.2f}:1 · на карточке {cr(c,surf):.2f}:1'
        out+=f'<div class="sw"><i style="background:{c}"></i><div><b>{name}</b><span class="mono">--{k}</span><span class="mono">{c}</span><em>{txt}</em></div></div>'
    return f'<div class="sws">{out}</div>'
page('Палитра · светлая тема', '<p class="lead">Цвет задаётся семантическими ролями (S11): компонент берёт роль, а не hex. Одни и те же роли в обеих темах. Контраст посчитан по формуле WCAG 2.2 (S9) и не округляется.</p>'+swatches(L,'light'), '1')
page('Палитра · тёмная тема', '<p class="lead">Фон <span class="mono">#0A0A0A</span>, карточки <span class="mono">#171717</span>, модалки <span class="mono">#1F1F22</span>: выше значит светлее. Насыщенные цвета светлой темы осветлены, чтобы сохранить 4,5:1 на тёмном.</p>'+swatches(Dk,'dark'), '1', cls='dk')

rows=pal['rows']
def ctab(rs):
    return '<table class="t"><tr><th>Тема</th><th>Пара</th><th>Текст</th><th>Фон</th><th>Контраст</th><th>Порог</th><th></th></tr>'+''.join(
        f'<tr><td>{a}</td><td>{b}</td><td><span class="chipc" style="background:{c};"></span><span class="mono">{c}</span></td><td><span class="chipc" style="background:{d}"></span><span class="mono">{d}</span></td><td class="mono">{e:.2f}:1</td><td class="mono">{f"{f}:1" if f else "—"}</td><td class="pass">{verdict(e,f)}</td></tr>' for a,b,c,d,e,f in rs)+'</table>'
def verdict(e,f):
    if not f: return 'не треб.'
    return 'AA' if e>=f else 'нет'
required=[r for r in rows if r[5]]
for theme in ('светлая','тёмная'):
    rs=[r for r in rows if r[0]==theme]; h=(len(rs)+1)//2
    page(f'Проверка контраста · {theme}', f'<p class="lead">Все {len(required)} рабочих пар двух тем проходят WCAG 2.2 AA: текст 4,5:1, границы элементов управления и фокус 3:1 (SC 1.4.3, 1.4.11). Неактивные элементы порога не имеют и показаны справочно. Расчёт: <span class="mono">source/contrast.py</span> из <span class="mono">tokens.json</span>.</p><div class="two">{ctab(rs[:h])}{ctab(rs[h:])}</div>', '1')

page('Цвет · правильно и неправильно', '<div class="pairs">'+
 pair(ok(demo('<div class="row g8"><span class="btn p">Добавить PDF</span><span class="btn s">Экспорт</span></div>'),'Одна главная кнопка чёрная, вторая белая с рамкой.'),
      no(demo('<div class="row g8"><span class="btn" style="background:#0F766E;color:#fff">Добавить PDF</span><span class="btn" style="background:#1D4ED8;color:#fff">Экспорт</span></div>'),'Две цветные кнопки спорят, акцент перестаёт что-то значить.'))+
 pair(ok(demo('<div style="background:#F4F4F5;padding:12px;border-radius:12px"><div style="background:#fff;border-radius:10px;padding:12px">Карточка на сером фоне</div></div>'),'Нейтральный серый фон, карточка отделяется тоном без линий.'),
      no(demo('<div style="background:#F3EBDD;padding:12px;border-radius:12px"><div style="background:#FBF7F0;border-radius:10px;padding:12px;color:#7A6A55">Карточка на бежевом</div></div>'),'Бежевая подложка выглядит блёкло и снижает контраст текста.'))+
 pair(ok(demo(f'<div class="row g8">{tag("an","Анализ")}{tag("co","Заключение")}{tag("ot","Другое")}</div>'),'Тип документа цветом и словом: метка читается без цвета.'),
      no(demo('<div class="row g8"><i style="width:12px;height:12px;border-radius:50%;background:#1D4ED8"></i><i style="width:12px;height:12px;border-radius:50%;background:#6D28D9"></i><i style="width:12px;height:12px;border-radius:50%;background:#52525B"></i></div>'),'Только цветная точка: дальтоник не отличит тип (SC 1.4.1).'))+'</div>', '1')

# ---------- typography
GL='АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ<br>абвгдеёжзийклмнопрстуфхцчшщъыьэюя<br>ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz<br>0123456789 «» ( ) , . : ; ! ? № % + − = / @ ₽'
page('Типографика · Medeo', f'''<div class="two"><div><div class="spec">Аа</div><p class="lead">Medeo Sans: открытое семейство студии DNF с латиницей и кириллицей, версия 1.0.0 из локального пакета Medeo-v1.0.0 (ADR-043), лицензия SIL OFL 1.1 (S15). Основан на Geist, часть кириллицы и интервалов из Inter. Подключение: вариативные файлы в <span class="mono">apps/web/app/fonts</span>, <span class="mono">next/font/local</span>, <span class="mono">font-display: swap</span>.</p>
<div class="wts">{"".join(f'<div><span style="font-weight:{w}">Медархив</span><em class="mono">{w}</em></div>' for w in (400,500,600))}</div></div>
<div><p class="glyphs">{GL}</p><p class="glyphs mono">08.04.2026 · 21.05.2026 · 79 КБ<br>7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE</p><p class="cap">Medeo Mono: даты, размеры, ключ доступа. Табличные цифры: столбец дат стоит ровно.</p></div></div>''', '2')

SC=[('display',44,52,600,'-0.03em','Онбординг'),('h1',28,36,600,'-0.02em','Документы'),('h2',20,28,600,'-0.01em','Новый документ'),('h3',16,24,600,'0','Заметка'),('bodyL',17,26,400,'0','Ваши медицинские документы в одном месте'),('body',14,20,400,'0','PDF-файл и заметка хранятся в вашем архиве'),('label',13,18,500,'0','Дата документа'),('caption',12,16,400,'0','Дата загрузки запишется автоматически')]
page('Типографика · шкала', '<table class="t ts"><tr><th>Стиль</th><th>Размер / строка</th><th>Вес</th><th>Трекинг</th><th>Образец</th></tr>'+''.join(
 f'<tr><td class="mono">{n}</td><td class="mono">{s} / {l}</td><td class="mono">{w}</td><td class="mono">{t}</td><td><span style="font-size:{s}px;line-height:{l}px;font-weight:{w};letter-spacing:{t}">{x}</span></td></tr>' for n,s,l,w,t,x in SC)+
 '<tr><td class="mono">mono</td><td class="mono">13 / 20</td><td class="mono">400</td><td class="mono">0</td><td><span class="mono" style="font-size:13px">08.04.2026 · 79 КБ</span></td></tr></table>'+
 '<div class="pairs" style="margin-top:16px">'+pair(ok(demo('<div class="col mono" style="font-size:14px"><span>08.04.2026</span><span>21.05.2026</span><span>10.11.2026</span></div>'),'Даты моноширинным: цифры стоят в колонку.'),no(demo('<div class="col" style="font-size:14px;font-weight:300"><span>08.04.2026</span><span>21.05.2026</span><span>10.11.2026</span></div>'),'Тонкий 300 и пропорциональные цифры: текст теряет контраст, колонка прыгает.'))+'</div>', '2')

# ---------- spacing
grid=''.join(f'<div class="sp"><i style="width:{v}px;height:{v}px"></i><span class="mono">{v}</span></div>' for v in (2,4,6,8,10,12,16,24,32,48,64))
prox_ok=demo('<div class="col" style="gap:8px"><b style="font-size:20px;font-weight:600">Документы</b><span style="color:var(--text2)">6 документов · по дате документа</span></div><div style="height:24px"></div><div class="row g8"><span class="btn p sm">Добавить PDF</span><span class="btn s sm">Экспорт</span></div>')
prox_no=demo('<div class="col" style="gap:16px"><b style="font-size:20px;font-weight:600">Документы</b><span style="color:var(--text2)">6 документов · по дате документа</span><div class="row g8"><span class="btn p sm">Добавить PDF</span><span class="btn s sm">Экспорт</span></div></div>')
page('Сетка, отступы, закон близости', f'''<div class="two"><div><p class="lead">Сетка 8 px. Раскладка: 8, 16, 24, 32, 48, 64. Внутри компонентов: 2, 4, 6, 10, 12. Нечётных значений нет. Десктоп 1440: поля 32, шапка 64, панель 420. Мобильный 390: поля 16, шапка 56.</p><div class="sps">{grid}</div>
<table class="t"><tr><th>Связь</th><th>Отступ</th></tr><tr><td>Заголовок и поясняющий текст</td><td class="mono">8</td></tr><tr><td>Текст и кнопка под ним</td><td class="mono">16</td></tr><tr><td>Поля формы между собой</td><td class="mono">16</td></tr><tr><td>Смысловые блоки экрана</td><td class="mono">24 до 32</td></tr></table></div>
<div class="pairs">{ok(prox_ok,"Заголовок и подпись в 8, блок действий через 24: группы видны сразу.")}{no(prox_no,"Все отступы по 16: глаз не видит, что к чему относится.")}</div></div>''', '3')

# ---------- radii
rad=''.join(f'<div class="rd"><i style="border-radius:{r}px"></i><b class="mono">{r}</b><span>{n}</span></div>' for r,n in ((6,'Метка, kbd'),(10,'Поле, кнопка sm'),(12,'Кнопка 40 и 48'),(16,'Карточка, таблица'),(20,'Модалка, лист'),(999,'Чип фильтра')))
page('Скругления и тени', f'''<div class="rds">{rad}</div><p class="lead">Вложенность: внутренний радиус = внешний минус отступ (карточка 16, отступ 4, плашка 12). В светлой теме тени shadow-1 у карточек и shadow-3 у модалок; в тёмной тени не видны, вместо них разница поверхностей и рамка <span class="mono">#2E2E32</span>.</p>
<div class="pairs">{pair(ok(demo('<div style="background:var(--raised);border-radius:20px;padding:16px;box-shadow:var(--shadow3)"><div class="row g8"><span class="btn t sm">Отмена</span><span class="btn p sm">Сохранить</span></div></div>'),"Модалка 20, кнопки внутри 10 и 12."),no(demo('<div style="background:#fff;border-radius:6px;padding:16px;box-shadow:var(--shadow3)"><div class="row g8"><span class="btn t sm" style="border-radius:24px">Отмена</span><span class="btn p sm" style="border-radius:24px">Сохранить</span></div></div>'),"Внутреннее скругление больше внешнего выглядит чужеродно."))}
{pair(ok(demo('<div style="background:#1F1F22;border:1px solid #2E2E32;border-radius:16px;padding:16px;color:#F4F4F5">Модалка в тёмной теме</div>','dark'),"Тёмная модалка светлее фона + рамка 1 px."),no(demo('<div style="background:#0A0A0A;border-radius:16px;padding:16px;color:#F4F4F5;box-shadow:0 10px 30px #000">Модалка в тёмной теме</div>','dark'),"Чёрная тень на чёрном не видна, слой сливается с фоном."))}</div>''', '4')

# ---------- buttons
def brow(theme):
    vs=[('p','Главная','Добавить PDF'),('s','Второстепенная','Экспорт'),('t','Текстовая','Отмена'),('dg','Разрушительная','Удалить'),('dgt','Разр. текстовая','Удалить документ')]
    st=['default','hover','focus','loading','disabled']
    head='<tr><th></th>'+''.join(f'<th>{s}</th>' for s in st)+'</tr>'
    body=''
    for k,n,t in vs:
        cells=''
        for s in st:
            style=''; cl=f'btn {k}'; txt=t; icon=''
            if s=='hover':
                style={'p':'background:var(--primaryHover)','s':'background:var(--sunken)','t':'background:var(--sunken)','dg':'filter:brightness(.92)','dgt':'background:var(--dangerBg)'}[k]
            if s=='focus': cl+=' focus'
            if s=='loading': icon='<span class="spin"></span>'; txt='Сохраняем…' if k in('p','s') else t
            if s=='disabled': cl='btn dis'
            cells+=f'<td><span class="{cl}" style="{style}">{icon}{txt}</span></td>'
        body+=f'<tr><td class="bn">{n}</td>{cells}</tr>'
    return demo(f'<table class="bt">{head}{body}</table>',theme,'padding:12px')
page('Кнопки · варианты и состояния', f'''<div class="col g12">{brow("light")}{brow("dark")}</div>
<div class="row g24" style="margin-top:10px;align-items:flex-end">{demo('<div class="row g12" style="align-items:center"><span class="btn p sm">sm 32 · r10</span><span class="btn p">md 40 · r12</span><span class="btn p lg">lg 48 · r12</span></div>')}<p class="cap" style="max-width:420px">Главная <span class="mono">#171717</span> в светлой и <span class="mono">#F4F4F5</span> в тёмной теме, радиус 12. Hover 120 мс, нажатие без масштаба, фокус кольцо 2 px accent. Loading не меняет ширину. Disabled <span class="mono">#EBEBED</span> и всегда с причиной рядом.</p></div>''', '5')

page('Кнопки · правильно и неправильно', '<div class="pairs">'+
 pair(ok(demo('<div class="row g8"><span class="btn t">Отмена</span><span class="btn p">Сохранить в архив</span></div>'),'Одна главная кнопка на экран.'),no(demo('<div class="row g8"><span class="btn p">Сохранить</span><span class="btn p">Сохранить и добавить ещё</span></div>'),'Две главные кнопки: ни одной главной.'))+
 pair(ok(demo('<div class="col g8"><span class="btn dis" style="align-self:flex-start">Сохранить в архив</span><span class="cap" style="color:var(--text3)">Заполните название, чтобы сохранить</span></div>'),'Заблокированная кнопка с причиной рядом.'),no(demo('<div class="row g8"><span class="seg"><span class="on">Анализ</span><span>Другое</span></span><span class="btn" style="background:#fff;color:#71717A;border:1px solid #E4E4E7">Сохранить</span></div>'),'Disabled похожа на активный сегмент и молчит о причине.'))+
 pair(ok(demo('<div class="row g8"><span class="btn p" style="width:170px"><span class="spin"></span>Сохраняем…</span></div>'),'Ширина не меняется при загрузке.'),no(demo('<div class="row g8"><span class="btn p" style="width:110px;padding:0 8px"><span class="spin"></span>…</span></div>'),'Кнопка сжимается и прыгает, текст исчезает.'))+'</div>', '5')

# ---------- inputs
def inputs(theme):
    return demo('<div class="grid3" style="gap:10px 16px">'+F('Название','<div class="inp"><span class="ph">Например, Общий анализ крови</span></div>','Видно в списке и в поиске')+
      F('Название (фокус)','<div class="inp f"><span>Общий анализ крови</span></div>')+
      F('Дата документа',f'<div class="inp e">{I("cal","ic ic16")}<span class="mono">31.02.2026</span></div>','', 'Такой даты нет. Проверьте день и месяц')+
      F('Дата документа (заблокировано)',f'<div class="inp dis">{I("cal","ic ic16")}<span>Не указана</span></div>')+
      F('Поиск',f'<div class="inp search">{I("search")}<span class="ph">Поиск по названию</span><span class="grow"></span><span class="kbd">/</span></div>')+
      F('Заметка','<div class="inp ta" style="min-height:64px">Холестерин выше нормы, пересдать в октябре.</div>','42 / 2000')+'</div>',theme,'padding:16px')
page('Поля ввода · состояния', f'<div class="col g12">{inputs("light")}{inputs("dark")}</div><p class="cap" style="margin-top:12px">Высота 40, радиус 10, граница <span class="mono">control</span> 3,38:1 на белом (SC 1.4.11). Подпись над полем, подсказка и ошибка под ним. Ошибка показывается после попытки сохранить, не при первом фокусе (S7).</p>', '6')

seg2=demo('<div class="col g12"><span class="cap">Сегмент: 2 до 4 коротких варианта</span>'+typeradio(0)+'<div class="seg"><span class="on">Дата документа</span><span>Дата загрузки</span></div><span class="cap">Радио-строки: варианты с пояснением, вся строка кликабельна</span>'+
 '<div class="radio on"><span class="dot"></span><div class="col g4"><b style="font-weight:500">Только найденные · 3 документа</b><span class="cap">С учётом поиска и периода</span></div></div><div class="radio"><span class="dot"></span><div class="col g4"><b style="font-weight:500">Весь архив · 6 документов</b><span class="cap">157 КБ</span></div></div>'+
 f'<label class="row g8"><span class="cb on">{I("check","ic ic16")}</span>Дата не указана в документе</label></div>','light','padding:16px')
page('Выбор из вариантов', f'''<div class="two">{seg2}<div><table class="t"><tr><th>Вариантов</th><th>Контрол</th><th>Пример</th></tr><tr><td>2 до 4, коротко</td><td>Сегмент (radiogroup)</td><td>Тип документа</td></tr><tr><td>2 до 4, с пояснением</td><td>Радио-строки</td><td>Объём экспорта</td></tr><tr><td>5 и больше</td><td>Список с поиском</td><td>Не используется в v1</td></tr><tr><td>Да / нет</td><td>Чекбокс</td><td>Дата не указана</td></tr></table>
<div class="grid2" style="margin-top:12px;gap:10px">{ok(demo(typeradio(1)),"Три варианта видны сразу, один клик.")}{no(demo(f'<div class="inp" style="width:220px"><span>Тип</span><span class="grow"></span>{I("chev","ic ic16")}</div>'),"Выпадающий список из 3 пунктов: лишний клик, варианты скрыты.")}
{ok(demo('<div class="radio on" style="outline:2px dashed var(--accent);outline-offset:2px"><span class="dot"></span><span>Весь архив</span></div>'),"Цель нажатия: вся строка (пунктир).")}{no(demo('<div class="row g8"><span class="dot" style="outline:2px dashed #B42318;outline-offset:2px"></span><span>Весь архив</span></div>'),"Кликабелен только кружок 18 px (SC 2.5.8).")}</div></div></div>''', '6')

# ---------- list
lst=f'<div style="width:100%">{table([4,3],sel=(1,),hov=0)}</div>'
page('Список документов', f'''{demo(lst,'light','padding:12px')}
<div class="two" style="margin-top:12px">{demo(f'<div class="col g8" style="width:340px">{mcard(0)}{mcard(5)}</div>','dark','padding:12px')}
<div class="grid2" style="gap:10px">{ok(demo('<div class="tr hov" style="grid-template-columns:1fr 90px;outline:2px dashed var(--accent);border-radius:8px"><span>Общий анализ крови</span><span class="mono">08.04.2026</span></div>'),"Вся строка открывает документ, hover на тон темнее.")}{no(demo('<div class="tr" style="grid-template-columns:1fr 90px 30px"><span>Общий анализ крови</span><span class="mono">08.04.2026</span><span style="color:var(--text3)">'+I("eye","ic ic16")+'</span></div>'),"Открыть можно только иконкой глаза 16 px.")}
{ok(demo(dd(None)),"Без даты: явная метка, строка в конце.")}{no(demo('<span style="color:var(--text3)">пусто</span>'),"Пустая ячейка: кажется, что данные потеряны.")}</div></div>''', '7')

# ---------- filters
chips=f'<div class="row g8" style="flex-wrap:wrap"><span class="faint cap">3 из 6 ·</span><span class="chip"><b>Дата документа:</b> 01.04.2026 – 30.04.2026<span class="x">{I("x","ic ic16")}</span></span><span class="chip"><b>Тип:</b> Анализ<span class="x">{I("x","ic ic16")}</span></span><span class="btn sm t">Сбросить всё</span></div>'
hint=f'<div class="alert i">{I("info")}<div>1 документ без даты не участвует в фильтре по дате документа. <u style="color:var(--text);font-weight:500">Показать его</u></div></div>'
empty=f'<div class="card" style="padding:28px;display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center"><span class="fi">{I("search")}</span><b style="font-size:16px">Ничего не нашлось</b><span class="muted" style="max-width:360px">По запросу «рентген» за 01.01.2026 – 31.03.2026 документов нет.</span><div class="row g8"><span class="btn sm s">Убрать фильтр по дате</span><span class="btn sm p">Сбросить всё</span></div></div>'
page('Фильтры и поиск', f'''{demo('<div class="col g12" style="width:100%">'+toolbar('','01.04.2026','30.04.2026',0)+chips+hint+'</div>','light','padding:16px')}
<div class="two" style="margin-top:12px">{demo(empty,'dark','padding:12px')}<div class="grid2" style="gap:10px">{ok(demo(chips),"Применённые фильтры чипами, у каждого крестик, рядом «Сбросить всё» (S8).")}{no(demo(f'<span class="btn s sm">{I("filter","ic ic16")}Фильтры (2)</span>'),"Только счётчик: не видно, что именно отфильтровано.")}</div></div>''', '8')

# ---------- modals
del_body='<p class="muted">Документ «Заключение терапевта» от 10.04.2026, PDF-файл и заметка будут удалены без возможности восстановления.</p>'
del_ok=f'<div class="mdemo">{modal("Удалить документ?",del_body,"<span class=\'btn s focus\'>Отмена</span><span class=\'btn dg\'>Удалить</span>",sm=True)}</div>'
del_no='<div class="mdemo"><div class="scrim"><div class="modal sm" style="text-align:center;align-items:center"><div class="mh" style="justify-content:center;width:100%"><span style="font-size:44px;color:#D97706">?</span></div><div class="mb"><h2 class="h2">Вы уверены?</h2><p class="muted">Это действие нельзя отменить.</p></div><div class="mf" style="justify-content:center"><span class="btn p focus">Да</span><span class="btn s">Нет</span></div></div></div></div>'
page('Модальные окна', f'''<div class="pairs">{pair(ok(del_ok,"Заголовок «глагол + объект?», конкретика, текст слева, «Отмена» слева в фокусе, «Удалить» красная справа (S2)."),no(del_no,"«Вы уверены?», «Да / Нет», огромный вопрос, всё по центру, фокус на опасном действии."))}</div>
<p class="cap" style="margin-top:10px">Модалка только для необратимого, короткой формы и выбора объёма экспорта (S1). Ширина 560 / 440, радиус 20, отступы 24. Esc закрывает; если в форме есть данные, спрашиваем «Закрыть без сохранения?».</p>''', '9')

# ---------- sheets
sheet=f'''<div class="phone"><div class="scrim" style="align-items:flex-end"></div><div class="sheet"><div class="grab"></div><div style="padding:16px;display:flex;flex-direction:column;gap:16px"><div class="row"><h2 class="h2 grow">Фильтр</h2><span class="ib sm">{I("x")}</span></div>{F("Искать по",'<div class="seg" style="width:100%"><span class="on" style="flex:1;justify-content:center">Дата документа</span><span style="flex:1;justify-content:center">Дата загрузки</span></div>')}<div class="row g8"><span class="btn s lg grow">Сбросить</span><span class="btn p lg grow">Показать 3</span></div></div><div class="safearea">env(safe-area-inset-bottom)</div><div class="home"></div></div></div>'''
page('Нижние листы и безопасная зона', f'''<div class="two"><div class="row g24">{demo(sheet,'light','padding:0;background:none')}{demo(sheet,'dark','padding:0;background:none')}</div>
<div><p class="lead">На мобильном вместо модалки нижний лист: ручка 36 x 4, радиус 20 сверху, кнопки 48 px. Отступ снизу <span class="mono">calc(16px + env(safe-area-inset-bottom))</span>, в <span class="mono">viewport</span> обязательно <span class="mono">viewport-fit=cover</span>. Ни одна кнопка не касается индикатора «Домой».</p>
<div class="pairs">{ok(demo('<div style="position:relative;height:90px;background:var(--raised);border-radius:16px 16px 0 0;padding:12px"><span class="btn p" style="width:100%">Показать 3</span><div style="position:absolute;left:0;right:0;bottom:0;height:34px;background:repeating-linear-gradient(45deg,#E6F4F1 0 6px,transparent 6px 12px)"></div></div>'),"Кнопка выше безопасной зоны (штриховка).")}{no(demo('<div style="position:relative;height:90px;background:var(--raised);border-radius:16px 16px 0 0;padding:12px;display:flex;align-items:flex-end"><span class="btn p" style="width:100%;margin-bottom:-6px">Показать 3</span><div style="position:absolute;left:50%;bottom:8px;width:120px;height:5px;border-radius:3px;background:#171717;transform:translateX(-50%)"></div></div>'),"Кнопка под индикатором «Домой»: промахи и случайный выход.")}</div></div></div>''', '9')

# ---------- states
page('Состояния: загрузка, успех, ошибка, офлайн', '<div class="grid2">'+
 demo('<div class="col g12">'+filebox('05-ultrasound-summary.pdf','78 КБ · загружено 62%','up',62)+f'<div class="alert e">{I("off")}<div><b>Связь прервалась на 62%</b>Введённые данные сохранены в форме.<div style="margin-top:8px"><span class="btn sm s">{I("retry","ic ic16")}Повторить загрузку</span></div></div></div></div>','light','padding:16px')+
 demo(f'<div class="col g12"><div class="banner" style="border-radius:12px;padding:10px 14px">{I("off")}<b>Нет связи с сервером.</b> Изменения пока недоступны.<span class="grow"></span><span class="btn sm s">Повторить</span></div><div style="position:relative;height:64px"><div class="toast">{I("check")}Документ «ЭКГ покоя» добавлен<u>Открыть</u></div></div><div class="row g12"><span class="save">Сохраняем…</span><span class="save ok">{I("check","ic ic16")}Сохранено</span><span class="save" style="color:var(--danger)">Не сохранилось. Повторить</span></div></div>','light','padding:16px')+
 demo(f'<div class="col g12"><div class="alert w">{I("alert")}<div><b>Файл больше 20 МБ</b>Сожмите PDF или разделите его на части.</div></div><div class="alert e">{I("alert")}<div><b>Это не PDF</b>Сервис принимает только PDF. Сохраните документ в PDF и попробуйте снова.</div></div></div>','dark','padding:16px')+
 demo(f'<div class="col g12"><div class="alert i">{I("info")}<div>В списке документ будет помечен «Дата не указана». В фильтре по дате документа он не участвует.</div></div><div style="position:relative;height:64px"><div class="toast">{I("check")}Документ удалён</div></div></div>','dark','padding:16px')+'</div>', '10')

# ---------- skeleton + AI frames
sk=''.join(f'<div class="row g12" style="padding:10px 0;border-top:1px solid var(--border)"><span class="skel" style="width:36px;height:36px;border-radius:10px"></span><div class="col g8 grow"><span class="skel" style="width:{w}px;height:12px"></span><span class="skel" style="width:90px;height:10px"></span></div><span class="skel" style="width:84px;height:20px"></span></div>' for w in (220,160))
def aiframe(n):
    gen_=lambda w: f'<span class="gen" style="width:{w}px;height:14px;display:block"></span>'
    ti = '<span>Липидограмма</span><span class="grow"></span><span class="tag ot" style="height:20px">'+I("spark","ic ic16")+'подсказка</span>' if n>=2 else gen_(160)
    ty = typeradio(0) if n>=3 else f'<div class="inp">{gen_(100)}</div>'
    da = f'<span class="mono">21.05.2026</span>' if n>=4 else gen_(90)
    head = f'<div class="alert i" style="background:var(--accentSoft);color:var(--accent)">{I("spark")}<div><b>Заполняем поля по тексту PDF</b>Это подсказка: проверьте значения.</div></div>' if n<4 else '<div class="alert s">'+I("check")+'<div><b>Поля заполнены</b>Проверьте перед сохранением.</div></div>'
    return f'<div class="aif"><span class="step-n">Кадр {n} · {["0,0 с","0,8 с","1,6 с","2,4 с"][n-1]}</span>'+demo('<div class="col g12">'+head+F('Название',f'<div class="inp">{ti}</div>')+F('Тип',ty)+F('Дата документа',f'<div class="inp">{I("cal","ic ic16")}{da}</div>','Найдено в PDF: «Дата документа 21.05.2026»' if n>=4 else '')+'<div class="row g8"><span class="btn t sm">Заполнить вручную</span><span class="grow"></span><span class="btn sm '+('p' if n>=4 else 'dis')+'">Сохранить</span></div></div>','light','padding:12px')+'</div>'
page('Скелетоны и AI-генерация', f'''<div class="two" style="grid-template-columns:1fr 1fr 1.1fr;display:grid;gap:14px;margin-bottom:12px"><div><span class="step-n">Скелетон списка · светлая</span>{demo(sk,'light','padding:4px 12px')}</div><div><span class="step-n">Скелетон списка · тёмная</span>{demo(sk,'dark','padding:4px 12px')}</div><p class="cap" style="align-self:end">Серый шиммер 1600 мс повторяет форму строк, показываем от 1 до 10 с ожидания. Меньше 1 с ничего не показываем, больше 10 с показываем прогресс и отмену (S5, S6).</p></div>
<div><div class="aifs">{"".join(aiframe(i) for i in (1,2,3,4))}</div><p class="cap" style="margin-top:8px">AI-подсказка: бирюзовый шиммер внутри полей (не серый, чтобы отличать от загрузки страницы), поля заполняются по одному с растворением 200 мс, у значения метка «подсказка», у даты цитата-источник. «Заполнить вручную» доступна сразу; через 10 с без ответа: «Не успели подсказать, заполните вручную»; при 429 отсчёт по Retry-After.</p></div></div>''', '12')

# ---------- motion
mt=[('fast','120 мс','ease-out','hover, нажатие',120),('base','200 мс','cubic-bezier(0.2, 0, 0, 1)','модалка, тост',200),('slow','320 мс','cubic-bezier(0.2, 0, 0, 1)','нижний лист',320),('highlight','1200 мс','ease-out','подсветка новой строки',1200),('shimmer','1600 мс','linear, бесконечно','скелетон, AI',1600)]
page('Движение', '<table class="t"><tr><th>Токен</th><th>Длительность</th><th>Кривая</th><th>Где</th><th>Шкала</th></tr>'+''.join(f'<tr><td class="mono">{a}</td><td class="mono">{b}</td><td class="mono">{c}</td><td>{d}</td><td><div class="tl"><i style="width:{e/1600*100:.1f}%"></i></div></td></tr>' for a,b,c,d,e in mt)+'</table>'+
 '<div class="pairs" style="margin-top:14px">'+pair(ok(demo('<div class="row g16"><div class="mv" style="opacity:.3;transform:translateY(8px)">0 мс</div><div class="mv" style="opacity:.7;transform:translateY(3px)">100 мс</div><div class="mv">200 мс</div></div>'),'Модалка: прозрачность 0 → 1 и сдвиг 8 px за 200 мс.'),no(demo('<div class="row g16"><div class="mv" style="transform:scale(.5)">0 мс</div><div class="mv" style="transform:scale(1.15)">150 мс</div><div class="mv">400 мс</div></div>'),'Масштаб 0,5 → 1,15 → 1 с пружиной: игрушечно и укачивает.'))+'</div><p class="cap">prefers-reduced-motion: reduce: длительности 0, шиммер статичный, вместо сдвига только прозрачность (S13).</p>', '11')

# ---------- icons
icons_dk=''.join(f'<div class="icn">{I(k,"ic ic24")}<span class="mono">{k}</span></div>' for k in list(P)[:16])
icons=''.join(f'<div class="icn">{I(k,"ic ic24")}<span class="mono">{k}</span></div>' for k in P)
page('Иконки', f'<p class="lead">Набор lucide, штрих 1,75, размеры 16 / 20 / 24, цвет наследуется от текста. Иконка-кнопка всегда с aria-label и подсказкой. Иконка без подписи только для общепринятых действий: поиск, закрыть, ещё.</p><div class="two" style="grid-template-columns:2fr 1fr">{demo(f"<div class=icns>{icons}</div>","light","padding:12px")}{demo(f"<div class=icns style=grid-template-columns:repeat(4,1fr)>{icons_dk}</div>","dark","padding:12px")}</div>', '13')

# ---------- a11y checklist
ch=['Контраст текста 4,5:1, крупного и границ 3:1 (проверено для всех пар)','Цель нажатия 40 px и больше, мобильные главные 48 px (SC 2.5.8 требует 24)','Фокус виден везде: кольцо 2 px accent с отступом 2 px','Порядок табуляции: шапка, поиск, фильтры, таблица, панель','Ошибки формы текстом и иконкой, не только цветом (SC 1.4.1)','Таблица семантическая, сортировка объявляется (aria-sort)','«Сохранено» и тосты в aria-live=polite','Модалка: фокус-ловушка, Esc, возврат фокуса на кнопку-источник','prefers-reduced-motion уважается','Зум 200% и ширина 320 px без горизонтальной прокрутки, кроме таблицы','lang="ru", даты в формате дд.мм.гггг','Тёмная тема не единственная: светлая по умолчанию (S4)']
page('Доступность: чек-лист дизайнера', '<div class="chk">'+''.join(f'<div>{I("check","ic ic16")}<span>{c}</span></div>' for c in ch)+'</div>', '15')

# ---------- screens
def shots(prefix, items, per, mobile=False):
    for i in range(0,len(items),per):
        chunk=items[i:i+per]
        cells=''.join(f'<figure class="{"mfig" if mobile else "dfig"}"><img src="../screens/{prefix}-{j:02d}.png"><figcaption><b>{n}</b>{(" · "+d) if d else ""}</figcaption></figure>' for j,n,d in chunk)
        title={'desktop-light':'Экраны · десктоп · светлая','desktop-dark':'Экраны · десктоп · тёмная','mobile-light':'Экраны · мобильный · светлая','mobile-dark':'Экраны · мобильный · тёмная'}[prefix]
        page(title+(f' · {i//per+1}' if len(items)>per else ''), f'<div class="{"mgrid" if mobile else "dgrid"}">{cells}</div>', 'Э', cls='scr')
DL=[(i+1,n,'') for i,(n,f,d) in enumerate(gen.D)]
DD=[(k+1,n+' · тёмная','') for k,(n,f,d) in enumerate([x for x in gen.D if x[0][:3] in ('D01','D02','D06','D07','D08','D09','D11','D12','D15')])]
ML=[(i+1,n,'') for i,(n,f,d) in enumerate(gen.M)]
MD=[(k+1,n+' · тёмная','') for k,(n,f,d) in enumerate([x for x in gen.M if x[0][:3] in ('M02','M04','M06','M07')])]
shots('desktop-light',DL,6); shots('desktop-dark',DD,6); shots('mobile-light',ML,4,True); shots('mobile-dark',MD,4,True)

# ---------- TOC (insert at index 1)
N=len(PAGES)+1
toc=[]; seen=set()
for idx,(t,s,b,c) in enumerate(PAGES):
    if not t: continue
    base=t.split(' · ')[0] if s=='Э' else t
    key=(s,base) if s=='Э' else t
    if s=='Э':
        base=' · '.join(t.split(' · ')[:3])
        if base in seen: continue
        seen.add(base)
    toc.append((base, idx+2))
half=(len(toc)+1)//2
tl=lambda xs: ''.join(f'<div class="tc"><span>{a}</span><i></i><b class="mono">{p}</b></div>' for a,p in xs)
PAGES.insert(1,('Содержание','', f'<div class="two">{"<div>"+tl(toc[:half])+"</div>"}{"<div>"+tl(toc[half:])+"</div>"}</div>',''))

html=['<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Медархив · Брендбук</title><link rel="stylesheet" href="app.css"><link rel="stylesheet" href="bb.css"></head><body class="bb">']
for i,(t,s,b,c) in enumerate(PAGES):
    hdr = '' if not t else f'<header><span class="sec">{s if s and s!="Э" else ("Экраны" if s=="Э" else "")}</span><h2>{t}</h2></header>'
    ftr = '' if i==0 else f'<footer><span>Медархив · Брендбук 1.0</span><span class="mono">{i+1} / {len(PAGES)}</span></footer>'
    html.append(f'<section class="pg {c}">{hdr}<div class="pb">{b}</div>{ftr}</section>')
html.append('</body></html>')
(HERE / 'brandbook.html').write_text('\n'.join(html), encoding='utf-8')
print(len(PAGES),'pages')
