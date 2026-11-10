import json
P={
'search':'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>','x':'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>','plus':'<path d="M5 12h14"/><path d="M12 5v14"/>',
'upload':'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
'download':'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
'file':'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
'cal':'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
'trash':'<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
'pencil':'<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>','note':'<path d="M15.5 3H5a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h14a2 2 0 0 0 2-2V8.5L15.5 3Z"/><path d="M15 3v6h6"/>',
'alert':'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
'check':'<path d="M20 6 9 17l-5-5"/>','moon':'<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
'sun':'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
'ext':'<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
'spark':'<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2Z"/><path d="M19 3v4M17 5h4"/>',
'info':'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
'archive':'<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
'back':'<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>','more':'<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
'lock':'<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
'off':'<path d="m2 2 20 20"/><path d="M5.78 5.78A7 7 0 0 0 9 19h8.5a4.5 4.5 0 0 0 1.31-.19"/><path d="M21.53 16.5A4.5 4.5 0 0 0 17.5 10h-1.79A7 7 0 0 0 10 5.07"/>',
'chev':'<path d="m6 9 6 6 6-6"/>','filter':'<path d="M3 6h18"/><path d="M7 12h10"/><path d="M10 18h4"/>',
'retry':'<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>','eye':'<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
'sort':'<path d="m3 16 4 4 4-4"/><path d="M7 20V4"/><path d="M11 4h10"/><path d="M11 8h7"/><path d="M11 12h4"/>',
'folder':'<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
'shield':'<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
'key':'<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
}
def I(n,c='ic'):return f'<svg class="{c}" viewBox="0 0 24 24">{P[n]}</svg>'
DOCS=[('Общий анализ крови','an','Анализ','08.04.2026','10.11.2026, 19:02','01-general-blood-test.pdf','79 КБ',True),
('Биохимический анализ крови','an','Анализ','08.04.2026','10.11.2026, 19:03','02-blood-biochemistry.pdf','78 КБ',False),
('Липидограмма','an','Анализ','21.05.2026','10.11.2026, 19:03','03-lipid-profile.pdf','77 КБ',False),
('Заключение терапевта','co','Заключение','10.04.2026','10.11.2026, 19:04','04-therapist-summary.pdf','78 КБ',True),
('УЗИ почек и мочевого пузыря','co','Заключение','22.05.2026','10.11.2026, 19:05','05-ultrasound-summary.pdf','78 КБ',False),
('ЭКГ покоя','co','Заключение',None,'10.11.2026, 19:05','06-ecg-summary-undated.pdf','76 КБ',False)]
ORDER=[4,2,3,0,1,5]  # by doc date desc, undated last
def tag(k,t):return f'<span class="tag {k}">{t}</span>'
def dd(d):return f'<span class="mono">{d}</span>' if d else f'<span class="nodate">{I("cal","ic ic16")}Не указана</span>'
def header(theme='light',mobile=False,actions=True):
    tog=I('moon' if theme=='light' else 'sun')
    if mobile:
        return f'<div class="hdr"><div class="logo"><i>{I("folder","ic ic16")}</i>Медархив</div><div class="sp"></div><div class="ib">{tog}</div><div class="ib">{I("download")}</div></div>'
    a=f'<div class="ib" title="Тема">{tog}</div><button class="btn s">{I("download")}Экспорт</button><button class="btn p">{I("plus")}Добавить PDF</button>' if actions else f'<div class="ib">{tog}</div>'
    return f'<div class="hdr"><div class="logo"><i>{I("folder","ic ic16")}</i>Медархив</div><span class="faint" style="margin-left:8px">Личный архив медицинских документов</span><div class="sp"></div>{a}</div>'
def toolbar(q='',fr='',to='',mode=0,typ=0,focus=False):
    s=f'<div class="inp search{" f" if focus else ""}">{I("search")}' + (f'<span>{q}</span><span class="grow"></span><span class="ib sm" style="width:24px;height:24px">{I("x","ic ic16")}</span>' if q else '<span class="ph">Поиск по названию</span><span class="grow"></span><span class="kbd">/</span>') + '</div>'
    seg='<div class="seg">'+''.join(f'<span class="{"on" if i==mode else ""}">{t}</span>' for i,t in enumerate(['Дата документа','Дата загрузки']))+'</div>'
    di=lambda v,ph:f'<div class="inp date">{I("cal","ic ic16")}'+(f'<span class="mono">{v}</span>' if v else f'<span class="ph">{ph}</span>')+'</div>'
    ty='<div class="seg">'+''.join(f'<span class="{"on" if i==typ else ""}">{t}</span>' for i,t in enumerate(['Все типы','Анализ','Заключение','Другое']))+'</div>'
    return f'<div class="toolbar">{s}<div class="fld"><label class="faint" style="font-weight:400;font-size:12px">Фильтр по</label>{seg}</div><div class="fld"><label class="faint" style="font-weight:400;font-size:12px">С</label>{di(fr,"дд.мм.гггг")}</div><div class="fld"><label class="faint" style="font-weight:400;font-size:12px">По</label>{di(to,"дд.мм.гггг")}</div><div class="grow"></div>{ty}</div>'
