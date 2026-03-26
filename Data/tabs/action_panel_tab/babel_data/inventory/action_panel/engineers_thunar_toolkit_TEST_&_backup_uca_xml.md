<?xml version="1.0" encoding="UTF-8"?>
<actions>
    <action>
        <icon>applications-development</icon>
        <name>Engineer's Toolkit: Open Project</name>
        <unique-id>engineers-toolkit-project</unique-id>
        <command>sh -c '/path/to/engineers-toolkit.sh gui %f'</command>
        <description>Open project in Engineer's Toolkit GUI</description>
        <patterns>*</patterns>
        <directories/>
    </action>
    
    <action>
        <icon>document-save</icon>
        <name>Engineer's Toolkit: Create Snapshot</name>
        <unique-id>engineers-toolkit-snapshot</unique-id>
        <command>sh -c '/path/to/engineers-toolkit.sh snapshot %f'</command>
        <description>Create project snapshot</description>
        <patterns>*</patterns>
        <directories/>
    </action>
    
    <action>
        <icon>edit-find</icon>
        <name>Engineer's Toolkit: Check File</name>
        <unique-id>engineers-toolkit-check</unique-id>
        <command>sh -c '/path/to/engineers-toolkit.sh check %f'</command>
        <description>Run quality checks on file</description>
        <patterns>*.py;*.pyw;*.pyi</patterns>
        <directories/>
    </action>
    
    <action>
        <icon>text-x-generic</icon>
        <name>Engineer's Toolkit: Generate Report</name>
        <unique-id>engineers-toolkit-report</unique-id>
        <command>sh -c '/path/to/engineers-toolkit.sh report %f'</command>
        <description>Generate project report</description>
        <patterns>*</patterns>
        <directories/>
    </action>
    
    <action>
        <icon>utilities-terminal</icon>
        <name>Engineer's Toolkit: Open Terminal Here</name>
        <unique-id>engineers-toolkit-terminal</unique-id>
        <command>sh -c 'cd "%f" && ${SHELL:-bash}'</command>
        <description>Open terminal in selected directory</description>
        <patterns>*</patterns>
        <directories/>
    </action>
</actions>