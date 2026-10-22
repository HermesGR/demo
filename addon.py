# -*- coding: utf-8 -*-
import os, json, re, html, urllib.request, urllib.parse, zipfile, shutil
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
A=xbmcaddon.Addon()
ROOT=xbmcvfs.translatePath(A.getAddonInfo('path'))
PROFILE=xbmcvfs.translatePath(A.getAddonInfo('profile'))
STORE=os.path.join(PROFILE,'games'); ART=os.path.join(PROFILE,'artwork')
ICON=os.path.join(ROOT,'resources','art','icon-1.0.4.png')
FANART=os.path.join(ROOT,'resources','art','background-1.0.4.png')
for p in (STORE,ART): os.makedirs(p,exist_ok=True)
with open(os.path.join(ROOT,'resources','catalog.json'),encoding='utf-8') as f:GAMES=json.load(f)['games']
CORES={'ps1':'game.libretro.pcsx-rearmed','snes':'game.libretro.snes9x','megadrive':'game.libretro.genplus','arcade':'game.libretro.fbneo'}
EXTS={'ps1':('.cue','.chd','.pbp','.iso','.img','.bin'),'snes':('.sfc','.smc'),'megadrive':('.md','.gen','.bin'),'arcade':('.zip',)}
CATEGORIES=list(dict.fromkeys(g['category'] for g in GAMES))

def dialog(text):xbmcgui.Dialog().ok('SorbettoGames',str(text))
def req(url):return urllib.request.Request(url,headers={'User-Agent':'SorbettoGames/1.0.4'})
def read(url,timeout=20):
    with urllib.request.urlopen(req(url),timeout=timeout) as r:return r.read()
def folder(g):return os.path.join(STORE,g['id'])
def installed(g):
    candidates=[os.path.join(p,n) for p,_,names in os.walk(folder(g)) for n in names if n.lower().endswith(EXTS[g['platform']])]
    return min(candidates,key=lambda p:(EXTS[g['platform']].index(os.path.splitext(p)[1].lower()),p)) if candidates else None

def release_assets():
    repo=A.getSetting('github_repo').strip() or 'HermesGR/SorbettoGames'
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Μη έγκυρο repository.')
    tag=A.getSetting('release_tag').strip()
    endpoint='tags/'+urllib.parse.quote(tag,safe='') if tag else 'latest'
    data=json.loads(read('https://api.github.com/repos/'+repo+'/releases/'+endpoint))
    return {a.get('name','').casefold():a for a in data.get('assets',[])}

def image(g):
    path=os.path.join(ART,g['id']+'.png')
    if os.path.isfile(path):return path
    if g['platform']=='arcade':return ICON
    return 'https://thumbnails.libretro.com/'+urllib.parse.quote(g['art_system'],safe='')+'/Named_Boxarts/'+urllib.parse.quote(g['art_title']+'.png',safe='')

def fetch_images():
    indexes={};done=0
    progress=xbmcgui.DialogProgress();progress.create('SorbettoGames','Ανάκτηση εικόνων…')
    try:
        for i,g in enumerate(GAMES):
            if progress.iscanceled():break
            progress.update(int(i*100/len(GAMES)),g['title']);success=False
            for kind in ('Named_Boxarts','Named_Titles'):
                base='https://thumbnails.libretro.com/'+urllib.parse.quote(g['art_system'],safe='')+'/'+kind+'/'
                try:
                    names=[g['art_title']+'.png']
                    if g['platform']=='arcade':
                        if kind not in indexes:
                            page=read(base,10).decode('utf-8',errors='replace')
                            indexes[kind]=[urllib.parse.unquote(html.unescape(x)) for x in re.findall(r'href="([^"<>]+\.png)"',page,re.I)]
                        key=re.sub('[^a-z0-9]','',g['art_title'].casefold())
                        names=[n for n in indexes[kind] if '/' not in n and re.sub('[^a-z0-9]','',os.path.splitext(n)[0].casefold()).startswith(key)]
                        names.sort(key=lambda n:(len(n),n));names=names[:3]
                    for name in names:
                        try:
                            data=read(base+urllib.parse.quote(name,safe=''),8)
                            if not data.startswith(b'\x89PNG\r\n\x1a\n'):continue
                            path=os.path.join(ART,g['id']+'.png')
                            with open(path+'.tmp','wb') as f:f.write(data)
                            os.replace(path+'.tmp',path);done+=1;success=True;break
                        except Exception:pass
                except Exception:pass
                if success:break
    finally:progress.close()
    dialog('Αποθηκεύτηκαν εικόνες: '+str(done)+'/15.')