def table(idx,sel=(),hov=None):
    h='<div class="tbl"><div class="tr th"><span><span class="cb"></span></span><span>Название</span><span>Тип</span><span class="row g4">Дата документа '+I('chev','ic ic16')+'</span><span>Загружен</span><span></span></div>'
    for i in idx:
        n,k,t,d,u,f,sz,note=DOCS[i]
        cls=' sel' if i in sel else (' hov' if i==hov else '')
        cb='<span class="cb on">'+I('check','ic ic16')+'</span>' if i in sel else '<span class="cb"></span>'
        nt=f'<span class="row g4">{I("note","ic ic16")}Есть заметка</span>' if note else ''
        h+=f'<div class="tr{cls}"><span>{cb}</span><div class="name"><span class="fi">{I("file")}</span><div class="col" style="min-width:0"><span class="t">{n}</span><span class="s"><span>PDF · {sz}</span>{nt}</span></div></div><span>{tag(k,t)}</span><span>{dd(d)}</span><span class="mono faint">{u}</span><span class="acts"><span class="ib sm">{I("eye","ic ic16")}</span><span class="ib sm">{I("more","ic ic16")}</span></span></div>'
    return h+'</div>'
def listpage(theme,extra='',idx=ORDER,tb=None,sub=None,chips='',sel=(),hov=None,banner=''):
    tb=tb or toolbar()
    sub=sub or f'{len(idx)} документов · отсортировано по дате документа, новые сверху'
    return f'{header(theme)}{banner}<div class="page"><div class="row g12"><div class="col"><h1 class="h1">Документы</h1><span class="muted">{sub}</span></div></div>{tb}{chips}{table(idx,sel,hov) if idx else ""}{extra}</div>'
def frame(cls,theme,inner,title,desc=''):
    home='<div class="home"></div>' if cls=='m' else ''
    return f'<div><div class="label">{title}<small>{desc}</small></div><div class="frame {cls}" data-theme="{theme}">{inner}{home}</div></div>'
def modal(title,body,foot,sub='',sm=False,icon=None,danger=False):
    ic=f'<span class="fi" style="width:40px;height:40px;{"background:var(--dangerBg);color:var(--danger)" if danger else ""}">{I(icon)}</span>' if icon else ''
    return f'<div class="scrim"><div class="modal{" sm" if sm else ""}" role="dialog"><div class="mh">{ic}<div class="col grow g4"><h2 class="h2">{title}</h2>{f"<p class=muted>{sub}</p>" if sub else ""}</div><span class="ib sm">{I("x")}</span></div><div class="mb">{body}</div><div class="mf">{foot}</div></div></div>'
def F(label,inner,hint='',err=''):
    return f'<div class="fld"><label>{label}</label>{inner}'+(f'<span class="hint">{hint}</span>' if hint else '')+(f'<span class="err">{I("alert","ic ic16")}{err}</span>' if err else '')+'</div>'
def typeradio(on=0):
    return '<div class="seg" style="width:100%">'+''.join(f'<span class="{"on" if i==on else ""}" style="flex:1;justify-content:center">{t}</span>' for i,t in enumerate(['Анализ','Заключение','Другое']))+'</div>'
def filebox(name,sz,state='ok',pct=100):
    st={'ok':f'<span class="save ok">{I("check","ic ic16")}Готов к сохранению</span>','up':f'<div class="bar" style="width:100%"><i style="width:{pct}%"></i></div>','err':f'<span class="err" style="color:var(--danger);font-size:12px">Это не PDF</span>'}[state]
    return f'<div class="filebox"><span class="fi">{I("file")}</span><div class="col grow g4" style="min-width:0"><span style="font-weight:500">{name}</span><span class="faint" style="font-size:12px">{sz}</span>{st if state!="ok" else ""}</div>{st if state=="ok" else ""}<span class="ib sm">{I("x","ic ic16")}</span></div>'
