the    
  plan forward:                                                                 
                                                                                
  Current Architecture Analysis                                                 
                                                                                
  Grep Flight Target System:                                                    
  - grep_flight_v2.py has IPC-based target setting via SET_TARGET messages      
  - target.sh sends targets to grep_flight                                      
  - Current target stored in engine.current_target                              
  - Issue: CLI launch (_launch_claude_terminal at line ~1703) doesn't use       
  working directory                                                             
                                                                                
  Directory Structure:                                                          
  - WorkspaceManager: Well-designed system handling project vs version          
  workspaces                                                                    
  - Version workspace: {version_dir}/.docv2_workspace/ with plans/, tasks/,     
  sessions/, etc.                                                               
  - Project workspace: When project set, uses project's PlannerSuite/, tasks/,  
  etc.                                                                          
                                                                                
  Multiple "Suites" with Different Expectations:                                
  - code_alchemist.py: Has --output for project root, creates                   
  inventory/provisions structure                                                
  - ag_forge: Uses knowledge_forge_data/, modules/, logs/                       
  - planner_wizard.py: Creates Epics/, Plans/, Phases/, Tasks/, Diffs/,         
  Manifests/                                                                    
  - warrior_gui: Manages projects but lacks coordination with code_alchemist    
                                                                                
  Implementation Plan                                                           
                                                                                
  Phase 1: Immediate Fix - CLI Working Directory                                
                                                                                
  File: grep_flight_v2.py                                                       
                                                                                
  Modify _launch_claude_terminal() (and _launch_gemini_terminal()) to:          
                                                                                
  def _launch_claude_terminal(self):                                            
      # ... existing session setup ...                                          
                                                                                
      # Determine working directory                                             
      work_dir = self._get_cli_working_directory()                              
                                                                                
      cmd = [                                                                   
          "xfce4-terminal",                                                     
          "--title=Claude CLI",                                                 
          "--hold",                                                             
          f"--geometry={geometry}",                                             
          f"--working-directory={work_dir}",  # NEW                             
          f"--command={claude_bin}"                                             
      ]                                                                         
      # ... rest of launch ...                                                  
                                                                                
  def _get_cli_working_directory(self) -> str:                                  
      """Get appropriate working directory for CLI launch"""                    
      # Priority 1: If target is set                                            
      if self.target_var.get():                                                 
          target = Path(self.target_var.get())                                  
          if target.is_dir():                                                   
              return str(target)                                                
          elif target.is_file():                                                
              return str(target.parent)                                         
                                                                                
      # Priority 2: If project is set via app_ref                               
      if self.app_ref and hasattr(self.app_ref, 'current_project'):             
          project = self.app_ref.current_project                                
          if project and Path(project).exists():                                
              return str(project)                                               
                                                                                
      # Priority 3: Default to version workspace                                
      return str(self.version_root / ".docv2_workspace")                        
</Notes>:NEW~
-warrior_gui.py needs a auto-set for default project directory location context in 'sub-inventories'
 relative to the new unified directory structure , it has a [Inventory] tab and 
  -current sub-tabs: '[Files]' '[Plans]' '[Modules]' '[Sandbox]'
  -currently main 'project directory' is set at a 'drop-down' to select 'version workspace'
   this finds the old .json and old '/.docv2_workspace' which does not have a unified structure for the modular project systems
    , we could set up toggles to switch context at the warrior_gui and leverage the '[Migrate]' functions ('Manage Versions' ui)
 -Pre created a few examples to work with for layout
 -/home/commander/3_Inventory/Warrior_Flow/versions/main_branch/ [Example | NEW] (for migration of 'main branch modules/functions')
 -/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/main_dev/ [Example | NEW] (For main branch 'plans and epic <-> task/diff' storage ect)
 -/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/main_dev/versions/Warrior_Flow_v09x_Monkey_Buisness_v2/ [Example, Fetch from manifests]
 -/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/projects/buisness/ [Example | for /ag_forge/quick_clip 'buisness variant' apps and software/engineer-design]
 -/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/projects/app_dev/ [Example | for all other types of apps]  
 -/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/main_dev/buisness/ [to store a main branch of buisness/plans/project documents]

-'[New projects]' '[New plans]' '[New task]' buttons all need locating , documenting , audit/review for inclusion in routing(s)
 and surface unified context/data-fields/input-lines/transparency-to-traceback-for-export-of-events at grep_flight as well
  as checks throughly thorugh the warrior_gui.py systems , planner_wizard.py ect.
<Notes/>.                                                                         
  Phase 2: Unified Directory Structure Template                                 
                                                                                
  Create a standard structure that all systems can use:                         
                                                                                
  {version_dir}/                                                                
  ├── .docv2_workspace/          # Version-level workspace (existing)           
  │   ├── plans/                                                                
  │   ├── tasks/                                                                
  │   ├── sessions/                                                             
  │   ├── config/                                                               
  │   └── pfc_history/                                                          
  │                                                                             
  ├── projects/                   # NEW: Unified project container              
  │   └── {project_name}/                                                       
  │       ├── PlannerSuite/      # Planning hierarchy                           
  │       │   ├── Epics/                                                        
  │       │   ├── Plans/                                                        
  │       │   ├── Phases/                                                       
  │       │   ├── Tasks/                                                        
  │       │   └── Milestones/                                                   
  │       ├── inventory/         # Code alchemist provisions                    
  │       │   ├── provisions/    # Scripts from Python-master                   
  │       │   └── sandbox/       # Working copies                               
  │       ├── knowledge/         # Ag_forge knowledge base                      
  │       ├── workspace/         # Active development                           
  │       ├── diffs/             # Change tracking                              
  │       └── .project_meta.json # Project metadata                             
  │                                                                             
  └── templates/                  # NEW: Project templates                      
      ├── code_project/                                                         
      ├── ag_business/                                                          
      └── general/                                                              
                                                                                
  Phase 3: Cross-System Alignment                                               
                                                                                
  1. Update code_alchemist.py:                                                  
  - Add --project-mode flag to work with unified structure                      
  - Coordinate with project system via metadata                                 
                                                                                
  2. Update planner_wizard.py:                                                  
  - Use workspace_manager for path resolution                                   
  - Create projects under unified structure                                     
                                                                                
  3. Update warrior_gui.py:                                                     
  - Add "Inventory" sub-tabs:                                                   
    - Provisions (code_alchemist inventory)                                     
    - Knowledge (ag_forge knowledge base)                                       
    - Templates (project templates)                                             
  - Coordinate with active version identification                               
                                                                                
  4. Create project template system:                                            
  - Template manifest JSON with:                                                
    - Required directories                                                      
    - Default files                                                             
    - Integration hooks (code_alchemist, ag_forge, planner)                     
    - Provision sources (Python-master paths)                                   
                                                                                
  Phase 4: Version Creation Flow                                                
                                                                                
  Update version creation to:                                                   
  1. Create unified directory structure                                         
  2. Initialize .docv2_workspace/                                               
  3. Create default projects/ directory                                         
  4. Link to templates/                                                         
  5. Update stable.json with structure metadata 