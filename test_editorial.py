"""Regression checks for RADAR editorial gate. No Gemini API needed."""
import ast
import pathlib
import re
source=pathlib.Path(__file__).with_name('analyze.py').read_text(encoding='utf-8')
tree=ast.parse(source)
keep=['editorial_precheck']
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in keep)
defs={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('NON_PROJECT',)}
namespace={'re':re,**defs}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'analyze.py','exec'),namespace)
check=namespace['editorial_precheck']
cases=[
 ('Back2Back DJ magazine',{'title':'Magazine : Back2Back, chacun son tour','category':'14 Musique Clips','summary':'DJ festivals and music performance'},False),
 ('Graphisme',{'title':'New graphic identity with typographic design','category':'03 DA Graphisme','summary':'A brand identity by a studio'},False),
 ('Tour announcement',{'title':'Singer announces new tour dates','category':'14 Musique Clips','summary':'Tickets go on sale tomorrow'},False),
 ('Music roundup',{'title':'Best songs of the week','category':'14 Musique Clips','summary':'A selection of new singles'},False),
 ('Stage design',{'title':'Stage design for the Aurora concert','category':'01 Spectacle Concert','summary':'The scenography uses moving lights, a sculptural set and projection mapping'},True),
 ('Broadcast set',{'title':'Broadcast set design for a new TV show','category':'02 TV Broadcast','summary':'A studio set uses modular structures, spatial lighting and projection'},True),
 ('Music video',{'title':'Music video directed by Ana Silva','category':'14 Musique Clips','summary':'The film uses a choreographed camera movement, colored lighting and a practical set'},True),
]
failed=0
for name,item,expected in cases:
 accepted,reason=check(item)
 result='PASS' if accepted==expected else 'FAIL'
 print(f'{result}: {name} => {accepted} ({reason})')
 failed+=accepted!=expected
if failed:raise SystemExit(f'{failed} editorial checks failed')
print(f'Editorial gate: {len(cases)} checks passed. Gemini calls: 0.')