# ---------- desktop screens
def D_onboarding(t):
    steps=''.join(f'<div class="step"><span class="n">{i+1}</span><div class="col"><b style="font-weight:600">{a}</b><span class="muted">{b}</span></div></div>' for i,(a,b) in enumerate([('Добавьте PDF','Перетащите файл или выберите его на компьютере. Подойдут анализы и заключения врачей.'),('Подпишите документ','Название, тип и дата документа. Дату загрузки мы запишем сами.'),('Находите и выгружайте','Поиск по названию, фильтр по датам, заметки и выгрузка архива одним ZIP.')]))
    body=f'''{header(t,actions=False)}<div style="display:grid;grid-template-columns:1fr 560px;gap:64px;padding:72px 120px;align-items:center">
<div class="col g24"><span class="tag ot" style="align-self:flex-start">Шаг 1 из 1 · первый запуск</span><h1 style="font:600 44px/52px Geist;letter-spacing:-.03em">Все медицинские документы в одном месте</h1><p class="muted" style="font-size:17px;line-height:26px;max-width:520px">Анализы и заключения больше не потеряются в почте и мессенджерах. Добавьте PDF, подпишите его и находите за секунды.</p><div class="steps">{steps}</div>
<div class="alert i" style="max-width:560px">{I("shield")}<div><b>Где хранятся документы</b>Файлы и заметки хранятся на сервере сервиса и привязаны к этому браузеру. Чтобы открыть архив на другом устройстве, сохраните ключ доступа в настройках.</div></div></div>
<div class="drop" style="padding:56px 32px;gap:16px"><span class="fi" style="width:64px;height:64px;border-radius:18px;background:var(--accentSoft);color:var(--accent)">{I("upload","ic ic24")}</span><h2 class="h2">Добавьте первый документ</h2><p class="muted">Перетащите PDF сюда или выберите файл</p><button class="btn p lg">{I("plus")}Выбрать PDF</button><span class="faint" style="font-size:12px">Только PDF, до 20 МБ. Распознавать текст не нужно.</span></div></div>'''
    return body
def D_upload(t,state='filled'):
    lst=listpage(t)
    if state=='filled':
        body=filebox('01-general-blood-test.pdf','79 КБ · 1 страница')+F('Название','<div class="inp f"><span>Общий анализ крови</span></div>','Так документ будет называться в списке. Имя файла не меняется.')+F('Тип',typeradio(0))+'<div class="row g12" style="align-items:flex-end">'+F('Дата документа',f'<div class="inp" style="width:200px">{I("cal","ic ic16")}<span class="mono">08.04.2026</span></div>')+f'<label class="row g8" style="height:40px"><span class="cb"></span>Дата не указана в документе</label></div><span class="hint faint" style="font-size:12px">Дата загрузки запишется автоматически: 10.11.2026, 19:02</span>'
        foot='<button class="btn t">Отмена</button><button class="btn p">Сохранить в архив</button>'
        return lst+modal('Новый документ',body,foot,'Проверьте данные перед сохранением. Их можно изменить позже.')
    if state=='nodate':
        body=filebox('06-ecg-summary-undated.pdf','76 КБ · 1 страница')+F('Название','<div class="inp"><span>ЭКГ покоя</span></div>')+F('Тип',typeradio(1))+'<div class="row g12" style="align-items:flex-end">'+F('Дата документа',f'<div class="inp dis" style="width:200px">{I("cal","ic ic16")}<span>Не указана</span></div>')+f'<label class="row g8" style="height:40px"><span class="cb on">{I("check","ic ic16")}</span>Дата не указана в документе</label></div><div class="alert w">{I("info")}<div>В списке документ будет помечен «Дата не указана». В фильтре по дате документа он не участвует, его всегда можно найти по названию.</div></div>'
        return lst+modal('Новый документ',body,'<button class="btn t">Отмена</button><button class="btn p">Сохранить в архив</button>')
    if state=='errors':
        body=f'<div class="drop over" style="padding:24px">{I("upload","ic ic24")}<b>Отпустите файл, чтобы добавить</b></div>'+filebox('скан_анализа.jpg','2,4 МБ','err')+f'<div class="alert e">{I("alert")}<div><b>Файл не добавлен: это не PDF</b>Сервис принимает только PDF. Сохраните документ в PDF и попробуйте снова.</div></div>'+F('Название','<div class="inp e"><span class="ph">Например, «Общий анализ крови»</span></div>',err='Введите название, чтобы найти документ в списке')+F('Дата документа',f'<div class="inp e" style="width:200px">{I("cal","ic ic16")}<span class="mono">31.02.2026</span></div>',err='Такой даты нет. Проверьте день и месяц')
        return lst+modal('Новый документ',body,'<button class="btn t">Отмена</button><button class="btn p">Сохранить в архив</button>')
    if state=='progress':
        body=filebox('05-ultrasound-summary.pdf','78 КБ · загружено 62%','up',62)+F('Название','<div class="inp dis"><span>УЗИ почек и мочевого пузыря</span></div>')+F('Тип',typeradio(1))+f'<div class="alert e">{I("off")}<div><b>Связь прервалась на 62%</b>Введённые данные сохранены в форме. Повторите загрузку, когда появится интернет.<div style="margin-top:8px"><span class="btn sm s">{I("retry","ic ic16")}Повторить загрузку</span></div></div></div>'
        return lst+modal('Новый документ',body,'<button class="btn t">Отмена</button><button class="btn p ld dis">Сохраняем…</button>')
