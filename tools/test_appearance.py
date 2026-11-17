"""Regression checks for rebuild preservation and the game's OBJ X correction."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pmgen

ROOT = Path(__file__).resolve().parents[1]


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        tpl = self.root / 'templates/Minimal Third Person/Data'
        tpl.mkdir(parents=True)
        (tpl/'Lighting.json').write_text('{"presetName":"Custom","fog":false}')
        (tpl/'PostProcessing.data').write_bytes(b'game-template-post-processing')
        (tpl/'Preview.jpg').write_bytes(b'template-preview')
        (tpl/'MinigameDefinitionData.json').write_text('{}')
        (tpl/'ModSettings.json').write_text('{"SimpleMinigameSettings":{},"SimpleModPlayerSettings":{}}')
        context = patch.object(pmgen, 'GAME_TEMPLATES', str(self.root/'templates'))
        context.start()
        self.addCleanup(context.stop)
        self.mod = pmgen.Mod('Appearance test')
        self.destination = self.root/'mods'

    def build(self):
        return Path(self.mod.write(str(self.destination)))/'Data'

    def profile(self, name='night.json'):
        file = self.root/name
        file.write_text('{"presetName":"Custom","fog":true}')
        return str(file)

    def test_editor_files_and_metadata_survive_two_rebuilds(self):
        data = self.build()
        lighting = b'{"presetName":"My editor sky","fog":true}'
        post = b'manually-edited-binary-post-processing'
        (data/'Lighting.json').write_bytes(lighting)
        (data/'PostProcessing.data').write_bytes(post)
        meta = json.loads((data/'Meta.json').read_text())
        meta.update(SelectedLightingPreset='Night', SelectedPostProcessingPreset='Custom',
                    ModVersion=9, IsUnlocked=True)
        (data/'Meta.json').write_text(json.dumps(meta))
        for _ in range(2):
            self.build()
            self.assertEqual((data/'Lighting.json').read_bytes(), lighting)
            self.assertEqual((data/'PostProcessing.data').read_bytes(), post)
            actual = json.loads((data/'Meta.json').read_text())
            for key in ('SelectedLightingPreset','SelectedPostProcessingPreset','ModVersion','IsUnlocked'):
                self.assertEqual(actual[key],meta[key])

    def test_profiles_seed_new_build_but_do_not_replace_existing_edits(self):
        self.mod.lighting_profile = self.profile()
        self.mod.post_processing_profile = str(self.root/'post.data')
        Path(self.mod.post_processing_profile).write_bytes(b'exported-preset')
        data = self.build()
        self.assertTrue(json.loads((data/'Lighting.json').read_text())['fog'])
        self.assertEqual((data/'PostProcessing.data').read_bytes(),b'exported-preset')
        self.assertEqual(json.loads((data/'Meta.json').read_text())['SelectedLightingPreset'],'Custom')
        (data/'Lighting.json').write_text('{"editor":true}')
        self.build()
        self.assertEqual(json.loads((data/'Lighting.json').read_text()),{'editor':True})

    def test_explicit_replacement_changes_only_selected_profile(self):
        data = self.build()
        self.mod.lighting_profile = self.profile()
        self.mod.replace_appearance = True
        self.build()
        self.assertTrue(json.loads((data/'Lighting.json').read_text())['fog'])
        self.assertEqual((data/'PostProcessing.data').read_bytes(),b'game-template-post-processing')

    def test_missing_profile_does_not_half_apply_appearance(self):
        data = self.build()
        before = (data/'Lighting.json').read_bytes()
        self.mod.lighting_profile = self.profile()
        self.mod.post_processing_profile = str(self.root/'missing.data')
        self.mod.replace_appearance = True
        with self.assertRaises(FileNotFoundError):
            self.build()
        self.assertEqual((data/'Lighting.json').read_bytes(),before)

    def test_deleted_appearance_file_is_restored_without_touching_other(self):
        data = self.build()
        (data/'Lighting.json').unlink()
        (data/'PostProcessing.data').write_bytes(b'keep this')
        self.build()
        self.assertFalse(json.loads((data/'Lighting.json').read_text())['fog'])
        self.assertEqual((data/'PostProcessing.data').read_bytes(),b'keep this')

    def test_screen_uv_is_readable_after_real_importer_x_reflection(self):
        vertices, uv, normals, faces = [], [], [], []
        path = ROOT/'packs/abandoned-park/assets/expansion/screen.obj'
        for line in path.read_text().splitlines():
            bits=line.split()
            if not bits: continue
            if bits[0]=='v': vertices.append(tuple(map(float,bits[1:])))
            if bits[0]=='vt': uv.append(tuple(map(float,bits[1:])))
            if bits[0]=='vn': normals.append(tuple(map(float,bits[1:])))
            if bits[0]=='f': faces.append(bits[1:])
        for token in faces[0]:
            v,t,n=(int(s)-1 for s in token.split('/'))
            x,y,z=vertices[v]
            self.assertEqual(uv[t],(-x+.5,y+.5))
            self.assertEqual(normals[n],(0,0,-1))
        # Importer reverses triangle winding after reflecting X: front remains -Z.
        points=[(-vertices[int(t.split('/')[0])-1][0],vertices[int(t.split('/')[0])-1][1])
                for t in reversed(faces[0])]
        a,b,c=points[:3]
        self.assertLess((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]),0)

    def test_shadow_figures_match_card_after_import(self):
        folder=ROOT/'packs/abandoned-park/assets/expansion/shadow-theatre'
        data=json.loads((folder/'manifest.json').read_text())
        for task in data['tasks']:
            for i,cells in enumerate(task['shapes']):
                vertices=[tuple(map(float,line.split()[1:])) for line in
                          (folder/f'{task["stem"]}_shape_{i}.obj').read_text().splitlines() if line.startswith('v ')]
                self.assertEqual(len(vertices),len(cells)*8)
                imported_cells=[]
                for start in range(0,len(vertices),8):
                    block=vertices[start:start+8]
                    imported_cells.append((round(min(-v[0] for v in block)/.55),
                                           round(min(v[1] for v in block)/.55),
                                           round(min(v[2] for v in block)/.55)))
                self.assertEqual(imported_cells,[tuple(cell) for cell in cells])
                if i==task['answer']:
                    self.assertEqual(sorted(set((x,y) for x,y,z in imported_cells)),
                                     [tuple(cell) for cell in task['silhouette']])

    def test_textured_cube_has_unit_bounds_and_non_degenerate_uv_on_every_face(self):
        vertices,uv,normals,faces=[],[],[],[]
        for line in (ROOT/'packs/abandoned-park/assets/art-direction/surface_cube.obj').read_text().splitlines():
            bits=line.split()
            if not bits: continue
            if bits[0]=='v': vertices.append(tuple(map(float,bits[1:])))
            elif bits[0]=='vt': uv.append(tuple(map(float,bits[1:])))
            elif bits[0]=='vn': normals.append(tuple(map(float,bits[1:])))
            elif bits[0]=='f': faces.append([tuple(int(x)-1 for x in token.split('/')) for token in bits[1:]])
        self.assertEqual(len(faces),6)
        for axis in range(3):
            self.assertEqual((min(v[axis] for v in vertices),max(v[axis] for v in vertices)),(-.5,.5))
        for face in faces:
            self.assertEqual({uv[t] for v,t,n in face},{(0,0),(0,1),(1,1),(1,0)})
            # Use the actual importer's X reflection and reversed winding.
            points=[(-vertices[v][0],vertices[v][1],vertices[v][2]) for v,t,n in reversed(face)]
            a,b,c=points[:3]; u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
            cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            normal=normals[face[0][2]]
            self.assertEqual(cross,(-normal[0],normal[1],normal[2]))
            self.assertGreater(sum(cross[i]*sum(p[i] for p in points)/4 for i in range(3)),0)


if __name__ == '__main__':
    unittest.main()