def download(g,assets):
    asset=assets.get(g['asset'].casefold())
    if not asset:dialog('Το αρχείο του παιχνιδιού δεν έχει ανέβει ακόμη.\nΑναμενόμενο: '+g['asset']);return None
    url=asset.get('browser_download_url','')
    if not url.startswith('https://'):dialog('Μη έγκυρος σύνδεσμος.');return None
    part=folder(g)+'.part';tmp=folder(g)+'.tmp'
    progress=xbmcgui.DialogProgress();progress.create('SorbettoGames','Λήψη: '+g['title'])
    try:
        shutil.rmtree(tmp,ignore_errors=True);os.makedirs(tmp)
        with urllib.request.urlopen(req(url),timeout=90) as r,open(part,'wb') as f:
            total=int(r.headers.get('Content-Length') or 0);count=0
            while True:
                if progress.iscanceled():raise InterruptedError('Η λήψη ακυρώθηκε.')
                data=r.read(262144)
                if not data:break
                f.write(data);count+=len(data)
                progress.update(min(99,int(count*100/total)) if total else 0,'%.1f MB'%(count/1048576))
        with zipfile.ZipFile(part) as z:
            if g['platform']=='arcade':
                members=[m for m in z.infolist() if m.filename.lower().endswith('.zip') and not m.is_dir()]
                if not members:raise ValueError('Το εξωτερικό ZIP Arcade πρέπει να περιέχει το αυθεντικό ZIP ROM set χωρίς μετονομασία, π.χ. bublbobl.zip.')
                for m in members:
                    target=os.path.join(tmp,os.path.basename(m.filename))
                    if os.path.exists(target):raise ValueError('Διπλό όνομα ROM set.')
                    with z.open(m) as src,open(target,'wb') as dst:shutil.copyfileobj(src,dst)
            else:
                root=os.path.abspath(tmp)
                for m in z.infolist():
                    target=os.path.abspath(os.path.join(tmp,m.filename))
                    if os.path.commonpath([root,target])!=root:raise ValueError('Μη ασφαλής διαδρομή ZIP.')
                    if ((m.external_attr>>16)&0o170000)==0o120000:raise ValueError('Δεν επιτρέπονται symlinks.')
                z.extractall(tmp)
            if not any(n.lower().endswith(EXTS[g['platform']]) for _,_,names in os.walk(tmp) for n in names):raise ValueError('Δεν βρέθηκε συμβατό αρχείο παιχνιδιού.')
        shutil.rmtree(folder(g),ignore_errors=True);os.replace(tmp,folder(g));return installed(g)
    except Exception as exc:
        xbmc.log('SorbettoGames download: '+str(exc),xbmc.LOGERROR);dialog('Αποτυχία λήψης/εγκατάστασης.\n'+str(exc))
    finally:
        progress.close();shutil.rmtree(tmp,ignore_errors=True)
        if os.path.isfile(part):os.remove(part)
    return None

def rpc(method,params):
    result=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})))
    if 'error' in result:raise RuntimeError(result['error'].get('message','Kodi JSON-RPC error'))
    return result.get('result',{})
def core_status(core):return rpc('Addons.GetAddonDetails',{'addonid':core,'properties':['enabled']}).get('addon',{}).get('enabled',False)
def ready_core(core):
    try:enabled=core_status(core)
    except Exception:
        xbmc.executebuiltin('InstallAddon('+core+')');monitor=xbmc.Monitor()
        for _ in range(120):
            if monitor.waitForAbort(1):return False
            try:enabled=core_status(core);break
            except Exception:pass
        else:dialog('Δεν ολοκληρώθηκε η εγκατάσταση '+core+'. Ελέγξτε το επίσημο Kodi Add-on repository.');return False
    if not enabled:
        if not xbmcgui.Dialog().yesno('SorbettoGames','Να ενεργοποιηθεί ο εξομοιωτής '+core+';'):return False
        try:
            rpc('Addons.SetAddonEnabled',{'addonid':core,'enabled':True})
            if not core_status(core):raise RuntimeError('Παραμένει απενεργοποιημένος.')
        except Exception as exc:dialog(str(exc));return False
    return True

def launch(g,rom):
    if not rom or not os.path.isfile(rom):dialog('Δεν βρέθηκε το αρχείο παιχνιδιού.');return False
    core=CORES[g['platform']]
    if not ready_core(core):return False
    try:
        item=xbmcgui.ListItem(label=g['title'],path=rom)
        tag=item.getGameInfoTag();tag.setTitle(g['title']);tag.setGameClient(core)
        item.setProperty('gameclient',core);item.setArt({'icon':image(g),'thumb':image(g),'fanart':FANART})
        xbmc.Player().play(rom,item);return True
    except Exception as exc:
        xbmc.log('SorbettoGames RetroPlayer: '+str(exc),xbmc.LOGERROR);dialog('Αποτυχία αιτήματος RetroPlayer.\n'+str(exc));return False