def D_list(t,toast=True):
    tst=f'<div class="toast">{I("check")}Документ «ЭКГ покоя» добавлен<u>Открыть</u></div>' if toast else ''
    return listpage(t,hov=0)+tst
def D_filtered(t):
    chips=f'<div class="row g8"><span class="faint" style="font-size:13px">3 из 6 · </span><span class="chip"><b>Дата документа:</b> 01.04.2026 – 30.04.2026<span class="x">{I("x","ic ic16")}</span></span><button class="btn sm t">Сбросить всё</button></div>'
    extra=f'<div class="alert i">{I("info")}<div>1 документ без даты не участвует в фильтре по дате документа. <u style="color:var(--text);font-weight:500">Показать его</u></div></div>'
    return listpage(t,extra=extra,idx=[3,0,1],tb=toolbar('','01.04.2026','30.04.2026',0),sub='Найдено 3 документа',chips=chips)
def D_empty_search(t):
    chips=f'<div class="row g8"><span class="chip"><b>Поиск:</b> рентген<span class="x">{I("x","ic ic16")}</span></span><span class="chip"><b>Дата загрузки:</b> 01.01.2026 – 31.03.2026<span class="x">{I("x","ic ic16")}</span></span><button class="btn sm t">Сбросить всё</button></div>'
    extra=f'<div class="card" style="padding:64px;display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center"><span class="fi" style="width:56px;height:56px;border-radius:16px">{I("search","ic ic24")}</span><h2 class="h2">Ничего не нашлось</h2><p class="muted" style="max-width:460px">По запросу «рентген» за 01.01.2026 – 31.03.2026 документов нет. Попробуйте другое название или расширьте период.</p><div class="row g8"><button class="btn s">Убрать фильтр по дате</button><button class="btn p">Сбросить всё</button></div></div>'
    return listpage(t,extra=extra,idx=[],tb=toolbar('рентген','01.01.2026','31.03.2026',1),sub='Найдено 0 документов',chips=chips)
