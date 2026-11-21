"""Real Chromium DOM checks; stdlib only, no browser-profile or NAS mutations.

LIDARR_UI_CATALOG=/path/to/private-catalog.json adds the live metadata scale
check (private read-only inventory, never committed).
"""
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).with_name('release-groups.user.js').read_text()
BROWSER = os.environ.get('LIDARR_UI_BROWSER', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
ARTIST = '22222222-2222-4222-8222-222222222222'


def release(number, title, date, secondary=(), primary='Album'):
    return dict(id=number, foreignAlbumId='00000000-0000-4000-8000-'+str(number).zfill(12), title=title, releaseDate=date, secondaryTypes=list(secondary), albumType=primary)


SAMPLE = [
    release(1, 'Z early studio', '1983-07-25'),
    release(2, 'A late studio', '2008-09-12'),
    release(3, 'Z early live', '1990-01-01', ['Live']),
    release(4, 'A late live', '2020-01-01', ['Live']),
    release(5, 'No release date', None),
    release(6, 'Mixed live compilation', '1995-01-01', ['Compilation', 'Live']),
    release(7, 'Compilation', '2000-01-01', ['Compilation']),
    release(8, '<img src=x onerror="window.injection=true">', '2001-01-01', ['Demo']),
    release(9, 'Mystery type', '2002-01-01', ['Something future']),
    release(10, 'An EP', '2003-01-01', [], 'EP'),
    release(11, 'Live EP', '2004-01-01', ['Live'], 'EP'),
]


class ReleaseGroupsTests(unittest.TestCase):
    def run_browser(self, albums, checks, fail=False, bootstrap=True, native=False, redirect=False, page_title='Sample artist — Lidarr UI test'):
        payload = json.dumps(albums).replace('<', '\\u003c')
        setup = '''
const DATA=__DATA__;
const OTHER_ARTIST='11111111-1111-4111-8111-111111111111';
const OTHER_DATA=[{id:901,foreignAlbumId:'99999999-9999-4999-8999-999999999991',title:'Other studio',releaseDate:'2000-01-01',albumType:'Album',secondaryTypes:[]},{id:902,foreignAlbumId:'99999999-9999-4999-8999-999999999992',title:'Other live',releaseDate:'2001-01-01',albumType:'Album',secondaryTypes:['Live']}];
window.Lidarr={apiRoot:'/api/v1',apiKey:'fixture-only-not-a-credential'};
window.REQUESTS=[];window.NATIVE=0;window.injection=false;
const realFetch=window.fetch.bind(window);
window.fetch=async(url,options={})=>{
 REQUESTS.push({url:String(url),method:options.method||'GET'});
 if(__REDIRECT__)return realFetch(url,options);
 return new Response(JSON.stringify(String(url).includes('/artist')?[{id:198,foreignArtistId:'__ARTIST__'},{id:999,foreignArtistId:OTHER_ARTIST}]:String(url).includes('artistId=999')?OTHER_DATA:DATA),{status:__STATUS__,headers:{'Content-Type':'application/json'}});
};
function makeTable(items){
 const section=document.createElement('section');
 const table=document.createElement('table');
 table.innerHTML='<thead><tr><th>Monitored</th><th>Title</th><th>Release date</th><th><button id="native-gear">⚙</button></th></tr></thead><tbody></tbody>';
 for(const item of items){
  const row=document.createElement('tr');row.dataset.native=String(item.id);
  const monitor=document.createElement('td');const button=document.createElement('button');button.textContent='Monitor';button.className='native-monitor';monitor.append(button);row.append(monitor);
  const title=document.createElement('td');const link=document.createElement('a');link.href='/album/'+item.foreignAlbumId;link.textContent=item.title;title.append(link);row.append(title);
  for(const text of [item.releaseDate||'', 'Actions']){const td=document.createElement('td');td.textContent=text;row.append(td);}
  if(__NATIVE__)row['__reactFiber$fixture']={memoizedProps:{},return:{memoizedProps:item}};
  table.tBodies[0].append(row);
 }
 section.append(table);document.querySelector('main').append(section);return table;
}
window.TABLE=makeTable(DATA.filter(a=>a.albumType==='Album'));
if(DATA.some(a=>a.albumType==='EP'))makeTable(DATA.filter(a=>a.albumType==='EP'));
document.querySelector('main').addEventListener('click',event=>{if(event.target.matches('.native-monitor'))NATIVE++;});
const BEFORE=[...TABLE.tBodies[0].children];
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function assert(condition,message){if(!condition)throw new Error(message);}
const rows=()=>[...TABLE.tBodies[0].querySelectorAll(':scope > tr[data-native]')];
'''.replace('__DATA__', payload).replace('__ARTIST__', ARTIST).replace('__STATUS__', '403' if fail else '200').replace('__NATIVE__', 'true' if native else 'false').replace('__REDIRECT__', 'true' if redirect else 'false')
        if not bootstrap:
            setup=setup.replace("window.Lidarr={apiRoot:'/api/v1',apiKey:'fixture-only-not-a-credential'};", '')
        final = '''
(async()=>{try{
 await sleep(1000);
 __CHECKS__
 assert(!window.injection,'metadata was executed as HTML');
 assert(REQUESTS.every(r=>r.method==='GET'&&new URL(r.url).origin===location.origin),'non-read-only or off-origin request');
 const result=document.createElement('pre');result.id='test-result';result.textContent=JSON.stringify({ok:true,requests:REQUESTS.length,albums:DATA.length});document.body.append(result);
}catch(error){const result=document.createElement('pre');result.id='test-result';result.textContent=JSON.stringify({ok:false,error:error.message,stack:error.stack});document.body.append(result);}})();
'''.replace('__CHECKS__', checks)
        page = '<!doctype html><meta charset="utf-8"><title>Sample artist — Lidarr UI test</title><main></main><script>'+setup+'</script><script>'+SCRIPT+'</script><script>'+final+'</script>'

        redirect_contacts = []

        page = page.replace('<title>Sample artist — Lidarr UI test</title>', '<title>' + html.escape(page_title) + '</title>')

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                redirect_contacts.append(('OPTIONS', False))
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Headers', 'X-Api-Key')
                self.end_headers()

            def do_GET(self):
                if redirect and self.path.startswith('/api/v1/'):
                    self.send_response(302)
                    # Different hostname is a different origin, on this same local fixture.
                    self.send_header('Location', f'http://localhost:{self.server.server_port}/redirect-target')
                    self.end_headers()
                    return
                if self.path.startswith('/redirect-target'):
                    redirect_contacts.append(('GET', 'X-Api-Key' in self.headers))
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'[]')
                    return
                data=page.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='lidarr-ui-test-') as temp:
                process=subprocess.Popen([BROWSER,'--headless','--disable-gpu','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check','--user-data-dir='+temp,'--virtual-time-budget=12000','--dump-dom',f'http://127.0.0.1:{server.server_port}/artist/{ARTIST}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
                try:
                    stdout,stderr=process.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGTERM)
                    try: process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);process.communicate()
                    raise
                result=subprocess.CompletedProcess(process.args,process.returncode,stdout,stderr)
                self.assertEqual(result.returncode,0,result.stderr[-2000:])
                found=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
                self.assertIsNotNone(found,'Browser did not finish: '+result.stderr[-2000:])
                value=json.loads(html.unescape(found.group(1)))
                self.assertTrue(value.get('ok'),value)
                self.assertEqual(redirect_contacts, [], 'Redirect target contacted (method, API-key-present): '+repr(redirect_contacts))
                return value
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_grouping_controls_rerenders_and_original_view(self):
        self.run_browser(SAMPLE, '''
 const headings=[...TABLE.querySelectorAll('tr[data-lrg-release-groups="group"]')];
 assert(headings.length===5,'expected studio, live, compilation, demos and other groups');
 const studio=rows().filter(r=>r.dataset.lrgGroup==='Album:standard');
 assert(studio.map(r=>r.dataset.native).join(',')==='1,2,5','studio dates must beat alphabetical titles and put unknown dates last');
 assert(rows().filter(r=>r.dataset.lrgGroup==='Album:live').map(r=>r.dataset.native).join(',')==='3,6,4','live compilation belongs in live, in date order');
 assert(BEFORE.every(r=>rows().includes(r)),'native rows must retain identity');
 const select=document.querySelector('#lrg-release-toolbar select');select.value='newest';select.dispatchEvent(new Event('change',{bubbles:true}));await sleep(250);
 assert(rows().filter(r=>r.dataset.lrgGroup==='Album:standard').map(r=>r.dataset.native).join(',')==='2,1,5','newest sorting or unknown date placement incorrect');
 const liveHeader=TABLE.querySelector('tr[data-group-key="Album:live"] button');liveHeader.click();await sleep(250);
 assert(liveHeader.getAttribute('aria-expanded')==='false','collapse aria');
 assert(rows().filter(r=>r.dataset.lrgGroup==='Album:live').every(r=>getComputedStyle(r).display==='none'),'collapse did not hide live rows');
 document.querySelector('#lrg-release-toolbar button:nth-of-type(2)').click();await sleep(250);
 const monitor=rows().find(r=>r.dataset.native==='1').querySelector('.native-monitor');monitor.click();assert(NATIVE===1,'native delegated control broken');
 monitor.dispatchEvent(new MouseEvent('click',{bubbles:true,shiftKey:true}));assert(NATIVE===1,'unsafe native shift range allowed');
 document.querySelector('#lrg-release-toolbar [data-toggle]').click();await sleep(250);
 assert(TABLE.querySelectorAll('tr[data-lrg-release-groups="group"]').length===0,'original mode left headers');
 assert(rows().every((r,i)=>r===BEFORE[i]),'original ordering not restored');
 monitor.dispatchEvent(new MouseEvent('click',{bubbles:true,shiftKey:true}));assert(NATIVE===2,'original view must restore native range events');
 document.querySelector('#lrg-release-toolbar [data-toggle]').click();await sleep(250);
 // React-like replacement/removal of native nodes, including a complete table.
 const parent=TABLE.parentElement;parent.remove();TABLE=makeTable(DATA.filter(a=>a.albumType==='Album'));await sleep(350);
 assert(TABLE.querySelectorAll('tr[data-lrg-release-groups="group"]').length===5,'rerender was not regrouped');
 assert(document.querySelectorAll('#lrg-release-toolbar').length===1,'duplicate toolbars');
 window.__lidarrReleaseGroups.stop();
 assert(!document.querySelector('#lrg-release-toolbar'),'stop did not restore');
 assert(!document.querySelector('tr[data-lrg-release-groups]'),'stop left injected or hidden rows');
 ''')

    def test_navigation_does_not_reuse_previous_artist_metadata(self):
        self.run_browser(SAMPLE, """
 assert(TABLE.dataset.lrgGrouped==='true','initial artist not grouped');
 document.querySelector('main').replaceChildren();
 history.pushState({},'', '/artist/'+OTHER_ARTIST);
 TABLE=makeTable(OTHER_DATA);await sleep(1400);
 assert(rows().length===2,'navigation changed the new artist row count');
 assert(rows().find(r=>r.dataset.native==='901').dataset.lrgGroup==='Album:standard','new studio release misclassified');
 assert(rows().find(r=>r.dataset.native==='902').dataset.lrgGroup==='Album:live','new live release misclassified');
 assert(!TABLE.textContent.includes('Z early studio'),'previous artist leaked into new page');
 assert(document.querySelectorAll('#lrg-release-toolbar').length===1,'navigation duplicated toolbar');
 assert(REQUESTS.length===4,'navigation should load metadata once per artist');
 """)

    def test_page_without_bootstrap_uses_same_origin_session(self):
        self.run_browser(SAMPLE, """
 assert(!window.Lidarr,'fixture unexpectedly has bootstrap config');
 assert(TABLE.dataset.lrgGrouped==='true','session-only page did not group');
 assert(REQUESTS.length===2,'expected one artist and one album GET');
 assert(REQUESTS.every(r=>new URL(r.url).pathname.startsWith('/api/v1/')),'fallback API base incorrect');
 """, bootstrap=False)

    def test_native_metadata_needs_no_bootstrap_or_api_requests(self):
        self.run_browser(SAMPLE, """
 assert(TABLE.dataset.lrgGrouped==='true','native metadata did not group');
 assert(REQUESTS.length===0,'native metadata must not make API requests');
 assert(rows().filter(r=>r.dataset.lrgGroup==='Album:live').map(r=>r.dataset.native).join(',')==='3,6,4','native dates/types not used');
 """, bootstrap=False, native=True)

    def test_api_failure_leaves_native_rows_and_actions(self):
        self.run_browser(SAMPLE, '''
 assert(!TABLE.querySelector('tr[data-lrg-release-groups="group"]'),'API failure grouped rows');
 assert(rows().every((r,i)=>r===BEFORE[i]),'API failure changed native rows');
 assert(document.querySelector('[data-note]').textContent.includes('HTTP 403'),'API failure must be visible');
 assert(REQUESTS.length===1,'failed API request retried itself');
 rows()[0].querySelector('.native-monitor').click();assert(NATIVE===1,'native controls unavailable after failure');
 ''', fail=True)

    def test_api_redirect_cannot_forward_credentials(self):
        self.run_browser(SAMPLE, '''
 assert(REQUESTS.length===1,'redirect failure retried itself');
 assert(rows().every((r,i)=>r===BEFORE[i]),'redirect failure changed native rows');
 assert(document.querySelector('[data-note]').textContent.includes('Original rows are unchanged'),'redirect failure not reported');
 ''', redirect=True)

    def test_off_origin_api_root_is_rejected_before_request(self):
        self.run_browser(SAMPLE, '''
 const before=REQUESTS.length;
 window.Lidarr.apiRoot='https://example.invalid/api/v1';
 [...document.querySelectorAll('#lrg-release-toolbar button')].find(b=>b.textContent==='Reload groups').click();
 await sleep(350);
 assert(REQUESTS.length===before,'off-origin API request was sent');
 assert(document.querySelector('[data-note]').textContent.includes('Refusing a different API origin'),'origin rejection not reported');
 ''')

    @unittest.skipUnless(os.environ.get('LIDARR_UI_CATALOG'),'Set LIDARR_UI_CATALOG for live catalog scale test')
    def test_live_catalog_scale_no_missing_or_duplicate_rows(self):
        albums=json.loads(Path(os.environ['LIDARR_UI_CATALOG']).read_text())['albums']
        self.run_browser(albums, '''
 const allRows=[...document.querySelectorAll('tbody tr[data-native]')];
 const expected=DATA.filter(a=>['Album','EP'].includes(a.albumType));
 assert(allRows.length===expected.length,'real-catalog row count changed');
 assert(new Set(allRows.map(r=>r.dataset.native)).size===expected.length,'duplicate catalog rows');
 assert(document.querySelectorAll('[data-group-key="Album:live"]').length===1,'missing live album group');
 for(const table of document.querySelectorAll('table')){
  const byGroup=new Map();
  for(const row of table.querySelectorAll('tr[data-native]')){const list=byGroup.get(row.dataset.lrgGroup)||[];list.push(DATA.find(a=>String(a.id)===row.dataset.native));byGroup.set(row.dataset.lrgGroup,list);}
  for(const entries of byGroup.values()){
   const known=entries.map(a=>Date.parse(a.releaseDate||'')).filter(Number.isFinite);
   assert(known.every((d,i)=>i===0||known[i-1]<=d),'real-catalog dates are not chronological');
  }
 }
 ''')


    def test_other_application_is_untouched(self):
        self.run_browser(SAMPLE, """
 assert(!document.querySelector('#lrg-release-toolbar'),'activated on another application');
 assert(!window.__lidarrReleaseGroups,'registered on another application');
 assert(REQUESTS.length===0,'requested metadata on another application');
 assert(rows().every((r,i)=>r===BEFORE[i]),'changed another application rows');
 """, bootstrap=False, native=True, page_title='Another application')


if __name__=='__main__':
    unittest.main(verbosity=2)
