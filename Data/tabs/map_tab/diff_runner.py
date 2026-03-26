import json
from pathlib import Path
from py_manifest_augmented import (
    Manifest, DiffEngine, RuntimeManifest, RuntimeEvent, FileMetadata,
    ImportInfo, ClassInfo, FunctionInfo, AttributeInfo, ControlFlowNode
)

def main():
    static_path = 'py_manifest.json'
    runtime_path = 'runtime_manifest.json'

    with open(static_path) as f:
        static_data = json.load(f)

    files = {}
    for fpath, meta_data in static_data['files'].items():
        files[fpath] = FileMetadata(
            file_path=meta_data['file_path'],
            hash=meta_data['hash'],
            last_analyzed=meta_data['last_analyzed'],
            imports=[ImportInfo(**imp) for imp in meta_data['imports']],
            classes=[
                ClassInfo(
                    **{k: v for k, v in cls.items() if k != 'methods' and k != 'attributes'}
                ) for cls in meta_data['classes']
            ],
            functions=[FunctionInfo(**func) for func in meta_data['functions']],
            attributes=[AttributeInfo(**attr) for attr in meta_data['attributes']],
            control_flow=[ControlFlowNode(**cf) for cf in meta_data['control_flow']],
            dependencies=set(meta_data['dependencies']),
            errors=meta_data['errors']
        )
        for cls_data, cls_obj in zip(meta_data['classes'], files[fpath].classes):
            cls_obj.methods = [FunctionInfo(**meth) for meth in cls_data['methods']]
            cls_obj.attributes = [AttributeInfo(**attr) for attr in cls_data['attributes']]


    static_manifest = Manifest(
        project_root=static_data['project_root'],
        generated_at=static_data['generated_at'],
        files=files,
        package_dependencies=static_data['package_dependencies'],
        who_log=static_data['who_log'],
        summary=static_data['summary']
    )


    with open(runtime_path) as f:
        runtime_data = json.load(f)

    runtime_manifest = RuntimeManifest(
        run_id=runtime_data['run_id'],
        start_time=runtime_data['start_time'],
        end_time=runtime_data['end_time'],
        script_path=runtime_data['script_path'],
        exit_code=runtime_data['exit_code'],
        events=[RuntimeEvent(**e) for e in runtime_data['events']],
        coverage=runtime_data['coverage'],
        summary=runtime_data['summary']
    )

    diff_engine = DiffEngine(static_manifest, runtime_manifest)
    diff_report = diff_engine.compare()

    print(json.dumps(diff_report, indent=2))

if __name__ == '__main__':
    main()