def side(edit=False,note='Холестерин в биохимии выше нормы, пересдать в октябре.',saved='ok'):
    if edit:
        meta=F('Название','<div class="inp f"><span>Общий анализ крови</span></div>')+F('Тип',typeradio(0))+F('Дата документа',f'<div class="inp">{I("cal","ic ic16")}<span class="mono">08.04.2026</span></div>')+'<label class="row g8"><span class="cb"></span>Дата не указана в документе</label><div class="row g8"><button class="btn p">Сохранить</button><button class="btn t">Отмена</button></div>'
    else:
        meta=f'<div class="row g8">{tag("an","Анализ")}</div><dl class="kv"><dt>Дата документа</dt><dd class="mono">08.04.2026</dd><dt>Загружен</dt><dd class="mono">10.11.2026, 19:02</dd><dt>Файл</dt><dd>01-general-blood-test.pdf<br><span class="faint">PDF · 79 КБ · 1 стр.</span></dd></dl><div class="row g8" style="flex-wrap:wrap"><button class="btn s sm">{I("pencil","ic ic16")}Изменить описание</button><button class="btn s sm">{I("download","ic ic16")}Скачать</button><button class="btn s sm">{I("ext","ic ic16")}В новой вкладке</button></div>'
    st={'ok':f'<span class="save ok">{I("check","ic ic16")}Сохранено</span>','ing':'<span class="save">Сохраняем…</span>','err':f'<span class="save" style="color:var(--danger)">{I("alert","ic ic16")}Не сохранилось. Повторить</span>'}[saved]
    return f'''<aside class="side"><div style="padding:24px;display:flex;flex-direction:column;gap:16px;border-bottom:1px solid var(--border)"><h2 class="h2">Общий анализ крови</h2>{meta}</div>
<div style="padding:24px;display:flex;flex-direction:column;gap:10px;flex:1"><div class="row"><span class="h3 grow">Заметка</span>{st}</div><div class="inp ta" style="min-height:140px">{note or '<span class="ph">Например: что сказал врач, когда пересдать</span>'}</div><div class="row"><span class="faint grow" style="font-size:12px">{len(note)} / 2000 · сохраняется автоматически</span><button class="btn sm t">Очистить</button></div></div>
<div style="padding:16px 24px;border-top:1px solid var(--border)"><button class="btn dgt sm" style="padding:0 8px">{I("trash","ic ic16")}Удалить документ</button></div></aside>'''
def D_doc(t,edit=False):
    return f'''{header(t)}<div class="row" style="height:836px;align-items:stretch"><div class="viewer"><div class="vtool"><span class="btn sm t" style="padding:0 8px">{I("back","ic ic16")}Все документы</span><span class="grow"></span><span>Стр. 1 из 1</span><span class="ib sm">−</span><span class="mono">100%</span><span class="ib sm">+</span></div><div style="overflow:hidden;flex:1"><div class="paper" style="width:600px"><img src="doc01-1.png"></div></div></div>{side(edit)}</div>'''
def D_delete(t):
    body='<p class="muted">Документ «Заключение терапевта» от 10.04.2026, PDF-файл и заметка будут удалены без возможности восстановления.</p>'
    return listpage(t)+modal('Удалить документ?',body,'<button class="btn s">Отмена</button><button class="btn dg">Удалить</button>',sm=True)
def D_export(t):
    r=lambda on,a,b:f'<div class="radio{" on" if on else ""}"><span class="dot"></span><div class="col"><b style="font-weight:500">{a}</b><span class="faint" style="font-size:13px">{b}</span></div></div>'
    body=r(0,'Весь архив','6 документов')+r(1,'Только найденные','2 документа по текущему поиску и фильтру')+r(0,'Выбранные','Отметьте документы в списке')+f'<div class="alert i">{I("archive")}<div><b>Что будет в ZIP</b>PDF с понятными именами вида «2026-04-08 Анализ Общий анализ крови.pdf», таблица documents.csv для Excel (название, тип, даты, заметка) и тот же список в documents.json.</div></div>'
    return listpage(t,idx=[0,1],sub='Найдено 2 документа')+modal('Выгрузить документы',body,f'<button class="btn t">Отмена</button><button class="btn p">{I("download")}Скачать ZIP · 157 КБ</button>')
def D_skeleton(t):
    rows=''.join(f'<div class="tr"><span><span class="skel" style="display:block;width:18px;height:18px"></span></span><div class="name"><span class="skel" style="width:36px;height:36px;border-radius:10px"></span><div class="col g8"><span class="skel" style="width:{w}px;height:12px"></span><span class="skel" style="width:90px;height:10px"></span></div></div><span class="skel" style="width:84px;height:20px"></span><span class="skel" style="width:90px;height:12px"></span><span class="skel" style="width:120px;height:12px"></span><span></span></div>' for w in (220,260,160,240,280,140))
    tbl='<div class="tbl"><div class="tr th"><span></span><span>Название</span><span>Тип</span><span>Дата документа</span><span>Загружен</span><span></span></div>'+rows+'</div>'
    return f'{header(t)}<div class="page"><div class="col g8"><h1 class="h1">Документы</h1><span class="skel" style="width:280px;height:14px"></span></div>{toolbar()}{tbl}</div>'
def D_offline(t):
    ban=f'<div class="banner">{I("off")}<b>Нет связи с сервером.</b> Показаны документы из последней загрузки. Изменения пока недоступны.<span class="grow"></span><span class="btn sm s">{I("retry","ic ic16")}Повторить</span></div>'
    return listpage(t,banner=ban)
