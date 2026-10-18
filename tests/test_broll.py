"""SRT provenance, source-time selections, live review and packaging delivery tests."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from broll import apply_selection, bound_segments, import_source, load_source, parse_srt, select_segments
from build_broll_preview import build, overlay_config, review_qa, serve, verify_bundle
from deliver_broll import deliver, verify
from film_core import build_timeline, digest, read, write

SRT="1\n00:00:00,200 --> 00:00:00,800\n第一句。\n\n2\n00:00:01,200 --> 00:00:01,800\n第二句。\n\n3\n00:00:02,200 --> 00:00:02,800\n第三句。\n"


@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
class BrollContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ivanvideo-broll-');self.root=Path(self.temp.name).resolve()
        self.srt=self.root/'references/input.srt';self.srt.parent.mkdir()
        self.srt.write_text(SRT,encoding='utf-8')
        self.master=self.root/'assets/master.mp4';self.master.parent.mkdir()
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=navy:s=320x180:r=30:d=3',
                        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000:duration=3',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.master)],check=True,capture_output=True)
        write(self.root/'project.json',{'title':'审核测试','fps':30,'width':320,'height':180,'aspect_ratio':'16:9','output':{'container':'mp4','video_codec':'h264'},'narration':{},'safe_area':{},'audio':{'sample_rate':48000,'tracks':[]}})
        write(self.root/'storyboard.json',{'shots':[]})
        write(self.root/'assets/manifest.json',[])
        self.selection={'segments':[{'id':'B01','title':'开场','from_cue':'srt-1','to_cue':'srt-2'},
                                    {'id':'B02','title':'总结','from_cue':'srt-3','to_cue':'srt-3'}]}

    def tearDown(self): self.temp.cleanup()

    def imported(self):
        item=import_source(self.root,self.srt,self.master)
        return self.root/item['source_path'],item['source']

    def applied(self):
        path,source=self.imported();apply_selection(self.root,path,self.selection);return source

    def test_bom_crlf_multiline_and_stable_ids(self):
        self.srt.write_text('\ufeff'+SRT.replace('第一句。','第一行\n第二行').replace('\n','\r\n'),encoding='utf-8')
        cues=parse_srt(self.srt);self.assertEqual(cues[0]['id'],'srt-1');self.assertEqual(cues[0]['text'],'第一行\n第二行')
        self.srt.write_text(SRT.replace('第一句。','已编辑的第一句。'))
        self.assertEqual(parse_srt(self.srt)[0]['id'],'srt-1')

    def test_parser_rejects_malformed_duplicate_reversed_unordered(self):
        for text in ['',SRT.replace('2\n00:','1\n00:'),SRT.replace('00:00:00,800','00:00:00,100'),
                     'nonsense',SRT.replace('00:00:01,200','00:00:00,100'),SRT.replace('00:00:00,200','00:99:00,200')]:
            self.srt.write_text(text)
            with self.assertRaises(ValueError): parse_srt(self.srt)

    def test_import_check_has_no_side_effects(self):
        item=import_source(self.root,self.srt,self.master,check=True)
        self.assertEqual(item['source']['frames'],90)
        self.assertFalse((self.root/'references/broll-sources').exists())
        self.assertEqual(read(self.root/'storyboard.json'),{'shots':[]})

    def test_import_rejects_past_master_and_noninteger_without_explicit_conversion(self):
        self.srt.write_text(SRT.replace('00:00:02,800','00:00:04,800'))
        with self.assertRaisesRegex(ValueError,'beyond'): self.imported()
        self.srt.write_text(SRT)
        from film_core import probe
        meta=probe(self.master);meta['streams'][0]['avg_frame_rate']='30000/1001';meta['streams'][0]['r_frame_rate']='30000/1001'
        with patch('broll.probe',return_value=meta):
            with self.assertRaisesRegex(ValueError,'explicitly choose'): import_source(self.root,self.srt,self.master,check=True)
            self.assertEqual(import_source(self.root,self.srt,self.master,fps=30,check=True)['source']['fps'],30)

    def test_import_snapshot_and_master_tampering(self):
        path,source=self.imported();self.assertEqual(load_source(self.root,path),source)
        (self.root/source['srt_path']).write_text(SRT.replace('第一句','改动'))
        with self.assertRaisesRegex(ValueError,'SRT'): load_source(self.root,path)
        (self.root/source['srt_path']).write_text(SRT)
        self.master.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Master changed'):load_source(self.root,path)

    def test_exact_expand_and_mid_sentence_flags(self):
        _,source=self.imported()
        selection={'segments':[{'id':'B','title':'测试','start_ms':500,'end_ms':1500}]}
        exact=select_segments(source,selection)[0]
        self.assertEqual((exact['start_frame'],exact['end_frame']),(15,45));self.assertTrue(exact['cut_start']);self.assertTrue(exact['cut_end'])
        selection['segments'][0]['snap']='expand';expanded=select_segments(source,selection)[0]
        self.assertEqual((expanded['start_frame'],expanded['end_frame']),(6,54));self.assertFalse(expanded['cut_start']);self.assertFalse(expanded['cut_end'])
        self.assertEqual(expanded['requested_ms'],[500,1500])

    def test_selection_rejects_overlap_unknown_duplicate_and_zero_frames(self):
        _,source=self.imported()
        examples=[{'segments':[{'id':'B','title':'x','from_cue':'unknown','to_cue':'srt-1'}]},
                  {'segments':[{'id':'B','title':'x','start_ms':220,'end_ms':221}]},
                  {'segments':[{'id':'B','title':'x','start_ms':0,'end_ms':3200}]},
                  {'segments':[{'id':'B','title':'x','start_ms':300,'end_ms':1500},{'id':'C','title':'y','start_ms':1400,'end_ms':1700}]}]
        duplicate=copy.deepcopy(self.selection);duplicate['segments'][1]['id']='B01';examples.append(duplicate)
        for example in examples:
            with self.assertRaises(ValueError): select_segments(source,example)

    def test_apply_preserves_source_time_gaps_original_audio_and_backups(self):
        source=self.applied();timeline=build_timeline(self.root)
        self.assertEqual(timeline['frames'],90)
        self.assertEqual(len(timeline['shots']),5)
        _,segments=bound_segments(self.root)
        self.assertEqual([(s['start_frame'],s['end_frame']) for _,s in segments],[(6,54),(66,84)])
        config=read(self.root/'project.json');self.assertTrue((self.root/config['narration']['audio_path']).is_file())
        timing=read(self.root/config['narration']['timing_path']);self.assertEqual([s['id'] for s in timing['segments']],['srt-1','srt-2','srt-3'])
        self.assertEqual(len(list((self.root/'references/broll-apply').glob('*/project.before.json'))),1)
        result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/validate_video_project.py'),str(self.root),'--delivery','--film'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaisesRegex(ValueError,'empty new'):apply_selection(self.root,self.root/config['broll']['source_path'],self.selection)

    def test_apply_does_not_replace_existing_board(self):
        path,_=self.imported();write(self.root/'storyboard.json',{'shots':[{'id':'approved'}]})
        before=digest(self.root/'storyboard.json')
        with self.assertRaisesRegex(ValueError,'preserve existing'):apply_selection(self.root,path,self.selection)
        self.assertEqual(before,digest(self.root/'storyboard.json'))

    def test_apply_rolls_back_failed_config_update(self):
        path,_=self.imported();before=(read(self.root/'project.json'),read(self.root/'storyboard.json'));failed=False
        def fail_once(path,value):
            nonlocal failed
            if Path(path)==self.root/'storyboard.json' and not failed:
                failed=True;raise OSError('injected')
            return write(path,value)
        with patch('broll.write',side_effect=fail_once):
            with self.assertRaises(OSError):apply_selection(self.root,path,self.selection)
        self.assertEqual(before,(read(self.root/'project.json'),read(self.root/'storyboard.json')))
        self.assertFalse((self.root/'audio/broll-subtitles.json').exists())
        self.assertFalse(list((self.root/'audio/broll-source').glob('*.wav')))

    def test_changed_boundaries_and_cue_binding_are_rejected(self):
        self.applied();board=read(self.root/'storyboard.json');original=copy.deepcopy(board)
        board['shots'][1]['end_seconds']+=.1;write(self.root/'storyboard.json',board)
        with self.assertRaisesRegex(ValueError,'interval changed'):build_timeline(self.root)
        original['shots'][1]['broll_segment']['cue_ids']=['srt-3'];write(self.root/'storyboard.json',original)
        with self.assertRaisesRegex(ValueError,'cue binding'):bound_segments(self.root)

    def test_edited_derived_subtitle_timing_is_rejected(self):
        self.applied();config=read(self.root/'project.json');path=self.root/config['narration']['timing_path']
        timing=read(path);timing['segments'][0]['start_seconds']+=.1;write(path,timing)
        with self.assertRaisesRegex(ValueError,'subtitle timing changed'):build_timeline(self.root)

    def test_overlay_validates_actual_circle_geometry_and_bounds(self):
        self.applied();config=read(self.root/'project.json');path=self.root/config['broll']['overlay_path']
        write(path,{'regions':[{'id':'host','kind':'avatar','shape':'circle','x':0,'y':0,'width':.2,'height':.2}]})
        with self.assertRaisesRegex(ValueError,'equal pixel'):overlay_config(self.root,config,320,180)
        write(path,{'regions':[{'id':'outside','kind':'subtitle','x':.9,'y':.9,'width':.2,'height':.2}]})
        with self.assertRaisesRegex(ValueError,'normalized'):overlay_config(self.root,config,320,180)

    def test_review_server_supports_media_byte_ranges(self):
        server=serve(self.root)
        try:
            url=f'http://127.0.0.1:{server.server_port}/assets/master.mp4'
            req=urllib.request.Request(url,headers={'Range':'bytes=10-109'})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status,206);self.assertEqual(response.read(),self.master.read_bytes()[10:110])
                self.assertEqual(response.headers['Accept-Ranges'],'bytes')
            req=urllib.request.Request(url,headers={'Range':'bytes=999999999-'})
            with self.assertRaises(urllib.error.HTTPError) as raised:urllib.request.urlopen(req)
            self.assertEqual(raised.exception.code,416)
        finally:server.shutdown();server.server_close()

    @unittest.skipUnless(importlib.util.find_spec('playwright'),'Existing Playwright environment required')
    def test_real_preview_seek_audio_overlay_notes_and_same_engine_pixels(self):
        self.applied()
        write(self.root/'references/broll-overlay.json',{'regions':[{'id':'test-region','kind':'protected','x':0,'y':0,'width':1,'height':1,'label':'测试区域'},
              {'id':'tiny-subtitle','kind':'subtitle','x':0,'y':.9,'width':1,'height':.02,'font_size':25}]})
        directory=self.root/'previews/review';build(self.root,directory);verify_bundle(directory)
        from playwright.sync_api import sync_playwright
        server=serve(directory)
        try:
            with sync_playwright() as p:
                with p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']) as browser:
                    page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/')
                    page.wait_for_function('window.ivanPreview && window.ivanPreview.ready')
                    page.locator('#scrub').fill('0.7')
                    page.wait_for_function('Math.abs(window.ivanPreview.state().time-.7)<.001')
                    state=page.evaluate('window.ivanPreview.state()');self.assertEqual(state['shot'],'B01');self.assertAlmostEqual(state['audio_time'],.7)
                    image=page.evaluate("[...document.querySelectorAll('iframe')].find(f=>f.style.display==='block').contentWindow.__canvas.toDataURL()")
                    page.locator('#overlays').uncheck()
                    self.assertEqual(image,page.evaluate("[...document.querySelectorAll('iframe')].find(f=>f.style.display==='block').contentWindow.__canvas.toDataURL()"))
                    direct=browser.new_page();direct.goto(f'http://127.0.0.1:{server.server_port}/engine/clip.html?render=1&spec=../specs/B01.json')
                    direct.wait_for_function('window.__ready');direct.evaluate('window.renderFrame(.5)')
                    self.assertEqual(image,direct.evaluate('window.__canvas.toDataURL()'))
                    inspect=page.evaluate('window.ivanPreview.inspect()');self.assertTrue(inspect['warnings'])
                    self.assertTrue(any('subtitle-overflow' in w['regions'] for w in inspect['warnings']))
                    page.locator('#note').fill('检查标题位置');page.locator('#mark').click();self.assertIn('检查标题位置',page.locator('#notes').inner_text())
                    page.evaluate('Promise.all([window.ivanPreview.seek(.4),window.ivanPreview.seek(1.4)])')
                    self.assertAlmostEqual(page.evaluate('window.ivanPreview.state().time'),1.4)
                    with page.expect_download() as result:page.locator('#save').click()
                    download=self.root/'notes.json';result.value.save_as(download)
                    self.assertEqual(read(download)['notes'][0]['shot'],'B01')
        finally:server.shutdown();server.server_close()
        qa=review_qa(directory,self.root/'previews/qa',times=[0,.7,1.4,2.5])
        self.assertFalse(qa['page_errors']);self.assertGreater(qa['playback']['time'],.1)
        (directory/'data.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'bundle changed'):verify_bundle(directory)

    @unittest.skipUnless(importlib.util.find_spec('playwright'),'Existing Playwright environment required')
    def test_real_delivery_frames_table_clean_audio_and_staleness(self):
        self.applied();directory=self.root/'outputs/packaging';records=deliver(self.root,directory)
        self.assertEqual([r['frames'] for r in records],[48,18]);self.assertEqual(records[0]['start_ms'],200)
        self.assertTrue(all(r['checks']['no_audio'] for r in records));self.assertEqual(verify(self.root,directory)['segments'],2)
        text=(directory/'replacement-table.md').read_text();self.assertIn('srt-1, srt-2',text)
        with self.assertRaisesRegex(ValueError,'exists'):deliver(self.root,directory)
        board=read(self.root/'storyboard.json');board['shots'][1]['animation']['data']['title']='改动'
        write(self.root/'storyboard.json',board)
        with self.assertRaisesRegex(ValueError,'stale'):verify(self.root,directory)
        unchanged=build_timeline(self.root)['shots'][3]['media']['path']
        stamp=Path(unchanged).stat().st_mtime_ns
        updated=deliver(self.root,self.root/'outputs/packaging-v2')
        self.assertEqual(records[1]['sha256'],updated[1]['sha256'])
        self.assertEqual(stamp,Path(unchanged).stat().st_mtime_ns)


if __name__=='__main__':unittest.main()
