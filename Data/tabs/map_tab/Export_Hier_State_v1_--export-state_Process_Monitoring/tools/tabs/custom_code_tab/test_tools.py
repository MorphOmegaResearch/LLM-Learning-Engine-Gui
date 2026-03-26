#!/usr/bin/env python3
"""
Tool Testing Script - Simulates model tool calls
Tests the tool execution pipeline as if we were a small language model
"""
import asyncio
import json
import sys
import os

# Add site-packages to path
sys.path.insert(0, '/home/commander/Desktop/BackupOpencode/versions/v1.2/site-packages')

from opencode.tools import ToolManager
from opencode.config import ToolsConfig
from rich.console import Console

console = Console()

class ToolTester:
    def __init__(self):
        # Create minimal config for testing
        config = ToolsConfig(
            enable_file_operations=True,
            enable_command_execution=True,
            enable_git_operations=True,
            enable_context_tools=True,
            max_file_size_mb=10,
            cache_ttl_seconds=300
        )
        self.tool_manager = ToolManager(config)
        self.test_results = []

    async def test_tool(self, tool_name: str, args: dict, description: str):
        """Test a single tool call"""
        console.print(f"\n[bold cyan]TEST: {description}[/bold cyan]")
        console.print(f"[dim]Tool: {tool_name}[/dim]")
        console.print(f"[dim]Args: {json.dumps(args, indent=2)}[/dim]")

        try:
            result = await self.tool_manager.execute_tool(tool_name, **args)

            success = getattr(result, 'success', True)
            output = getattr(result, 'output', '')
            error = getattr(result, 'error', None)

            if success and not error:
                console.print(f"[green]✓ PASSED[/green]")
                if output:
                    # Truncate long output
                    display_output = output[:500] + "..." if len(output) > 500 else output
                    console.print(f"[dim]Output: {display_output}[/dim]")
            else:
                console.print(f"[red]✗ FAILED[/red]")
                console.print(f"[red]Error: {error}[/red]")

            self.test_results.append({
                'test': description,
                'tool': tool_name,
                'success': success,
                'error': error
            })

            return result

        except Exception as e:
            console.print(f"[red]✗ EXCEPTION: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

            self.test_results.append({
                'test': description,
                'tool': tool_name,
                'success': False,
                'error': str(e)
            })

    async def run_all_tests(self):
        """Run comprehensive tool tests"""

        console.print("[bold]Starting Tool Test Suite[/bold]\n")

        # Test 1: file_search for existing file
        await self.test_tool(
            'file_search',
            {'pattern': '*.py', 'path': '.'},
            "Search for Python files"
        )

        # Test 2: file_read with valid path
        await self.test_tool(
            'file_read',
            {'file_path': 'test_tools.py'},
            "Read this test script"
        )

        # Test 3: file_read with non-existent file (should fail gracefully)
        await self.test_tool(
            'file_read',
            {'file_path': 'nonexistent_file.txt'},
            "Read non-existent file"
        )

        # Test 4: file_search with no results
        await self.test_tool(
            'file_search',
            {'pattern': '*.xyz123', 'path': '.'},
            "Search for non-existent file type"
        )

        # Test 5: directory_list current directory
        await self.test_tool(
            'directory_list',
            {'path': '.'},
            "List current directory"
        )

        # Test 6: execute_command (simple ls)
        await self.test_tool(
            'execute_command',
            {'command': 'ls -la'},
            "Execute ls command"
        )

        # Test 7: file_write (create test file)
        await self.test_tool(
            'file_write',
            {'file_path': 'test_output.txt', 'content': 'Test content from tool tester'},
            "Write test file"
        )

        # Test 8: file_read the file we just wrote
        await self.test_tool(
            'file_read',
            {'file_path': 'test_output.txt'},
            "Read back written file"
        )

        # Test 9: code_search for a pattern
        await self.test_tool(
            'code_search',
            {'pattern': 'def test_tool', 'path': '.'},
            "Search for function definition"
        )

        # Test 10: path traversal attempt (SECURITY TEST)
        await self.test_tool(
            'file_read',
            {'file_path': '../../../etc/passwd'},
            "SECURITY: Path traversal attempt (should be blocked)"
        )

        # Test 11: Large file handling (context explosion test)
        # First create a large file
        large_content = "x" * 20000  # 20KB file
        await self.test_tool(
            'file_write',
            {'file_path': 'large_test.txt', 'content': large_content},
            "Create large test file (20KB)"
        )

        # Then try to read it
        await self.test_tool(
            'file_read',
            {'file_path': 'large_test.txt'},
            "Read large file (should truncate)"
        )

        # Cleanup
        console.print("\n[bold]Cleaning up test files...[/bold]")
        os.system('rm -f test_output.txt large_test.txt')

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        console.print("\n" + "="*60)
        console.print("[bold]TEST SUMMARY[/bold]")
        console.print("="*60)

        passed = sum(1 for r in self.test_results if r['success'])
        failed = sum(1 for r in self.test_results if not r['success'])
        total = len(self.test_results)

        console.print(f"\nTotal Tests: {total}")
        console.print(f"[green]Passed: {passed}[/green]")
        console.print(f"[red]Failed: {failed}[/red]")

        if failed > 0:
            console.print("\n[red]Failed Tests:[/red]")
            for result in self.test_results:
                if not result['success']:
                    console.print(f"  - {result['test']}: {result['error']}")

        console.print("\n" + "="*60)

        # Return exit code
        return 0 if failed == 0 else 1

async def main():
    """Main test runner"""
    tester = ToolTester()
    await tester.run_all_tests()
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