def D_ai(t):
    body=filebox('03-lipid-profile.pdf','77 КБ · 1 страница')+f'<div class="alert i" style="background:var(--accentSoft);color:var(--accent)">{I("spark")}<div><b>Заполняем поля по тексту PDF</b>Это подсказка, а не распознавание: проверьте значения. Медицинских выводов сервис не делает.</div></div>'+F('Название','<div class="inp"><span class="gen" style="width:180px;height:14px;display:block"></span></div>')+F('Тип','<div class="inp"><span class="gen" style="width:110px;height:14px;display:block"></span></div>')+F('Дата документа',f'<div class="inp" style="width:200px">{I("cal","ic ic16")}<span class="gen" style="width:96px;height:14px;display:block"></span></div>')
    return listpage(t)+modal('Новый документ',body,'<button class="btn t">Заполнить вручную</button><button class="btn p dis">Сохранить в архив</button>')
def D_ai_done(t):
    body=filebox('03-lipid-profile.pdf','77 КБ · 1 страница')+F('Название',f'<div class="inp"><span>Липидограмма</span><span class="grow"></span><span class="tag ot" style="height:20px">{I("spark","ic ic16")}подсказка</span></div>')+F('Тип',typeradio(0))+F('Дата документа',f'<div class="inp" style="width:200px">{I("cal","ic ic16")}<span class="mono">21.05.2026</span></div>','Найдено в PDF: «Дата документа 21.05.2026»')
    return listpage(t)+modal('Новый документ',body,'<button class="btn t">Отмена</button><button class="btn p">Сохранить в архив</button>','Поля заполнены по тексту файла. Проверьте их перед сохранением.')
# ---------- mobile
def mcard(i,sel=False):
    n,k,tp,d,u,f,sz,note=DOCS[i]
    return f'<div class="mcard"><span class="fi">{I("file")}</span><div class="col grow g8" style="min-width:0"><span style="font-weight:500">{n}</span><div class="row g8" style="flex-wrap:wrap">{tag(k,tp)}{dd(d)}</div><span class="faint" style="font-size:12px">Загружен 10.11.2026{" · есть заметка" if note else ""}</span></div><span class="ib sm">{I("more","ic ic16")}</span></div>'
def M_list(t,idx=ORDER,top=''):
    cards=''.join(mcard(i) for i in idx)
    return f'{header(t,True)}<div style="padding:16px;display:flex;flex-direction:column;gap:12px"><div class="row"><h1 class="h2 grow">Документы</h1><span class="faint">{len(idx)}</span></div><div class="row g8"><div class="inp grow">{I("search")}<span class="ph">Поиск по названию</span></div><div class="ib s">{I("filter")}</div></div>{top}{cards}</div><div class="sticky"><button class="btn p lg" style="width:100%">{I("plus")}Добавить PDF</button></div>'
def M_onb(t):
    steps=''.join(f'<div class="step"><span class="n">{i+1}</span><div class="col"><b style="font-weight:600">{a}</b><span class="muted" style="font-size:13px">{b}</span></div></div>' for i,(a,b) in enumerate([('Добавьте PDF','Анализ или заключение врача'),('Подпишите','Название, тип, дата документа'),('Находите и выгружайте','Поиск, фильтр по датам, ZIP')]))
    return f'{header(t,True)}<div style="padding:24px 16px;display:flex;flex-direction:column;gap:20px"><h1 style="font:600 30px/36px Geist;letter-spacing:-.02em">Все медицинские документы в одном месте</h1><p class="muted">Добавьте PDF, подпишите его и находите за секунды.</p><div class="steps">{steps}</div><div class="alert i">{I("shield")}<div>Файлы хранятся на сервере и привязаны к этому браузеру. Ключ доступа откроет архив на другом устройстве.</div></div></div><div class="sticky"><button class="btn p lg" style="width:100%">{I("plus")}Выбрать первый PDF</button></div>'
