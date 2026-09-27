"""Observe installed pages using the exact user-session management link.

Only GETs and the existing read-scope browser-access POST are permitted.
The short-lived capability stays in a private /tmp input, never the report.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

sys.path.append('/tmp/scid-workbench-browser')
from playwright.sync_api import sync_playwright

access = json.loads(Path(sys.argv[1]).read_text())
mode = sys.argv[2]
evidence = Path(__file__).resolve().parent
parsed = urlparse(access['url'])
base = parsed.scheme + '://' + parsed.netloc
report = {'instance_name': access['name'], 'mode': mode, 'live_installed_service': True,
          'allowed_read_access_posts': 0, 'blocked_writes': [], 'http_errors': [], 'javascript_errors': []}
with tempfile.TemporaryDirectory(prefix='scid-nav-live-browser-') as temporary:
    temporary = Path(temporary)
    browser_env = dict(os.environ)
    font = Path('/mnt/c/Windows/Fonts/msyh.ttc')
    if font.is_file():
        fonts = temporary / 'fonts'; fonts.mkdir(); (fonts / font.name).symlink_to(font)
        config = temporary / 'fonts.conf'
        config.write_text(f"<fontconfig><include ignore_missing='yes'>/etc/fonts/fonts.conf</include><dir>{fonts}</dir><cachedir>{temporary}/font-cache</cachedir></fontconfig>")
        browser_env['FONTCONFIG_FILE'] = str(config)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, env=browser_env,
            args=['--no-sandbox', '--no-zygote', '--single-process', '--disable-gpu',
                  '--disable-dev-shm-usage', '--js-flags=--max-old-space-size=32',
                  '--disable-features=BackForwardCache'])
        context = browser.new_context(viewport={'width':1280,'height':900}, locale='zh-CN')
        def guard(route):
            request = route.request
            path = urlparse(request.url).path
            if request.method == 'GET':
                return route.continue_()
            if (request.method == 'POST' and path == '/instances/access'
                    and parse_qs(request.post_data or '').get('scope') == ['read']):
                report['allowed_read_access_posts'] += 1
                return route.continue_()
            report['blocked_writes'].append({'method':request.method,'path':path})
            route.abort()
        context.route('**/*', guard)
        page = context.new_page(); page.set_default_timeout(10000)
        page.on('pageerror', lambda error: report['javascript_errors'].append(str(error)))
        page.on('response', lambda response: report['http_errors'].append(
            {'path':urlparse(response.url).path,'status':response.status}) if response.status >= 400 else None)
        try:
            response = page.goto(access['url'])
            assert response.status == 200, response.status
            assert page.locator('.session-title').inner_text().strip() == access['title'].strip()
            assert page.get_by_role('button', name='进入当前实例工作台', exact=True).count() == 1
            report['bound_instance_shown_on_home'] = True
            if mode == 'directory':
                page.locator(".home-entry[href='/instances/manage']").click()
                current = page.locator('.instance-directory-card').filter(has_text='当前会话已绑定')
                assert current.count() == 1
                assert current.locator('h2').inner_text().strip() == access['title'].strip()
                report['current_instance_status'] = current.locator('.instance-latest').inner_text()
                report['visible_instance_cards'] = page.locator('.instance-directory-card').count()
            else:
                page.get_by_role('button', name='进入当前实例工作台', exact=True).click()
                page.wait_for_url('**/instance/*')
                assert page.locator('#trajectory').count() == 1
                report['trajectory_nodes_in_dom'] = page.locator('.trajectory-node').count()
                report['home_navigation'] = page.locator('.global-navigation .home-button').count() == 1
                report['phase_headings'] = page.locator('.panel-heading h2').all_inner_texts()
            assert page.locator("form[action='/instances/select']").count() == 0
            assert page.locator("form[action='/instances/create']").count() == 0
            report['desktop_height'] = page.evaluate('document.documentElement.scrollHeight')
            page.screenshot(path=str(evidence / f'LIVE_{mode}_1280.png'))
            page.set_viewport_size({'width':390,'height':900})
            report['mobile_overflow'] = page.evaluate('document.documentElement.scrollWidth > innerWidth+2')
            assert not report['mobile_overflow']
            page.screenshot(path=str(evidence / f'LIVE_{mode}_390.png'))
            page.locator('.global-navigation .home-button').click()
            page.wait_for_url(base+'/')
            assert page.locator('.session-title').inner_text().strip() == access['title'].strip()
            report['return_home_keeps_bound_context'] = True
            assert not report['blocked_writes']
            assert not report['http_errors'], report['http_errors']
            assert not report['javascript_errors'], report['javascript_errors']
            report['pass'] = True
        finally:
            context.close(); browser.close()
            (evidence/f'LIVE_{mode}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps(report, ensure_ascii=False), flush=True)