class Menu(xbmcgui.WindowXMLDialog):
    def __init__(self,*args,**kwargs):self.heading='SorbettoGames';self.entries=[];self.choice=-1
    def onInit(self):
        self.getControl(50).setImage(FANART);self.getControl(60).setLabel(self.heading)
        listing=self.getControl(100);listing.reset();listing.addItems(self.entries);self.setFocusId(100)
    def onClick(self,control):
        if control==100:self.choice=self.getControl(100).getSelectedPosition();self.close()
    def onAction(self,action):
        if action.getId() in (9,10,92,216,247):self.close()

def choose(title,labels):
    entries=[]
    for label in labels:
        item=xbmcgui.ListItem(label=label);item.setArt({'icon':ICON,'thumb':ICON,'fanart':FANART});entries.append(item)
    w=Menu('SorbettoMenu.xml',ROOT,'Default','1080i');w.heading=title;w.entries=entries
    w.doModal();choice=w.choice;del w;return choice

def game_menu(g,assets):
    rom=installed(g)
    action=choose(g['title'],['Εκκίνηση' if rom else 'Λήψη και εγκατάσταση','Πληροφορίες','Διαγραφή εγκατάστασης'])
    if action==0:
        if rom:return launch(g,rom)
        rom=download(g,assets)
        if rom and xbmcgui.Dialog().yesno('SorbettoGames','Εγκαταστάθηκε. Να γίνει εκκίνηση;'):return launch(g,rom)
    elif action==1:dialog(g['category']+'\nΕξομοιωτής: '+CORES[g['platform']]+'\nΑναμενόμενο: '+g['asset'])
    elif action==2 and rom and xbmcgui.Dialog().yesno('SorbettoGames','Διαγραφή τοπικής εγκατάστασης;'):shutil.rmtree(folder(g),ignore_errors=True)
    return False

class Browser(xbmcgui.WindowXMLDialog):
    def __init__(self,*args,**kwargs):self.assets={};self.category=None;self.visible_games=[]
    def onInit(self):
        self.getControl(50).setImage(FANART)
        self.fill();self.setFocusId(100)
    def fill(self):
        self.visible_games=[g for g in GAMES if self.category is None or g['category']==self.category]
        items=[]
        for g in self.visible_games:
            state='Εγκατεστημένο' if installed(g) else ('Διαθέσιμο για λήψη' if g['asset'].casefold() in self.assets else 'Αναμένεται το αρχείο παιχνιδιού')
            item=xbmcgui.ListItem(label=g['title'],label2=g['category']+'  •  '+state)
            item.setArt({'icon':image(g),'thumb':image(g),'fanart':FANART});items.append(item)
        listing=self.getControl(100);listing.reset();listing.addItems(items)
        self.getControl(200).setLabel('Κονσόλα: '+(self.category or 'Όλες'))
        self.getControl(61).setLabel(str(len(items))+' παιχνίδια  •  PlayStation 1 πρώτα στην πλήρη λίστα')
    def onClick(self,control):
        if control==100:
            position=self.getControl(100).getSelectedPosition()
            if 0<=position<len(self.visible_games):
                if game_menu(self.visible_games[position],self.assets):self.close()
                else:self.fill();self.setFocusId(100)
        elif control==200:
            selected=xbmcgui.Dialog().select('Φίλτρο κονσόλας',['Όλες']+CATEGORIES)
            if selected>=0:self.category=None if selected==0 else CATEGORIES[selected-1];self.fill();self.setFocusId(100)
        elif control==201:
            try:self.assets=release_assets()
            except Exception as exc:dialog('Δεν ανανεώθηκε το Release.\n'+str(exc))
            self.fill()
        elif control==202:fetch_images();self.fill()
        elif control==203:A.openSettings()
        elif control==204:self.close()
    def onAction(self,action):
        if action.getId() in (9,10,92,216,247):self.close()

def main():
    try:assets=release_assets()
    except Exception as exc:assets={};dialog('Το Release δεν είναι προσβάσιμο. Τα 15 παιχνίδια παραμένουν ορατά.\n'+str(exc))
    browser=Browser('SorbettoBrowser.xml',ROOT,'Default','1080i');browser.assets=assets
    browser.doModal();del browser
if __name__=='__main__':main()