def M_filter(t):
    sh=f'<div class="sheet"><div class="grab"></div><div style="padding:16px;display:flex;flex-direction:column;gap:16px"><div class="row"><h2 class="h2 grow">Фильтр</h2><span class="ib sm">{I("x")}</span></div>'+F('Искать по','<div class="seg" style="width:100%"><span class="on" style="flex:1;justify-content:center">Дата документа</span><span style="flex:1;justify-content:center">Дата загрузки</span></div>')+'<div class="row g8">'+F('С',f'<div class="inp">{I("cal","ic ic16")}<span class="mono">01.04.2026</span></div>')+F('По',f'<div class="inp">{I("cal","ic ic16")}<span class="mono">30.04.2026</span></div>')+'</div>'+F('Тип','<div class="seg" style="width:100%"><span class="on" style="flex:1;justify-content:center">Все</span><span style="flex:1;justify-content:center">Анализ</span><span style="flex:1;justify-content:center">Заключ.</span></div>')+'<div class="row g8" style="padding-bottom:50px"><button class="btn s lg grow">Сбросить</button><button class="btn p lg grow">Показать 3</button></div></div></div>'
    return f'<div style="filter:none">{M_list(t)}</div><div class="scrim" style="align-items:flex-end"></div>{sh}'
def M_doc(t):
    return f'''<div class="hdr"><span class="ib">{I("back")}</span><span class="h3 grow" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Общий анализ крови</span><span class="ib">{I("more")}</span></div><div style="padding:16px;display:flex;flex-direction:column;gap:14px"><div class="paper" style="width:100%;margin:0;height:240px"><img src="doc01-1.png"></div><div class="row g8"><button class="btn s grow">{I("ext","ic ic16")}Открыть PDF</button><button class="btn s grow">{I("download","ic ic16")}Скачать</button></div><div class="row g8">{tag("an","Анализ")}</div><dl class="kv" style="grid-template-columns:130px 1fr"><dt>Дата документа</dt><dd class="mono">08.04.2026</dd><dt>Загружен</dt><dd class="mono">10.11.2026, 19:02</dd></dl><div class="row"><span class="h3 grow">Заметка</span><span class="save ok">{I("check","ic ic16")}Сохранено</span></div><div class="inp ta" style="min-height:96px">Холестерин в биохимии выше нормы, пересдать в октябре.</div><div class="row"><button class="btn sm t">{I("pencil","ic ic16")}Изменить описание</button><span class="grow"></span><button class="btn sm dgt">{I("trash","ic ic16")}Удалить</button></div></div>'''
def M_upload(t):
    sh='<div class="sheet"><div class="grab"></div><div style="padding:16px;display:flex;flex-direction:column;gap:14px"><h2 class="h2">Новый документ</h2>'+filebox('01-general-blood-test.pdf','79 КБ')+F('Название','<div class="inp f"><span>Общий анализ крови</span></div>')+F('Тип',typeradio(0))+F('Дата документа',f'<div class="inp">{I("cal","ic ic16")}<span class="mono">08.04.2026</span></div>')+'<label class="row g8"><span class="cb"></span>Дата не указана в документе</label><button class="btn p lg" style="margin-bottom:34px">Сохранить в архив</button></div></div>'
    return M_list(t)+'<div class="scrim"></div>'+sh
def M_delete(t):
    sh=f'<div class="sheet"><div class="grab"></div><div style="padding:16px 16px 50px;display:flex;flex-direction:column;gap:16px"><div class="row"><h2 class="h2 grow">Удалить документ?</h2><span class="ib sm">{I("x")}</span></div><p class="muted">«Заключение терапевта» от 10.04.2026, файл и заметка удалятся без возможности восстановления.</p><button class="btn dg lg">Удалить</button><button class="btn s lg">Отмена</button></div></div>'
    return M_list(t)+'<div class="scrim"></div>'+sh
def M_export(t):
    r=lambda on,a,b:f'<div class="radio{" on" if on else ""}"><span class="dot"></span><div class="col"><b style="font-weight:500">{a}</b><span class="faint" style="font-size:13px">{b}</span></div></div>'
    sh=f'<div class="sheet"><div class="grab"></div><div style="padding:16px 16px 50px;display:flex;flex-direction:column;gap:12px"><h2 class="h2">Выгрузить документы</h2>{r(1,"Весь архив","6 документов")}{r(0,"Только найденные","По текущему поиску и фильтру")}<p class="faint" style="font-size:13px">ZIP: PDF с понятными именами, documents.csv и documents.json</p><button class="btn p lg">{I("download")}Скачать ZIP · 466 КБ</button></div></div>'
    return M_list(t)+'<div class="scrim"></div>'+sh
