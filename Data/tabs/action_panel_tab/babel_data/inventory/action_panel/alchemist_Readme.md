usage: code_alchemist.py [-h] [--analyze FILE] [--hybrid FILE [FILE ...]]
                         [--batch DIR] [--iterations ITERATIONS]
                         [--output DIR] [--verbose] [--no-gui]

Code Alchemist - GUI Code Hybridization Tool

options:
  -h, --help            show this help message and exit
  --analyze FILE, -a FILE
                        Analyze a Python file
  --hybrid FILE [FILE ...]
                        Create hybrid from files
  --batch DIR, -b DIR   Batch analyze directory
  --iterations ITERATIONS, -i ITERATIONS
                        Number of iterations to run
  --output DIR, -o DIR  Output directory
  --verbose, -v         Verbose output
  --no-gui              Run in CLI mode only

Examples:
  code_alchemist.py                         # Launch GUI
  code_alchemist.py --analyze file.py       # Analyze single file
  code_alchemist.py --hybrid file1.py file2.py  # Create hybrid from files
  code_alchemist.py --batch /path/to/files  # Batch analyze directory
  code_alchemist.py --iterations 100        # Run iterations on current build
        
Features:
  • Analyze Python/Tkinter code structure
  • Create hybrid builds from multiple sources
  • Iterative refinement with confidence scoring
  • Variable parameter tuning
  • Real-time statistics and logging
        
