"""Create a review archive from explicit source/document roots; exclude local state."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'START_HERE.md','README.md','SUBMISSION_MESSAGE.md','pyproject.toml','uv.lock',
    'Dockerfile','compose.yaml','compose.webui-reports.yaml','.env.example','.gitignore','.dockerignore'}
TREES={'retail','scripts','tests','integrations','docs','evaluation','openspec'}
SUFFIXES={'.py','.js','.css','.html','.md','.json','.txt','.yaml','.yml','.toml'}


def selected(path):
    relative=path.relative_to(ROOT)
    if path.is_symlink() or not path.is_file():
        return False
    if len(relative.parts)==1:
        return relative.name in ROOT_FILES
    return (relative.parts[0] in TREES and path.suffix in SUFFIXES
        and not any(part.startswith('.') or part=='__pycache__' for part in relative.parts)
        and not any((ROOT/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new path to preserve prior evidence.')
    candidates=[ROOT/name for name in ROOT_FILES]
    for directory in TREES:
        candidates.extend((ROOT/directory).rglob('*'))
    files=sorted(p for p in candidates if selected(p))
    manifest={'format':'retail-assessment-source-v1','files':{
        p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'excluded':'Local env files except .env.example, credentials helpers, databases, caches, JSONL logs, virtualenv and Git metadata.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            archive.write(p,'retail-assistant/'+p.relative_to(ROOT).as_posix())
        archive.writestr('retail-assistant/SUBMISSION_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix('.sha256').write_text(digest+'  '+args.output.name+'\n')
    print(json.dumps({'archive':str(args.output),'source_files':len(files),'sha256':digest}))


if __name__=='__main__': main()