def M_empty(t):
    top=f'<div class="row g8" style="overflow:hidden"><span class="chip"><b>Поиск:</b> рентген<span class="x">{I("x","ic ic16")}</span></span><button class="btn sm t">Сбросить</button></div><div class="card" style="padding:40px 20px;display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center"><span class="fi" style="width:48px;height:48px">{I("search")}</span><h2 class="h3">Ничего не нашлось</h2><p class="muted" style="font-size:13px">По запросу «рентген» документов нет. Проверьте название или сбросьте поиск.</p><button class="btn s">Сбросить поиск</button></div>'
    return M_list(t,idx=[],top=top)
D=[('D01 Онбординг и пустой архив',D_onboarding,'Первый вход: назначение, способ хранения, путь к первому файлу. Пустое состояние = онбординг, без отдельного тура.'),
('D02 Добавление: форма заполнена',lambda t:D_upload(t,'filled'),'Модальное окно после выбора файла. Название подставлено из имени файла, фокус в поле «Название».'),
('D03 Добавление: дата не указана',lambda t:D_upload(t,'nodate'),'Чекбокс блокирует поле даты и объясняет последствия для фильтра.'),
('D04 Добавление: ошибки валидации',lambda t:D_upload(t,'errors'),'Не PDF, пустое название, несуществующая дата. Ошибки у поля, текст без обвинения.'),
('D05 Добавление: обрыв сети',lambda t:D_upload(t,'progress'),'Прогресс загрузки и восстановление после обрыва. Данные формы сохраняются.'),
('D06 Архив: список',D_list,'6 документов, сортировка по дате документа, документ без даты в конце с явной меткой. Тост после добавления.'),
('D07 Фильтр по периоду',D_filtered,'Применённый фильтр виден чипом, есть «Сбросить всё». Подсказка о документе без даты, который не участвует в фильтре.'),
('D08 Ничего не найдено',D_empty_search,'Объясняет, что искали, и даёт два выхода: ослабить фильтр или сбросить всё.'),
('D09 Просмотр документа и заметка',D_doc,'PDF слева, описание и заметка справа. Автосохранение заметки со статусом.'),
('D10 Редактирование описания',lambda t:D_doc(t,True),'Редактирование названия, типа и даты в той же панели, без перехода.'),
('D11 Удаление с подтверждением',D_delete,'Заголовок «глагол + объект?», текст говорит, что действие необратимо. Отмена слева, красный глагол справа, без кнопки по умолчанию и без иконки-вопроса.'),
('D12 Экспорт',D_export,'Объём выгрузки, состав ZIP и размер до скачивания.'),
('D13 Загрузка списка: скелетон',D_skeleton,'Только если ответ дольше 1 с. Повторяет структуру таблицы.'),
('D14 Нет связи с сервером',D_offline,'Баннер вместо пустого экрана, кнопка повтора, данные из кэша только для чтения.'),
('D15 AI-подсказка полей: генерация',D_ai,'Опциональная функция за флагом. Поля заполняются шиммером, ручной путь доступен сразу.'),
('D16 AI-подсказка полей: результат',D_ai_done,'Подсказанные значения помечены, источник даты показан цитатой из PDF.')]
M=[('M01 Онбординг',M_onb,''),('M02 Список',M_list,''),('M03 Добавление (bottom sheet)',M_upload,''),('M04 Фильтр (bottom sheet)',M_filter,''),('M05 Ничего не найдено',M_empty,''),('M06 Документ и заметка',M_doc,''),('M07 Удаление',M_delete,''),('M08 Экспорт',M_export,'')]
def page(title,frames):
    return f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title><link rel="stylesheet" href="app.css"></head><body><div class="board">{"".join(frames)}</div></body></html>'
import sys
boards={
 'desktop-light':[frame('d','light',f(t:='light'),n,d) for n,f,d in D],
 'desktop-dark':[frame('d','dark',f('dark'),n+' · тёмная',d) for n,f,d in D if n[:3] in ('D01','D02','D06','D07','D08','D09','D11','D12','D15')],
 'mobile-light':[frame('m','light',f('light'),n,d) for n,f,d in M],
 'mobile-dark':[frame('m','dark',f('dark'),n+' · тёмная',d) for n,f,d in M if n[:3] in ('M02','M04','M06','M07')],
}
for k,v in boards.items():
    open(f'{k}.html','w').write(page(k,v))
# single-screen pages for review
print({k:len(v) for k,v in boards.items()})
_dl=boards['desktop-light']
open('desktop-light-a.html','w').write(page('desktop-light-a',_dl[:8]))
open('desktop-light-b.html','w').write(page('desktop-light-b',_dl[8:]))
